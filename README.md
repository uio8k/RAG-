# StockX Pro — RAG 金融 AI 投顾助手

[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.0-green)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/bootstrap-5.3-purple)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

> 基于 [Nexent](https://github.com/ModelEngine-Group/nexent) 改造的 RAG 金融 AI 投顾，支持私有数据检索与自然语言交互。

---

## 🚀 项目简介

**StockX Pro** 是一个基于检索增强生成（RAG）技术的金融 AI 投顾助手。项目基于 Nexent 开源框架改造，将通用 AI Agent 平台转型为聚焦 **金融数据分析** 与 **智能投顾问答** 的垂直领域应用。

核心亮点：
- 🤖 **RAG 私有数据检索** — FAISS 向量库 + sentence-transformers，AI 可直接查询你的财务数据库
- 💬 **自然语言交互** — 用中文提问持仓分析、风险评估、市场行情，Markdown 富文本回复
- 🎨 **现代 SaaS 风格 UI** — 借鉴 Heidi Health 设计语言，暖色调专业仪表盘

---

## 🖥️ 功能展示

### AI 投顾对话
基于 RAG 技术，智能体可直接读取数据库中的股票行情、财务报表等私有数据，回答持仓分析、风险评估、投资建议等问题，支持 Markdown 渲染（表格、代码块、列表等）。

### 市场数据浏览
内置 A 股市场行情浏览，支持按行业筛选和关键词搜索，可查看股票详情和历史财务指标。

### 游客模式
无需注册即可体验 AI 投顾功能，一键进入系统。

---

## 🛠️ 核心功能

### 1. RAG 智能投顾（Fin-Insight-Expert Pro）
- **FAISS 向量检索** — 将用户私有财务数据向量化，支持语义级相似度搜索
- **DeepSeek 大模型** — 调用 DeepSeek API 进行深度金融分析
- **Text-to-SQL** — 自然语言自动转换为数据库查询，精准获取数据
- **多轮对话记忆** — 保持对话上下文，支持连续追问与深度分析
- **Markdown 回复** — 表格、代码、列表等富文本格式输出

### 2. 市场数据查询
- 东方财富 A 股实时行情
- 行业分类筛选
- 历史价格与财务指标可视化（Chart.js）

### 3. 用户系统
- 注册 / 登录 / 游客模式
- 个性化数据隔离

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│                    前端 (Browser)                 │
│  Bootstrap 5 + Chart.js + Marked.js              │
│  Heidi Health 设计风格 · 暖金色调                 │
└─────────────────┬───────────────────────────────┘
                  │ HTTP
┌─────────────────▼───────────────────────────────┐
│                Django 6.0 (Python)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Views   │ │  Models  │ │  AI Brain (RAG)   │ │
│  │  页面渲染  │ │  数据模型  │ │  FAISS + LLM     │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              数据层                               │
│  SQLite / MySQL  ·  FAISS 向量索引  ·  东方财富API │
│             ·  DeepSeek API                      │
└─────────────────────────────────────────────────┘
```

### AI 数据检索层级

```
用户提问
    │
    ▼
┌─────────────────┐
│ 1. 持仓数据检索   │  ← 私有数据库
├─────────────────┤
│ 2. 历史行情查询   │  ← DailyPrice 表
├─────────────────┤
│ 3. 实时行情      │  ← 实时缓存
├─────────────────┤
│ 4. 网络资讯      │  ← 搜索引擎
└─────────────────┘
    │
    ▼
DeepSeek LLM 综合分析 → Markdown 回复
```

---

## 💻 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | Django 6.0.3 |
| **前端** | Bootstrap 5.3 + Chart.js 4.4 + Marked.js |
| **数据库** | SQLite（开发）/ MySQL（生产） |
| **AI/ML** | FAISS + sentence-transformers + DeepSeek API |
| **数据源** | 东方财富 A 股行情 |
| **字体** | Inter + Georgia（Google Fonts） |
| **Python 版本** | 3.13 |

---

## 📦 安装与运行

### 前置条件
- Python 3.13+
- Conda（推荐）或 venv

### 快速开始

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd DataBase_Project

# 2. 创建并激活环境
conda create -n Py313 python=3.13 -y
conda activate Py313

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python manage.py migrate

# 5. 导入 A 股数据（可选，但建议执行）
python ./Data/spider_pro.py        # 爬取最新行情
python import_csv.py                # 导入 CSV 数据
python manage.py populate_a_stocks --refresh  # 填充 A 股列表

# 6. 配置环境变量
# 创建 .env 文件，填入 DeepSeek API Key:
# DEEPSEEK_API_KEY=your_key_here

# 7. 启动服务器
python manage.py runserver

# 8. 访问系统
# 浏览器打开 http://127.0.0.1:8000
```

---

## 🎮 使用指南

### 游客模式
点击导航栏「游客模式」或登录页「游客模式浏览」即可免注册体验。

### AI 对话
在首页底部 AI 对话区域直接提问，例如：
- "帮我分析一下当前市场整体走势"
- "最近一周哪些板块表现最好？"
- "000001 这只股票的财务情况如何？"
- "推荐几只低市盈率且营收增长稳定的股票"

### 浏览市场数据
在「市场行情」区域可按行业筛选、搜索股票，点击「详情」查看完整财务指标。

---

## 🎨 设计系统

本项目 UI 设计灵感来源于 [Heidi Health](https://www.heidihealth.com/en-gb) 登陆页，通过 Firecrawl 提取设计令牌后重新应用到金融场景：

| 设计元素 | 取值 |
|---------|------|
| 主色调 | `#FBF582` 暖金 |
| 辅色 | `#755760` 紫褐 |
| 背景 | `#FCFAF8` 暖白 |
| 标题字体 | Georgia（衬线） |
| 正文字体 | Inter（无衬线） |
| 按钮圆角 | 12px |

完整设计文档见 [`DESIGN.md`](DESIGN.md)。

---

## 📁 项目结构

```
DataBase_Project/
├── capstone/                  # Django 项目配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── stock/                     # 主应用
│   ├── models.py              # 13 张数据表
│   ├── views.py               # 业务逻辑 + API
│   ├── urls.py                # 路由配置
│   ├── templates/stock/       # Django 模板
│   │   ├── base.html          # 基础布局
│   │   ├── index.html         # 首页（AI 对话 + 行情浏览）
│   │   ├── detail.html        # 股票详情
│   │   ├── transactions.html  # 历史记录
│   │   ├── login.html         # 登录页
│   │   ├── register.html      # 注册页
│   │   └── ...
│   └── management/commands/   # 管理命令
├── agents/                    # AI 智能体
│   ├── brain.py               # RAG 推理引擎
│   ├── memory.py              # 对话记忆
│   └── tools.py               # 工具函数
├── services/                  # 外部服务
│   └── eastmoney_service.py   # 东方财富 API
├── static/                    # 静态资源
│   ├── css/style.css          # Heidi 风格样式
│   └── js/                    # Chart.js 图表 + 搜索交互
├── fonts/                     # 中文字体
├── Data/                      # 数据采集脚本
│   └── spider_pro.py
├── DESIGN.md                  # 设计系统文档
├── requirements.txt
├── manage.py
└── README.md
```

---

## 🙏 致谢与许可

### 原始项目
本项目基于 [Nexent](https://github.com/ModelEngine-Group/nexent) by **Huawei Technologies Co., Ltd.** 改造而来，原始项目采用 MIT 许可证。

### 设计灵感
UI 设计灵感来源于 [Heidi Health](https://www.heidihealth.com/en-gb)，通过 [Firecrawl](https://www.firecrawl.dev) 提取设计令牌。

### AI 模型
智能投顾由 [DeepSeek](https://www.deepseek.com/) 大语言模型驱动。

### 开源协议
本项目继承原始项目的 [MIT License](LICENSE)。

```
MIT License

Copyright (c) 2025 Huawei Technologies Co., Ltd. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 🔗 相关链接

- 原始项目：[Nexent](https://github.com/ModelEngine-Group/nexent)
- 设计参考：[Heidi Health](https://www.heidihealth.com/en-gb)
- 设计工具：[Firecrawl](https://www.firecrawl.dev)
