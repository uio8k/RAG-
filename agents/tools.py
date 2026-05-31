# agents/tools.py
from django.apps import apps
from decimal import Decimal
from datetime import date


def get_user_holdings_context(user):
    """
    获取用户的实时持仓摘要，供 Agent 决策
    """
    Simulation = apps.get_model('stock', 'Simulation')
    Simulation_Holding = apps.get_model('stock', 'Simulation_Holding')

    active_sim = Simulation.objects.filter(user=user).order_by('-created_at').first()

    if not active_sim:
        return "用户当前没有活跃的模拟账户。"

    holdings = Simulation_Holding.objects.filter(sim=active_sim).exclude(quantity=0)

    if not holdings.exists():
        return f"账户 {active_sim.name} 目前是空仓状态。"

    summary = f"账户名称: {active_sim.name}, 余额: {active_sim.available_cash}\n当前持仓:\n"
    for h in holdings:
        summary += f"- {h.symbol.symbol}({h.symbol.full_name}): {h.quantity}股, 成本价: {h.avg_cost}\n"

    return summary


def get_holdings_daily_price_context(user) -> str:
    """
    获取用户持仓股票的最新日线行情，包含涨跌、成交量等。
    解决 Agent 说"无法获取实时行情"的问题。
    """
    Simulation = apps.get_model('stock', 'Simulation')
    Simulation_Holding = apps.get_model('stock', 'Simulation_Holding')
    DailyPrice = apps.get_model('stock', 'DailyPrice')

    active_sim = Simulation.objects.filter(user=user).order_by('-created_at').first()
    if not active_sim:
        return ""

    holdings = Simulation_Holding.objects.filter(sim=active_sim).exclude(quantity=0)
    if not holdings.exists():
        return "用户当前空仓，无持仓行情数据。"

    lines = ["--- 📊 用户持仓最新行情 (DailyPrice) ---"]
    today = date.today()

    for h in holdings:
        # 获取该股票最新（最接近今天）的日线数据
        latest_price = DailyPrice.objects.filter(
            symbol=h.symbol,
            trade_date__lte=today
        ).order_by('-trade_date').first()

        # 同时获取前一交易日数据用于计算涨跌幅
        prev_price = None
        if latest_price:
            prev_price = DailyPrice.objects.filter(
                symbol=h.symbol,
                trade_date__lt=latest_price.trade_date
            ).order_by('-trade_date').first()

        if latest_price:
            cost = h.avg_cost or Decimal('0')
            current = latest_price.close_price
            pnl_pct = float((current - cost) / cost * 100) if cost > 0 else 0
            change_pct = float(
                (latest_price.close_price - prev_price.close_price) / prev_price.close_price * 100
            ) if prev_price and prev_price.close_price > 0 else 0
            change_sign = "+" if change_pct >= 0 else ""

            lines.append(
                f"- {h.symbol.symbol} {h.symbol.full_name}: "
                f"最新价 ¥{current:.4f} (日期: {latest_price.trade_date}), "
                f"涨跌 {change_sign}{change_pct:.2f}%, "
                f"成交量 {latest_price.volume:,}, "
                f"持仓盈亏 {pnl_pct:+.2f}%"
            )
        else:
            lines.append(f"- {h.symbol.symbol} {h.symbol.full_name}: 暂无日线行情数据")

    return '\n'.join(lines)


