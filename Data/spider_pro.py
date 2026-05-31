"""
A股数据爬虫 —— 新浪财经(行情/日线) + 同花顺(财务)
输出: companies.csv / daily_prices.csv / financials.csv

数据源说明:
  - 实时行情/公司名: hq.sinajs.cn（新浪）
  - 历史日线:       ak.stock_zh_a_daily()（新浪）
  - 财务报表:       ak.stock_financial_abstract_ths()（同花顺）
"""
import re
import time
import requests
import pandas as pd
import akshare as ak

# ============================================================
# Monkey-patch: 修复 akshare 在当前网络下 CDN 子域名不通的问题
# 将所有 \d+.push2.eastmoney.com → push2.eastmoney.com
# 将 push2his.eastmoney.com → push2.eastmoney.com
# ============================================================
import akshare.utils.request as _ak_req
_original_request = _ak_req.request_with_retry

def _patched_request(url: str, **kwargs):
    url = re.sub(r'https?://\d+\.(push2\.eastmoney\.com)', r'https://\1', url)
    url = re.sub(r'https?://push2his\.eastmoney\.com', r'https://push2.eastmoney.com', url)
    return _original_request(url, **kwargs)

_ak_req.request_with_retry = _patched_request
# ============================================================

# 15只知名A股（纯代码）
SYMBOLS = [
    '600519',  # 贵州茅台
    '000858',  # 五粮液
    '601318',  # 中国平安
    '000333',  # 美的集团
    '600036',  # 招商银行
    '002415',  # 海康威视
    '600276',  # 恒瑞医药
    '000651',  # 格力电器
    '601166',  # 兴业银行
    '300750',  # 宁德时代
    '600030',  # 中信证券
    '000002',  # 万科A
    '601888',  # 中国中免
    '002594',  # 比亚迪
    '600900',  # 长江电力
]

SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}


def _sina_full_code(symbol: str) -> str:
    """600519 → sh600519, 000858 → sz000858"""
    if symbol.startswith(('6', '5', '9')):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _market(symbol: str) -> str:
    return 'SH' if symbol.startswith(('6', '5', '9')) else 'SZ'


def _fetch_sina_quotes(symbols: list) -> dict:
    """
    批量获取新浪实时行情，返回 {symbol: {name, price, open, high, low, volume}} 
    新浪字段顺序:
      0:名称 1:今开 2:昨收 3:当前价 4:最高 5:最低
      6:竞买价 7:竞卖价 8:成交量(股) 9:成交额(元)
      ...
    """
    full_codes = [_sina_full_code(s) for s in symbols]
    url = f"https://hq.sinajs.cn/list={','.join(full_codes)}"
    try:
        r = requests.get(url, headers=SINA_HEADERS, timeout=15)
        r.encoding = 'gb18030'
    except Exception as e:
        print(f"    [错误] 新浪行情请求失败: {e}")
        return {}

    result = {}
    for line in r.text.strip().split('\n'):
        if not line.strip():
            continue
        # var hq_str_sh600519="贵州茅台,1287.000,..."
        match = re.match(r'var hq_str_(\w+)="(.+)"', line)
        if not match:
            continue
        code = match.group(1).replace('sh', '').replace('sz', '')
        fields = match.group(2).split(',')
        if len(fields) < 9:
            continue
        result[code] = {
            'name': fields[0],
            'open': _safe_float(fields[1]),
            'prev_close': _safe_float(fields[2]),
            'price': _safe_float(fields[3]),
            'high': _safe_float(fields[4]),
            'low': _safe_float(fields[5]),
            'volume': _safe_int(fields[8]),
            'amount': _safe_float(fields[9]),
        }
    return result


def fetch_all_data():
    company_list = []
    financials_list = []
    daily_prices_list = []

    start_date = "20260212"
    end_date = "20260331"

    # === 1. 批量获取新浪实时行情 ===
    print(">>> 正在通过新浪财经获取实时行情...")
    quotes = _fetch_sina_quotes(SYMBOLS)
    print(f"    获取到 {len(quotes)} 只股票行情")

    for symbol in SYMBOLS:
        print(f">>> 正在处理 {symbol} ...")
        market = _market(symbol)
        q = quotes.get(symbol, {})

        # --- 公司基本信息 ---
        company_list.append({
            'symbol': symbol,
            'full_name': q.get('name', symbol),
            'industry': 'N/A',
            'sector': 'N/A',
            'market': market,
            'market_cap': None,
            'trailing_pe': None,
            'price_sales': None,
            'current_price': q.get('price'),
        })

        # --- 历史日线（akshare，新浪数据源）---
        try:
            sina_code = _sina_full_code(symbol)
            hist = ak.stock_zh_a_daily(
                symbol=sina_code,
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            if not hist.empty:
                for _, row in hist.iterrows():
                    daily_prices_list.append({
                        'symbol': symbol,
                        'trade_date': str(row['date'])[:10],
                        'open_price': round(float(row['open']), 4),
                        'high_price': round(float(row['high']), 4),
                        'low_price': round(float(row['low']), 4),
                        'close_price': round(float(row['close']), 4),
                        'volume': int(row['volume']),
                    })
                print(f"    日线数据: {len(hist)} 条")
            else:
                print(f"    日线数据: 无数据")
        except Exception as e:
            print(f"    [错误] 日线数据: {e}")

        # --- 财务报表（akshare，同花顺数据源）---
        try:
            fin = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if not fin.empty and len(fin.columns) >= 2:
                for _, row in fin.head(4).iterrows():
                    report_date = str(row.iloc[0])[:10]
                    financials_list.append({
                        'symbol': symbol,
                        'report_date': report_date,
                        'total_revenue': _safe_num(row.iloc[1]) if len(row) > 1 else None,
                        'gross_profit': None,
                        'operating_income': _safe_num(row.iloc[2]) if len(row) > 2 else None,
                        'net_income': _safe_num(row.iloc[3]) if len(row) > 3 else None,
                        'basic_eps': _safe_num(row.iloc[4]) if len(row) > 4 else None,
                        'total_assets': _safe_num(row.iloc[5]) if len(row) > 5 else None,
                        'total_liabilities': _safe_num(row.iloc[6]) if len(row) > 6 else None,
                        'current_assets': None,
                        'current_liabilities': None,
                        'inventory': None,
                    })
                print(f"    财务数据: {min(len(fin), 4)} 条")
            else:
                print(f"    财务数据: 无数据")
        except Exception as e:
            print(f"    [错误] 财务数据: {e}")

        time.sleep(0.3)

    # --- 导出 CSV ---
    pd.DataFrame(company_list).to_csv('companies.csv', index=False)
    pd.DataFrame(financials_list).to_csv('financials.csv', index=False)
    pd.DataFrame(daily_prices_list).to_csv('daily_prices.csv', index=False)

    print(f"\n===== 数据抓取完成 =====")
    print(f"  公司信息: {len(company_list)} 条")
    print(f"  日线数据: {len(daily_prices_list)} 条")
    print(f"  财务数据: {len(financials_list)} 条")


def _safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _safe_num(val):
    """安全数字转换"""
    if val is None:
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return int(f) if f == int(f) and abs(f) < 1e15 else f
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    fetch_all_data()