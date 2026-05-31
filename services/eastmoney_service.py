"""
东方财富 API 服务层
提供 A 股全量股票列表获取和实时行情查询能力。

数据来源:
  - 股票列表: push2.eastmoney.com (无频率限制)
  - 实时行情: push2.eastmoney.com / hq.sinajs.cn (延迟约 3 秒)

使用方式:
  >>> from services import EastMoneyService
  >>> ems = EastMoneyService()
  >>> stocks = ems.get_all_a_stocks()          # 获取全量 A 股列表
  >>> price = ems.get_realtime_price('000001') # 获取单只实时行情
  >>> prices = ems.get_batch_prices(['000001','600519']) # 批量获取
"""

import requests
import time
from decimal import Decimal, InvalidOperation
from functools import lru_cache

# 安全Decimal转换：处理 '-' 'N/A' None 等异常值
def _safe_decimal(val, divisor=1):
    """将东方财富API返回值转为Decimal, 支持 divisor 提前除以"""
    if val is None or val == '' or val == '-':
        return Decimal('0')
    try:
        d = Decimal(str(val))
        if divisor != 1:
            d = d / Decimal(str(divisor))
        return d
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')

def _safe_int(val, default=0):
    """安全整数转换"""
    if val is None or val == '' or val == '-':
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
from typing import Optional