def get_latest_market_prices_context(symbols: list = None, top_n: int = 10) -> str:
    """
    获取最新的市场日线行情概览。
    如果提供 symbols 列表则只查询这些股票，否则返回最近有交易的热门股票。
    """
    DailyPrice = apps.get_model('stock', 'DailyPrice')
    today = date.today()

    if symbols:
        prices = []
        for sym in symbols:
            p = DailyPrice.objects.filter(
                symbol__symbol=sym,
                trade_date__lte=today
            ).select_related('symbol').order_by('-trade_date').first()
            if p:
                prices.append(p)
    else:
        # 获取最近有交易的前 top_n 只股票的最新行情
        from django.db.models import Max
        latest_dates = DailyPrice.objects.filter(
            trade_date__lte=today
        ).values('symbol').annotate(max_date=Max('trade_date'))

        symbol_ids = [d['symbol'] for d in latest_dates]
        prices = []
        for sid in symbol_ids[:top_n * 2]:
            p = DailyPrice.objects.filter(
                symbol_id=sid,
                trade_date__lte=today
            ).select_related('symbol').order_by('-trade_date').first()
            if p:
                prices.append(p)
        prices = prices[:top_n]

    if not prices:
        return "⚠️ 暂无日线行情数据，请先导入 daily_prices.csv。"

    lines = ["--- 📈 最新日线行情 ---"]
    lines.append(f"数据日期: {today}\n")
    for p in prices:
        lines.append(
            f"{p.symbol.symbol:<8} {p.symbol.full_name:<15} "
            f"¥{p.close_price:>10.4f}  日期: {p.trade_date}"
        )
    return '\n'.join(lines)


def get_stocks_daily_price_detail(symbols: list) -> str:
    """
    获取指定股票列表的详细日线行情（含开盘/最高/最低/收盘/涨跌幅/成交量）。
    用于用户提到特定股票代码时（如 GOOGL, META, AAPL）。

    Args:
        symbols: 股票代码列表，如 ['GOOGL', 'META', 'AAL']

    Returns:
        格式化的详细行情文本
    """
    DailyPrice = apps.get_model('stock', 'DailyPrice')
    today = date.today()

    if not symbols:
        return ""

    lines = ["--- 📊 指定股票最新行情 (DailyPrice) ---"]
    found_any = False

    for sym in symbols:
        # 获取最新日线
        latest = DailyPrice.objects.filter(
            symbol__symbol__iexact=sym,
            trade_date__lte=today
        ).select_related('symbol').order_by('-trade_date').first()

        if not latest:
            lines.append(f"- {sym}: 数据库中没有该股票的日线行情数据")
            continue

        found_any = True
        # 前一日收盘用于计算涨跌幅
        prev = DailyPrice.objects.filter(
            symbol=latest.symbol,
            trade_date__lt=latest.trade_date
        ).order_by('-trade_date').first()

        change_pct = 0.0
        if prev and prev.close_price > 0:
            change_pct = float(
                (latest.close_price - prev.close_price) / prev.close_price * 100
            )

        change_sign = "+" if change_pct >= 0 else ""
        lines.append(
            f"\n{latest.symbol.symbol} ({latest.symbol.full_name}) - 日期: {latest.trade_date}\n"
            f"  开盘: ¥{latest.open_price:.4f}  最高: ¥{latest.high_price:.4f}  "
            f"最低: ¥{latest.low_price:.4f}  收盘: ¥{latest.close_price:.4f}\n"
            f"  涨跌幅: {change_sign}{change_pct:.2f}%  成交量: {latest.volume:,}"
        )

    if not found_any:
        return f"⚠️ 以下股票在 DailyPrice 表中均无数据: {', '.join(symbols)}。请先导入 daily_prices.csv。"

    return '\n'.join(lines)


def get_a_share_market_context(keyword: str = None, top_n: int = 1024) -> str:
    """
    获取 A 股实时行情摘要，供 Agent 分析。

    Args:
        keyword: 搜索关键字（代码或名称），None 则返回涨幅榜
        top_n: 返回前 N 条

    Returns:
        格式化的行情摘要文本
    """
    try:
        AShareRealtimePrice = apps.get_model('stock', 'AShareRealtimePrice')
        AShareStock = apps.get_model('stock', 'AShareStock')

        # 检查实时行情是否已刷新
        price_count = AShareRealtimePrice.objects.count()
        if price_count == 0:
            return ("⚠️ A股实时行情数据尚未刷新，请先运行:\n"
                    "  python manage.py populate_a_stocks --refresh\n"
                    "已有 AShareStock 股票列表数据可供基础查询。")

        if keyword:
            # 搜索模式
            results = AShareRealtimePrice.objects.filter(
                models.Q(symbol__icontains=keyword) |
                models.Q(name__icontains=keyword)
            ).order_by('-change_pct')[:top_n]
        else:
            # 默认涨幅榜
            results = AShareRealtimePrice.objects.order_by(
                '-change_pct'
            )[:top_n]

        if not results.exists():
            return f"未找到与 '{keyword}' 相关的A股行情。"

        lines = [f"--- 📈 A股实时行情摘要 (涨幅前{top_n}名 / 共{price_count}只) ---"]
        lines.append("数据来源: 新浪财经\n")
        lines.append(f"{'代码':<8} {'名称':<10} {'现价':>8} {'涨跌幅':>8}")
        lines.append("-" * 40)

        for r in results:
            change_sign = "+" if r.change_pct >= 0 else ""
            lines.append(
                f"{r.symbol:<8} {r.name:<10} ¥{r.price:>7.2f} {change_sign}{r.change_pct:>7.2f}%"
            )

        # 统计涨跌数量
        up_count = AShareRealtimePrice.objects.filter(change_pct__gt=0).count()
        down_count = AShareRealtimePrice.objects.filter(change_pct__lt=0).count()
        lines.append(f"\n📊 上涨: {up_count} 只 | 下跌: {down_count} 只")

        return '\n'.join(lines)

    except Exception as e:
        return f"获取A股行情失败: {e}"


