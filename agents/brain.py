# agents/brain.py
import os
import re
import requests
from datetime import date
from django.apps import apps
from .memory import VectorMemory
from .tools import (
    get_user_holdings_context,
    get_holdings_daily_price_context,
    get_a_share_market_context,
    get_a_share_detail,
    get_latest_market_prices_context,
    get_stocks_daily_price_detail,
    search_web_finance,
    search_stock_news,
)

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


class FinancialBrain:
    # === 类级别单例：共享同一个 VectorMemory，避免重复加载模型和重建索引 ===
    _shared_memory = None
    _api_available = None  # 缓存 API 可用性检测结果

    def __init__(self, model_name=None):
        self.model_name = model_name or DEEPSEEK_MODEL
        # 所有 FinancialBrain 实例共享同一个 VectorMemory
        if FinancialBrain._shared_memory is None:
            print("--- [Brain] 初始化共享向量内存 (仅此一次) ---")
            FinancialBrain._shared_memory = VectorMemory()
        self.memory = FinancialBrain._shared_memory

        # 首次初始化时检测 API
        if FinancialBrain._api_available is None:
            FinancialBrain._api_available = self._check_api()

    def _check_api(self) -> bool:
        """检测 DeepSeek API 是否可用"""
        if not DEEPSEEK_API_KEY:
            print("--- [Brain] ⚠️ 未设置 DEEPSEEK_API_KEY，请创建 .env 文件或设置环境变量 ---")
            return False
        try:
            resp = requests.get(
                f"{DEEPSEEK_BASE_URL}/models",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"--- [Brain] ✅ DeepSeek API 连接成功 (模型: {self.model_name}) ---")
                return True
            else:
                print(f"--- [Brain] ⚠️ DeepSeek API 返回 {resp.status_code}: {resp.text[:200]} ---")
                return False
        except Exception as e:
            print(f"--- [Brain] ⚠️ DeepSeek API 连接失败: {e} ---")
            return False

    def _call_deepseek(self, system_prompt: str, user_query: str) -> str:
        """调用 DeepSeek API (OpenAI 兼容格式)"""
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False,
        }
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _sync_simulation_date(self, user):
        """
        将用户的仿真日期同步为本地计算机时间。
        同时更新 Simulation.current_virtual_date 和 GlobalSimulationState。
        """
        Simulation = apps.get_model('stock', 'Simulation')
        today = date.today()

        active_sim = Simulation.objects.filter(user=user).order_by('-created_at').first()
        if active_sim and active_sim.current_virtual_date != today:
            active_sim.current_virtual_date = today
            active_sim.save(update_fields=['current_virtual_date'])
            print(f"--- [Brain] 仿真日期已同步: {active_sim.current_virtual_date} → {today} ---")

        # 同步全局仿真状态
        try:
            GlobalSimulationState = apps.get_model('stock', 'GlobalSimulationState')
            global_state = GlobalSimulationState.objects.first()
            if global_state and global_state.current_global_date != today:
                global_state.current_global_date = today
                global_state.save(update_fields=['current_global_date'])
                print(f"--- [Brain] 全局仿真日期已同步: → {today} ---")
        except LookupError:
            pass

        return today

    def think(self, user, user_query):
        """
        Agent 决策逻辑：整合 美股财报 + A股实时行情 + 每日行情 + 用户持仓。
        调用 DeepSeek API 进行推理。
        """
        # 0. API 检查
        if not FinancialBrain._api_available:
            return (
                "⚠️ DeepSeek API 未配置或不可用。请按以下步骤设置：\n\n"
                "1. 在项目根目录创建 .env 文件\n"
                "2. 添加: DEEPSEEK_API_KEY=你的API密钥\n"
                "3. 可选: DEEPSEEK_MODEL=deepseek-v4-pro\n"
                "4. 重启服务器"
            )

        # 1. 仿真日期同步为本地计算机时间
        today = self._sync_simulation_date(user)
        print(f"--- [Brain] 当前仿真日期(本地时间): {today} ---")

        # 2. 检测用户问题类型，决定数据源
        query_lower = user_query.lower()
        is_a_share_query = any(kw in query_lower for kw in [
            'a股', 'a-share', 'a_share', 'ashare',
            '上证', '深证', '创业板', '科创板', '沪深',
            '中国股市', '国内', '茅台', '宁德', '比亚迪',
            '600', '601', '603', '688',  # 上证代码
            '000', '001', '002', '003',  # 深证代码
            '300', '301',                 # 创业板
        ])
        # 检测 A 股具体代码
        code_match = re.search(r'(sz|sh)?(\d{6})', user_query)
        specific_code = code_match.group(2) if code_match else None

        # === 提取用户问题中提到的美股代码（大写字母 1-5 位） ===
        us_symbols = re.findall(r'\b([A-Z]{1,5})\b', user_query)
        # 过滤掉常见的非股票英文单词
        noise_words = {'A', 'I', 'AI', 'API', 'IT', 'THE', 'IS', 'ARE', 'FOR', 'AND',
                       'OR', 'TO', 'IN', 'ON', 'AT', 'BY', 'BE', 'DO', 'GO', 'NO', 'OK',
                       'IF', 'AS', 'SO', 'WE', 'US', 'ME', 'HE', 'HI', 'MY', 'NEW', 'BUY',
                       'SELL', 'NOW', 'ALL', 'CAN', 'HAS', 'HAD', 'WAS', 'WILL', 'WHAT',
                       'WHEN', 'HOW', 'WHY', 'WHO', 'WHICH', 'FROM', 'WITH', 'THIS', 'THAT',
                       'JUST', 'LIKE', 'HAVE', 'BEEN', 'MORE', 'SOME', 'ALSO', 'ONLY',
                       'MUCH', 'VERY', 'GOOD', 'BAD', 'HIGH', 'LOW', 'BIG', 'TOP', 'LONG',
                       'SHORT', 'PUT', 'CALL', 'ETF', 'IPO', 'CEO', 'CFO', 'GDP', 'EPS',
                       'PE', 'PS', 'PB', 'ROE', 'ROA', 'YOY', 'QOQ', 'USD', 'CNY', 'HKD'}
        us_symbols = [s for s in us_symbols if s not in noise_words]

        print(f"--- [Brain] 检测到美股代码: {us_symbols if us_symbols else '无'} ---")

        # 3. === 收集价格数据（三层策略：持仓行情 > 用户指定股票 > 市场概览） ===
        price_data_sections = []

        # 3a. 持仓行情
        holdings_price = get_holdings_daily_price_context(user)
        has_holdings_data = holdings_price and "空仓" not in holdings_price

        # 3b. 用户提到的特定美股 → 查详细行情
        if us_symbols:
            specific_stocks_detail = get_stocks_daily_price_detail(us_symbols)
            if specific_stocks_detail and "无数据" not in specific_stocks_detail:
                price_data_sections.append(specific_stocks_detail)

        # 3c. 持仓行情
        if has_holdings_data:
            price_data_sections.append(holdings_price)
        # 如果既没持仓也没提到具体股票，回退到市场概览
        elif not us_symbols:
            market_overview = get_latest_market_prices_context(top_n=10)
            if market_overview and "暂无" not in market_overview:
                price_data_sections.append(market_overview)

        # 合并所有价格数据
        daily_price_context = '\n'.join(price_data_sections) if price_data_sections else ""

        # 获取用户持仓背景
        holdings_context = get_user_holdings_context(user)

        # 4. 根据问题类型获取额外数据
        a_share_context = ""
        financial_knowledge = ""

        # === A股行情：始终获取，作为默认市场参考 ===
        # 不再只在检测到A股关键词时才查询
        a_share_context = get_a_share_market_context(top_n=1024)

        if is_a_share_query:
            if specific_code:
                # 用户指定了具体A股代码，补充详细行情
                a_share_detail = get_a_share_detail(specific_code)
                if a_share_detail:
                    a_share_context = a_share_detail + "\n\n" + a_share_context
            # A股查询也加载财报知识库
            self.memory.build_knowledge_base(current_sim_date=today)
            financial_knowledge = self.memory.query(user_query, k=3)
        else:
            # 美股/通用查询：加载财报知识库
            self.memory.build_knowledge_base(current_sim_date=today)
            financial_knowledge = self.memory.query(user_query, k=5)

        # === 4.5 联网搜索：获取实时股票资讯 ===
        web_context = ""
        try:
            if specific_code:
                web_context = search_web_finance(f"A股 {specific_code} 最新消息 2026", limit=3)
            elif us_symbols:
                for sym in us_symbols[:2]:
                    news = search_stock_news(sym, sym)
                    if news:
                        web_context += news + "\n"
            elif any(kw in user_query for kw in ['买', '卖', '推荐', '行情', '分析', '市场',
                                                   '涨', '跌', '热点', '新闻', '消息',
                                                   '今天', '最近', '现在', '投资', '机会']):
                web_context = search_web_finance(
                    f"A股 市场热点 今日行情 2026年5月", limit=5
                )
        except Exception:
            pass

        # 5. 构造 Prompt
        data_section = ""

        # 历史日线行情（注意：可能不是今日数据）
        if daily_price_context:
            data_section += f"\n【参考事实 - 历史日线行情 (DailyPrice，注意：数据日期可能不是今天)】:\n{daily_price_context}\n"
        else:
            data_section += "\n【参考事实 - 历史日线行情】: ⚠️ DailyPrice 表中暂无数据。\n"

        # A 股实时行情（今日最新，优先使用）
        if a_share_context and "暂无行情数据" not in a_share_context:
            data_section += f"\n【参考事实 - A股今日实时行情（最新，优先参考）】:\n{a_share_context}\n"

        if financial_knowledge and "暂无" not in financial_knowledge:
            data_section += f"\n【参考事实 - 数据库财务详情】:\n{financial_knowledge}\n"
        else:
            data_section += "\n【参考事实 - 数据库财务详情】: 暂无财务数据。\n"

        # 网络实时资讯
        if web_context:
            data_section += f"\n【参考事实 - 网络实时资讯（今日最新）】:\n{web_context}\n"

        system_prompt = f"""你是一位名为 'Ada-Finance' 的 AI 投资顾问，精通美股和A股市场。

【当前时间背景】:
今天是 {today}（与你的本地计算机时间同步）。

⚠️ 数据优先规则（重要）：
- 如果【A股今日实时行情】中有数据，它反映的是今天 {today} 的真实市场行情，必须作为主要分析依据。
- 【历史日线行情】是 DailyPrice 表中的历史记录，其日期可能早于今天，仅作背景参考。
- 如果提供了【网络实时资讯】，应结合最新新闻、政策、事件进行分析，引用其中的关键信息。
- 在回答时，优先引用今日实时行情的价格和涨跌幅，不要因为历史日线数据较旧就说"无法获取今日行情"。
{data_section}
【参考事实 - 用户当前持仓】:
{holdings_context}

【回答准则】:
1. 必须引用参考事实中的具体数字来回答（如价格、涨跌幅、成交量）。
2. A股分析时，结合涨跌幅和成交量判断市场情绪。
3. 若持有股票涨跌幅超过±5%，提醒用户注意风险。
4. 若数据来源显示"暂无数据"，如实告知用户并建议导入数据。
5. 语气专业且果断，禁止编造未来数据或预测具体涨跌幅度。"""

        try:
            # 6. 调用 DeepSeek API
            return self._call_deepseek(system_prompt, user_query)
        except Exception as e:
            print(f"--- [Brain] DeepSeek API 调用失败: {e} ---")
            return f"⚠️ AI 服务暂时不可用: {str(e)}"