class EastMoneyService:
    """东方财富行情服务"""

    # A股 fs 代码: m=市场 t=板块
    # 沪市: m:1 深市: m:0
    FS_MAP = {
        'sh': 'm:1+t:2,m:1+t:23',              # 上证主板+科创板
        'sz': 'm:0+t:6,m:0+t:80',              # 深证主板+创业板
        'bj': 'm:0+t:81',                       # 北京证券交易所
        'all': 'm:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80,m:0+t:81',
    }

    BASE_URL_LIST = "https://push2.eastmoney.com/api/qt/clist/get"
    BASE_URL_REALTIME = "https://push2.eastmoney.com/api/qt/stock/get"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/",
    }

    # -------- 缓存策略 --------
    # 股票全量列表 24 小时刷新一次（上市公司变化很小）
    _stock_list_cache = None
    _stock_list_cache_time = 0

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # ==========================================
    # 1. 获取 A 股全量列表
    # ==========================================

    def get_all_a_stocks(self, market: str = 'all', force_refresh: bool = False) -> list[dict]:
        """
        获取 A 股全量股票列表。

        Args:
            market: 'sh'|'sz'|'bj'|'all'
            force_refresh: 是否强制刷新缓存

        Returns:
            [{
                'code': '000001',        # 股票代码
                'name': '平安银行',       # 股票名称
                'market': 'SZ',          # 市场 SH/SZ/BJ
                'market_type': '主板',    # 板块类型
                'price': Decimal,        # 最新价
                'pe_ratio': Decimal,     # 市盈率
                'change_pct': Decimal,   # 涨跌幅(%)
                'volume': int,           # 成交量
                'amount': Decimal,       # 成交额
                'total_market_cap': int, # 总市值(元)
            }, ...]
        """
        # 使用缓存（24小时内不重复请求全量列表）
        now = time.time()
        if (not force_refresh and self._stock_list_cache is not None
                and now - self._stock_list_cache_time < 86400):
            return self._stock_list_cache

        all_stocks = []
        page = 1
        while True:
            params = {
                "pn": page,
                "pz": 500,  # 每页 500 条
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fs": self.FS_MAP.get(market, self.FS_MAP['all']),
                "fields": "f2,f3,f4,f5,f6,f7,f8,f12,f13,f14,f15,f16,f17,f18,f20,f21,f100,f115",
            }

            try:
                resp = self.session.get(self.BASE_URL_LIST, params=params, timeout=10)
                data = resp.json()
                items = data.get("data", {}).get("diff", [])
                total = data.get("data", {}).get("total", 0)

                if not items:
                    break

                for item in items:
                    all_stocks.append({
                        'code':         item.get("f12", ""),
                        'name':         item.get("f14", ""),
                        'market':       self._detect_market(item.get("f12", "")),
                        'market_type':  item.get("f100", ""),
                        'price':        _safe_decimal(item.get("f2"), divisor=100),
                        'pe_ratio':     _safe_decimal(item.get("f115"), divisor=100),
                        'change_pct':   _safe_decimal(item.get("f3"), divisor=100),
                        'volume':       _safe_int(item.get("f5")),
                        'amount':       _safe_decimal(item.get("f6")),
                        'total_market_cap': _safe_int(item.get("f20")),
                    })

                print(f"  [EastMoney] 第{page}页: 获取{len(items)}条, 累计{len(all_stocks)}/{total}")
                if len(all_stocks) >= total:
                    break
                page += 1
                time.sleep(0.3)  # 礼貌间隔

            except Exception as e:
                print(f"  [EastMoney] 获取列表失败 (第{page}页): {e}")
                break

        self._stock_list_cache = all_stocks
        self._stock_list_cache_time = now
        print(f"[EastMoney] 共获取 {len(all_stocks)} 只 A 股")
        return all_stocks

    # ==========================================
    # 2. 获取单只股票实时行情
    # ==========================================

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        """
        获取单只股票的实时行情。

        Args:
            symbol: 股票代码, 如 '000001' 或 '600519'

        Returns:
            {
                'code': '000001',
                'name': '平安银行',
                'price': Decimal,        # 最新价
                'open': Decimal,         # 开盘价
                'high': Decimal,         # 最高价
                'low': Decimal,          # 最低价
                'pre_close': Decimal,    # 昨收价
                'volume': int,           # 成交量(手)
                'amount': Decimal,       # 成交额(元)
                'change_pct': Decimal,   # 涨跌幅(%)
                'pe_ratio': Decimal,     # 市盈率
            }
        """
        market_code = self._get_market_code(symbol)
        if not market_code:
            return None

        params = {
            "secid": market_code,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f115,f116,f117,f162,f167,f169,f170",
        }

        try:
            resp = self.session.get(self.BASE_URL_REALTIME, params=params, timeout=8)
            data = resp.json().get("data", {})

            if not data:
                return None

            return {
                'code':       data.get("f57", symbol),
                'name':       data.get("f58", ""),
                'price':      _safe_decimal(data.get("f43"), divisor=100),
                'open':       _safe_decimal(data.get("f46"), divisor=100),
                'high':       _safe_decimal(data.get("f44"), divisor=100),
                'low':        _safe_decimal(data.get("f45"), divisor=100),
                'pre_close':  _safe_decimal(data.get("f60"), divisor=100),
                'volume':     _safe_int(data.get("f47")),
                'amount':     _safe_decimal(data.get("f48")),
                'change_pct': _safe_decimal(data.get("f170"), divisor=100),
                'pe_ratio':   _safe_decimal(data.get("f162"), divisor=100),
            }

        except Exception as e:
            print(f"  [EastMoney] 获取 {symbol} 行情失败: {e}")
            return None

    # ==========================================
    # 3. 批量获取实时行情
    # ==========================================

    def get_batch_prices(self, symbols: list[str]) -> dict[str, dict]:
        """
        批量获取实时行情（一次请求获取多只股票）。

        Args:
            symbols: 股票代码列表, 最多 50 只

        Returns:
            {'000001': {...}, '600519': {...}}
        """
        if len(symbols) > 50:
            # 分批处理
            result = {}
            for i in range(0, len(symbols), 50):
                batch = symbols[i:i + 50]
                result.update(self._batch_request(batch))
                if i + 50 < len(symbols):
                    time.sleep(0.3)
            return result
        return self._batch_request(symbols)

    def _batch_request(self, symbols: list[str]) -> dict[str, dict]:
        """单批请求（最多50只）"""
        secids = []
        for s in symbols:
            mc = self._get_market_code(s)
            if mc:
                secids.append(mc)

        if not secids:
            return {}

        params = {
            "secids": ",".join(secids),
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f115,f116,f117,f162,f167,f169,f170",
        }

        try:
            resp = self.session.get(self.BASE_URL_REALTIME, params=params, timeout=10)
            result = {}
            items = resp.json().get("data", {})

            if isinstance(items, dict):
                # 单只返回 dict，多只返回 dict of dict
                if items.get("f57"):
                    price_info = self._parse_price_item(items)
                    result[price_info['code']] = price_info
                else:
                    for secid, data in items.items():
                        if isinstance(data, dict) and data.get("f57"):
                            price_info = self._parse_price_item(data)
                            result[price_info['code']] = price_info
            return result

        except Exception as e:
            print(f"  [EastMoney] 批量获取行情失败: {e}")
            return {}

    # ==========================================
    # 4. 搜索股票
    # ==========================================

    def search_stocks(self, keyword: str, limit: int = 20) -> list[dict]:
        """
        根据关键字搜索股票。

        Args:
            keyword: 搜索关键字（代码或名称）
            limit: 返回数量上限
        """
        stocks = self.get_all_a_stocks()
        keyword_upper = keyword.upper().strip()

        results = []
        for s in stocks:
            if (keyword_upper in s['code'].upper() or
                    keyword_upper in s['name'].upper()):
                results.append(s)
                if len(results) >= limit:
                    break
        return results

    # ==========================================
    # 辅助方法
    # ==========================================

    @staticmethod
    def _detect_market(code: str) -> str:
        """根据代码判断所属市场"""
        if not code:
            return "UNKNOWN"
        if code.startswith(('60', '68')):
            return "SH"
        elif code.startswith(('00', '30', '002', '003')):
            return "SZ"
        elif code.startswith(('8', '4')):
            return "BJ"
        return "UNKNOWN"

    @staticmethod
    def _get_market_code(code: str) -> Optional[str]:
        """将纯代码转为东方财富 secid 格式"""
        if not code:
            return None
        code = str(code).strip()
        market = EastMoneyService._detect_market(code)
        if market == 'SH':
            return f"1.{code}"
        elif market == 'SZ':
            return f"0.{code}"
        elif market == 'BJ':
            return f"0.{code}"
        return None

    @staticmethod
    def _parse_price_item(data: dict) -> dict:
        """解析单条行情数据"""
        return {
            'code':       data.get("f57", ""),
            'name':       data.get("f58", ""),
            'price':      _safe_decimal(data.get("f43"), divisor=100),
            'open':       _safe_decimal(data.get("f46"), divisor=100),
            'high':       _safe_decimal(data.get("f44"), divisor=100),
            'low':        _safe_decimal(data.get("f45"), divisor=100),
            'pre_close':  _safe_decimal(data.get("f60"), divisor=100),
            'volume':     _safe_int(data.get("f47")),
            'amount':     _safe_decimal(data.get("f48")),
            'change_pct': _safe_decimal(data.get("f170"), divisor=100),
            'pe_ratio':   _safe_decimal(data.get("f162"), divisor=100),
        }