def get_a_share_detail(symbol: str) -> str:
    """
    获取单只 A 股的详细行情信息。

    Args:
        symbol: 股票代码，如 '000001'

    Returns:
        详细的行情信息文本
    """
    try:
        AShareRealtimePrice = apps.get_model('stock', 'AShareRealtimePrice')

        price = AShareRealtimePrice.objects.filter(symbol=symbol).first()
        if not price:
            return f"未找到 {symbol} 的实时行情，请先刷新数据。"

        lines = [
            f"--- 📊 {price.symbol} {price.name} 实时行情 ---",
            f"最新价: ¥{price.price}",
            f"开盘价: ¥{price.open_price}",
            f"最高价: ¥{price.high_price}",
            f"最低价: ¥{price.low_price}",
            f"昨收价: ¥{price.pre_close}",
            f"成交量: {price.volume:,} 手",
            f"成交额: ¥{price.amount:,.0f}",
            f"涨跌幅: {price.change_pct:+.2f}%",
        ]
        if price.pe_ratio:
            lines.append(f"市盈率: {price.pe_ratio:.2f}")

        return '\n'.join(lines)

    except Exception as e:
        return f"获取 {symbol} 详情失败: {e}"


# ==========================================
# 7. Web Search (Firecrawl API) — 联网搜索
# ==========================================
import os as _os
import requests as _requests

_FIRECRAWL_API_KEY = _os.environ.get("FIRECRAWL_API_KEY", "")
_FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"


def search_web_finance(query: str, limit: int = 5) -> str:
    """
    使用 Firecrawl 搜索网络，获取股票/金融相关信息。
    
    Args:
        query: 搜索关键词，如 "贵州茅台 最新消息"
        limit: 返回结果数（默认5）
    
    Returns:
        格式化的搜索结果文本
    """
    if not _FIRECRAWL_API_KEY:
        return ""  # 静默跳过，不污染 prompt

    try:
        resp = _requests.post(
            f"{_FIRECRAWL_API_URL}/search",
            headers={
                "Authorization": f"Bearer {_FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "limit": limit,
                "scrapeOptions": {"formats": ["markdown"]},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("data"):
            return ""

        lines = [f"--- 🌐 网络搜索: {query} ---"]
        for item in data["data"][:limit]:
            title = item.get("title", "无标题")
            url = item.get("url", "")
            description = item.get("description", "")
            content = item.get("markdown", "")

            lines.append(f"\n### {title}")
            if description:
                lines.append(f"摘要: {description[:300]}")
            if content:
                lines.append(f"内容: {content[:600]}")

        return '\n'.join(lines)

    except Exception:
        return ""  # 网络失败不阻塞主流程


def search_stock_news(stock_name: str, stock_code: str = "") -> str:
    """搜索特定股票的最新新闻"""
    query = f"{stock_name} {stock_code} 股票 最新消息 2026"
    return search_web_finance(query, limit=3)


# 延迟导入 Django models（避免循环引用）
def _get_models():
    from django.db import models
    return models
models = _get_models()