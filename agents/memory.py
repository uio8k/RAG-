import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from django.apps import apps
import os

class VectorMemory:
    # === 类级别单例：嵌入模型只加载一次，所有实例共享 ===
    _encoder = None

    def __init__(self):
        # 模型只加载一次（类级别共享，优先使用本地模型）
        if VectorMemory._encoder is None:
            try:
                from config import memory_config
                model_path = memory_config.get_embedding_model()
                print(f"--- [Memory] 首次加载嵌入模型 (仅此一次): {model_path} ---")
                VectorMemory._encoder = SentenceTransformer(model_path)
            except Exception as e:
                print(f"--- [Memory] ⚠ 嵌入模型加载失败: {e} ---")
                print("--- [Memory] 将使用关键词匹配模式（功能降级） ---")
                VectorMemory._encoder = None
        self.encoder = VectorMemory._encoder

        # FAISS 索引 (维度 384)
        self.index = faiss.IndexFlatL2(384)

        # 存储原始文本列表，用于检索后还原
        self.metadata = []

        # === 缓存追踪：避免每次 think() 都重建 ===
        self._last_sim_date = None   # 上次构建时的仿真日期
        self._last_db_count = 0      # 上次构建时的数据库记录总数

    def _should_rebuild(self, current_sim_date):
        """判断是否需要重建知识库（仿真日期变了 或 数据库新增了记录）"""
        if self.index.ntotal == 0:
            return True  # 索引为空，必须重建
        try:
            Financials = apps.get_model('stock', 'Financials')
            current_count = Financials.objects.count()
        except LookupError:
            return True
        if current_sim_date != self._last_sim_date:
            return True  # 仿真日期变了
        if current_count != self._last_db_count:
            return True  # 数据库记录数变了（有新财报导入）
        return False

    def build_knowledge_base(self, current_sim_date=None, force=False):
        """
        核心功能：根据时间限制构建知识库
        current_sim_date: 用户模拟交易盘当前的仿真日期。
        如果提供，则只加载报告日期 <= 该日期的财务数据。
        force: 强制重建，忽略缓存。
        """
        # === 智能跳过：数据没变就不重建 ===
        if not force and not self._should_rebuild(current_sim_date):
            print(f"--- [Memory] 知识库未变化，跳过重建 (日期={current_sim_date}, 记录数={self._last_db_count}) ---")
            return

        try:
            Financials = apps.get_model('stock', 'Financials')
            # 基础查询：关联股票代码表
            queryset = Financials.objects.select_related('symbol')

            # 【关键创新：时间围栏】
            # 确保 Agent 不会拥有“上帝视角”看到未来的财报
            if current_sim_date:
                queryset = queryset.filter(report_date__lte=current_sim_date)
                print(f"--- [Memory] 正在应用时间过滤：只读取 {current_sim_date} 以前的财报 ---")
            else:
                print("--- [Memory] 未检测到仿真日期，将读取全量历史数据 (仅建议测试使用) ---")

            records = queryset.all()
        except LookupError:
            print("--- [Error] 找不到 stock.Financials 模型，请确认 app 名称是否为 stock ---")
            return

        # 每次构建前重置索引和元数据，防止数据残留或重复
        documents = []
        self.metadata = []
        self.index = faiss.IndexFlatL2(384)

        for r in records:
            # 将结构化财务指标转化为自然语言描述
            desc = (
                f"股票代码: {r.symbol.symbol}, 公司名称: {r.symbol.full_name}. "
                f"报告日期: {r.report_date}. "
                f"总营收: {r.total_revenue}, 净利润: {r.net_income}, "
                f"资产负债率: {r.debt_asset_ratio}%, 流动比率: {r.current_ratio}. "
                f"每股收益(EPS): {r.basic_eps}."
            )
            documents.append(desc)
            self.metadata.append(desc)

        if documents:
            if self.encoder is not None:
                print(f"--- [Memory] 正在编码 {len(documents)} 条财务记录为向量... ---")
                embeddings = self.encoder.encode(documents)
                self.index.add(np.array(embeddings).astype('float32'))
                print(f"--- [Memory] 知识库构建完毕，共加载 {len(documents)} 条符合时间条件的记录 ---")
            else:
                print(f"--- [Memory] 嵌入模型不可用，跳过向量化 ({len(documents)} 条记录供关键词匹配) ---")
        else:
            print("--- [Warning] 该时间点之前没有任何财务数据记录 ---")

        # === 更新缓存标记 ===
        self._last_sim_date = current_sim_date
        try:
            Financials = apps.get_model('stock', 'Financials')
            self._last_db_count = Financials.objects.count()
        except LookupError:
            self._last_db_count = 0

    def query(self, user_query, k=5):
        """
        根据用户问题执行向量检索
        k=5 增加了检索深度，能有效区分 AAPL 和 AAL 等缩写相近的股票
        """
        if self.index.ntotal == 0:
            return "本地知识库中暂无符合当前时间条件的财务信息。"

        # 有编码器用向量检索，否则降级为关键词匹配
        if self.encoder is not None:
            query_vec = self.encoder.encode([user_query])
            D, I = self.index.search(np.array(query_vec).astype('float32'), k)
            results = [self.metadata[i] for i in I[0] if i != -1]
        else:
            keywords = user_query.lower().split()
            scored = []
            for i, doc in enumerate(self.metadata):
                score = sum(1 for kw in keywords if kw in doc.lower())
                if score > 0:
                    scored.append((score, i))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [self.metadata[i] for _, i in scored[:k]]

        return "\n".join(results) if results else "本地知识库中暂无符合当前时间条件的财务信息。"