# =========================================================================
# Sina Finance Service (新浪财经 - 更稳定的备用数据源)
# =========================================================================

class SinaFinanceService:
    """
    新浪财经行情服务
    数据格式参考: https://hq.sinajs.cn/list=sh600519,sz000001
    字段顺序:
      0=名称 1=今开 2=昨收 3=现价 4=最高 5=最低
      6=竞买价 7=竞卖价 8=成交量(股) 9=成交额(元)
      10-19=买一到买五 20-29=卖一到卖五
      30=日期 31=时间 32=状态
    """
    BASE_URL = "https://hq.sinajs.cn/list="

    # 最大每批股票数量（新浪单次请求限制）
    MAX_PER_BATCH = 800

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://finance.sina.com.cn/",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    @staticmethod
    def _sina_code(symbol: str) -> str:
        """将纯代码转为新浪格式: 000001 -> sz000001, 600519 -> sh600519"""
        s = str(symbol).strip()
        if s.startswith(('60', '68')):
            return f"sh{s}"
        else:
            return f"sz{s}"

    def get_realtime_price(self, symbol: str) -> Optional[dict]:
        """获取单只股票实时行情"""
        return self.get_batch_prices([symbol]).get(symbol)

    def get_batch_prices(self, symbols: list[str], max_per_batch: int = None) -> dict[str, dict]:
        """批量获取实时行情"""
        if max_per_batch is None:
            max_per_batch = self.MAX_PER_BATCH

        result = {}
        sina_codes = [self._sina_code(s) for s in symbols]

        for i in range(0, len(sina_codes), max_per_batch):
            batch_codes = sina_codes[i:i + max_per_batch]
            batch_symbols = symbols[i:i + max_per_batch]

            # 新浪 API 要求 list 参数直接拼在 URL 中
            url = self.BASE_URL + ",".join(batch_codes)
            try:
                resp = self.session.get(url, timeout=10)
                resp.encoding = 'gbk'
                lines = resp.text.strip().split('\n')

                for j, line in enumerate(lines):
                    if '=' not in line or '""' in line:
                        continue
                    try:
                        data_str = line.split('"')[1]
                        fields = data_str.split(',')
                        if len(fields) < 32:
                            continue

                        # 从返回数据中提取原始代码
                        code_part = line.split('=')[0].replace('var hq_str_', '')
                        orig_symbol = code_part.replace('sh', '').replace('sz', '')

                        # 有时新浪给的是纯数字，确保匹配
                        result[orig_symbol] = {
                            'code': orig_symbol,
                            'name': fields[0],
                            'price': _safe_decimal(fields[3]),
                            'open': _safe_decimal(fields[1]),
                            'high': _safe_decimal(fields[4]),
                            'low': _safe_decimal(fields[5]),
                            'pre_close': _safe_decimal(fields[2]),
                            'volume': _safe_int(fields[8]),
                            'amount': _safe_decimal(fields[9]),
                            'change_pct': _safe_decimal(0),
                            'pe_ratio': None,
                        }
                        # 计算涨跌幅
                        pre = result[orig_symbol]['pre_close']
                        if pre > 0:
                            change = result[orig_symbol]['price'] - pre
                            result[orig_symbol]['change_pct'] = (
                                change / pre * 100
                            ).quantize(Decimal('0.01'))

                    except (IndexError, ValueError) as e:
                        continue

            except Exception as e:
                print(f"  [Sina] 批量获取行情失败: {e}")

        return result

    def search_stock(self, keyword: str) -> Optional[dict]:
        """
        根据代码获取行情（新浪无搜索API，直接查行情）
        """
        return self.get_realtime_price(keyword)

    def get_top_stocks_by_change(self, symbols: list[str], top_n: int = 20) -> list[dict]:
        """
        获取涨幅前 N 只股票
        （需先获取全量行情再排序，适合少量股票）
        """
        prices = self.get_batch_prices(symbols)
        sorted_stocks = sorted(
            prices.values(),
            key=lambda x: x.get('change_pct', Decimal('0')),
            reverse=True
        )
        return sorted_stocks[:top_n]
