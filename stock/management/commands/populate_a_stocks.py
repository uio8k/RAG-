"""
Django 管理命令：导入 A 股全量股票列表和实时行情。

用法:
  python manage.py populate_a_stocks              # 导入热门A股列表
  python manage.py populate_a_stocks --refresh     # 强制刷新行情
  python manage.py populate_a_stocks --symbol 000001 # 获取单只行情
  python manage.py populate_a_stocks --source sina  # 使用新浪API（默认）
  python manage.py populate_a_stocks --source eastmoney  # 使用东方财富API
"""

from django.core.management.base import BaseCommand
from services.eastmoney_service import EastMoneyService, SinaFinanceService
from stock.models import AShareStock, AShareRealtimePrice
from decimal import Decimal
import time

# 精选热门A股列表（当全量API不可用时作为fallback）
HOT_A_STOCKS = [
    # 上证主板
    ("600519", "贵州茅台"), ("600036", "招商银行"), ("601318", "中国平安"),
    ("600030", "中信证券"), ("601012", "隆基绿能"), ("600900", "长江电力"),
    ("603259", "药明康德"), ("600276", "恒瑞医药"), ("601166", "兴业银行"),
    ("600050", "中国联通"), ("601398", "工商银行"), ("600809", "山西汾酒"),
    ("600031", "三一重工"), ("600585", "海螺水泥"), ("601888", "中国中免"),
    # 上证科创板
    ("688981", "中芯国际"), ("688012", "中微公司"),
    # 深圳主板
    ("000001", "平安银行"), ("000858", "五粮液"), ("000725", "京东方A"),
    ("002415", "海康威视"), ("002594", "比亚迪"), ("002230", "科大讯飞"),
    ("002475", "立讯精密"), ("002714", "牧原股份"), ("000333", "美的集团"),
    ("000002", "万科A"), ("001979", "招商蛇口"), ("002304", "洋河股份"),
    # 创业板
    ("300750", "宁德时代"), ("300059", "东方财富"), ("300015", "爱尔眼科"),
    ("300124", "汇川技术"), ("300059", "东方财富"), ("300274", "阳光电源"),
    ("300498", "温氏股份"), ("300760", "迈瑞医疗"),
]


class Command(BaseCommand):
    help = '从新浪/东方财富导入 A 股股票列表和实时行情'

    def add_arguments(self, parser):
        parser.add_argument('--refresh', action='store_true',
            help='强制刷新实时行情')
        parser.add_argument('--symbol', type=str,
            help='只获取指定股票的行情，如 000001')
        parser.add_argument('--limit', type=int, default=0,
            help='限制行情获取数量（0=全部）')
        parser.add_argument('--source', type=str, default='sina',
            choices=['sina', 'eastmoney'],
            help='数据源：sina(新浪,默认) 或 eastmoney(东方财富)')

    def handle(self, *args, **options):
        source = options['source']
        use_sina = (source == 'sina')

        # ==========================================
        # Step 1: 导入 A 股列表
        # ==========================================
        self.stdout.write(self.style.WARNING(
            f'\n=== Step 1: 获取 A 股列表 (数据源: {source}) ==='
        ))

        imported = 0
        updated = 0

        if use_sina or source == 'eastmoney':
            # 尝试东方财富全量列表
            # 如果失败，使用内置热门列表
            try:
                ems = EastMoneyService()
                all_stocks = ems.get_all_a_stocks(force_refresh=True)
                if len(all_stocks) < 10:
                    raise Exception("API返回数据不足")
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'  API 获取失败: {e}\n  切换到内置热门A股列表...'
                ))
                all_stocks = [
                    {'code': c, 'name': n, 'market': ('SH' if c.startswith(('6','68')) else 'SZ'),
                     'market_type': '', 'total_market_cap': 0}
                    for c, n in HOT_A_STOCKS
                ]

            for stock in all_stocks:
                _, created = AShareStock.objects.update_or_create(
                    symbol=stock['code'],
                    defaults={
                        'name': stock['name'],
                        'market': stock['market'],
                        'market_type': stock.get('market_type', ''),
                        'total_market_cap': stock.get('total_market_cap', 0),
                    }
                )
                if created:
                    imported += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'  股票列表: 新增 {imported} 只, 更新 {updated} 只, 共 {AShareStock.objects.count()} 只'
        ))

        # ==========================================
        # Step 2: 获取实时行情
        # ==========================================
        if options['refresh'] or options['symbol']:
            self.stdout.write(self.style.WARNING('\n=== Step 2: 获取实时行情 ==='))
            self._fetch_realtime_prices(options)
        else:
            self.stdout.write(self.style.NOTICE(
                '\n提示: 使用 --refresh 参数可同步获取实时行情'
            ))

    def _fetch_realtime_prices(self, options):
        """批量获取实时行情"""
        sina = SinaFinanceService()
        ems = None

        if options['symbol']:
            symbols = [options['symbol']]
        else:
            stocks = AShareStock.objects.all()
            if options['limit'] > 0:
                stocks = stocks[:options['limit']]
            symbols = [s.symbol for s in stocks]

        total = len(symbols)
        saved = 0

        # 尝试新浪API（每批50只）
        self.stdout.write(f'  正在从新浪财经获取 {total} 只股票的行情...')
        prices = sina.get_batch_prices(symbols, max_per_batch=50)

        for symbol, price_info in prices.items():
            if not price_info.get('name'):
                continue
            AShareRealtimePrice.objects.update_or_create(
                symbol=symbol,
                defaults={
                    'name': price_info.get('name', ''),
                    'price': price_info.get('price', Decimal('0')),
                    'open_price': price_info.get('open', Decimal('0')),
                    'high_price': price_info.get('high', Decimal('0')),
                    'low_price': price_info.get('low', Decimal('0')),
                    'pre_close': price_info.get('pre_close', Decimal('0')),
                    'volume': price_info.get('volume', 0),
                    'amount': price_info.get('amount', Decimal('0')),
                    'change_pct': price_info.get('change_pct', Decimal('0')),
                    'pe_ratio': price_info.get('pe_ratio'),
                }
            )
            saved += 1

        self.stdout.write(self.style.SUCCESS(
            f'  实时行情: 成功保存 {saved}/{total} 条, 共 {AShareRealtimePrice.objects.count()} 条'
        ))

        # 打印涨跌幅前5
        top5 = AShareRealtimePrice.objects.order_by('-change_pct')[:5]
        self.stdout.write('\n  📈 涨幅前5:')
        for p in top5:
            self.stdout.write(
                f'    {p.symbol} {p.name}  ¥{p.price}  {p.change_pct:+.2f}%'
            )

