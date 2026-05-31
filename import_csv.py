import os
import csv
import django
import sys
from decimal import Decimal
from datetime import datetime

# ==========================================
# 1. 环境初始化
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone.settings') 

try:
    django.setup()
except Exception as e:
    print(f"Django 初始化失败: {e}")
    sys.exit(1)

# 导入所有相关模型
from stock.models import AShareStock, Financials, DailyPrice, Industry

# ==========================================
# 2. 配置 CSV 文件路径 (指向 Data 文件夹)
# ==========================================
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")
COMPANIES_CSV = os.path.join(BASE_DIR, "companies.csv")
FINANCIALS_CSV = os.path.join(BASE_DIR, "financials.csv")
PRICES_CSV = os.path.join(BASE_DIR, "daily_prices.csv")

def clean_val(val, default=0):
    """处理空字符串、N/A 或无效数值"""
    if not val or val == 'N/A' or val == '':
        return default
    try:
        # float(val) 可以处理科学计数法如 2.15E+11
        return float(val)
    except ValueError:
        return default

def import_companies():
    print("正在导入行业与股票档案...")
    if not os.path.exists(COMPANIES_CSV):
        print(f"错误：找不到文件 {COMPANIES_CSV}")
        return
        
    with open(COMPANIES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # 1. 先处理 Industry 表 (get_or_create 避免重复)
            industry_name = row.get('industry', 'Other')
            sector_name = row.get('sector', 'Other')
            
            industry_obj, _ = Industry.objects.get_or_create(
                name=industry_name,
                defaults={'sector': sector_name}
            )

            # 2. 更新或创建股票信息，并关联 Industry
            AShareStock.objects.update_or_create(
                symbol=row['symbol'],
                defaults={
                    'name': row.get('full_name', row['symbol']),
                    'industry': industry_obj,
                    'market': row.get('market', 'SH'),  # 从 CSV 读取市场，默认上海
                    'market_type': sector_name,
                    'total_market_cap': int(clean_val(row.get('market_cap'))) if row.get('market_cap') else None,
                    'trailing_pe': Decimal(str(clean_val(row.get('trailing_pe')))) if row.get('trailing_pe') else None,
                    'price_sales': Decimal(str(clean_val(row.get('price_sales')))) if row.get('price_sales') else None,
                    'current_price': Decimal(str(clean_val(row.get('current_price')))) if row.get('current_price') else None,
                }
            )
            count += 1
    print(f"成功导入/更新 {count} 只股票及其行业分类。")

def import_financials():
    print("正在导入详细财务报表 (包含资产负债数据)...")
    if not os.path.exists(FINANCIALS_CSV):
        print(f"错误：找不到文件 {FINANCIALS_CSV}")
        return
    with open(FINANCIALS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                comp = AShareStock.objects.get(symbol=row['symbol'])
                # 处理日期格式 (兼容 2026/1/31 或 2026-01-31)
                date_str = row['report_date'].replace('/', '-')
                
                Financials.objects.update_or_create(
                    symbol=comp,
                    report_date=date_str,
                    defaults={
                        'total_revenue': int(clean_val(row.get('total_revenue'))),
                        'gross_profit': int(clean_val(row.get('gross_profit'))),
                        'operating_income': int(clean_val(row.get('operating_income'))),
                        'net_income': int(clean_val(row.get('net_income'))),
                        'basic_eps': Decimal(str(clean_val(row.get('basic_eps')))),
                        # 新增资产负债字段
                        'total_assets': int(clean_val(row.get('total_assets'))),
                        'total_liabilities': int(clean_val(row.get('total_liabilities'))),
                        'current_assets': int(clean_val(row.get('current_assets'))),
                        'current_liabilities': int(clean_val(row.get('current_liabilities'))),
                        'inventory': int(clean_val(row.get('inventory', 0))),
                    }
                )
                count += 1
            except AShareStock.DoesNotExist:
                continue
    print(f"成功导入 {count} 条财务报表记录。")

def import_daily_prices():
    print("正在同步历史股价...")
    if not os.path.exists(PRICES_CSV):
        print("未找到股价文件，跳过。")
        return
    
    existing_records = set(
        DailyPrice.objects.values_list('symbol__symbol', 'trade_date')
    )

    with open(PRICES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prices_to_create = []
        count = 0
        skipped = 0

        for row in reader:
            trade_date_obj = datetime.strptime(row['trade_date'], '%Y-%m-%d').date()
            if (row['symbol'], trade_date_obj) not in existing_records:
                try:
                    comp = AShareStock.objects.get(symbol=row['symbol'])
                    prices_to_create.append(DailyPrice(
                        symbol=comp,
                        trade_date=row['trade_date'],
                        open_price=Decimal(str(clean_val(row['open_price']))),
                        high_price=Decimal(str(clean_val(row['high_price']))),
                        low_price=Decimal(str(clean_val(row['low_price']))),
                        close_price=Decimal(str(clean_val(row['close_price']))),
                        volume=int(clean_val(row.get('volume')))
                    ))
                except AShareStock.DoesNotExist:
                    continue
            else:
                skipped += 1

            if len(prices_to_create) >= 1000:
                DailyPrice.objects.bulk_create(prices_to_create)
                count += len(prices_to_create)
                prices_to_create = []

        if prices_to_create:
            DailyPrice.objects.bulk_create(prices_to_create)
            count += len(prices_to_create)
            
    print(f"股价同步完成！新增: {count} 条，跳过(已存在): {skipped} 条。")

if __name__ == "__main__":
    import_companies()
    import_financials()
    import_daily_prices()