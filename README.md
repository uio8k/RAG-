# StockX Pro: 金融交易仿真系统及RAG投顾助手

[![Python Version](https://img.shields.io/badge/python-3.14.2-blue)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Django%205.0-green)](https://www.djangoproject.com/)


## 🚀 项目简介
**StockX Pro** 是一个专为金融工程和算法交易设计的专业级股票模拟交易系统。该系统集成了深度的市场模拟逻辑、实时资产管理的 AI 投顾智能体。

本项目旨在探索大型语言模型（LLM）与复杂金融优化算法在模拟实盘环境中的深度融合。

---

## 🛠️ 核心功能展示

### 1. 交易终端概览
系统提供沉浸式的交易体验，包括实时资产走势图、多维度盈亏分析以及动态市场探索。
[首页展示]
<img width="2513" height="1385" alt="首页" src="https://github.com/user-attachments/assets/2ebf508a-4b84-4c08-ba4c-22873976dcb4" />


### 2. 深度资产管理
支持对个人持仓的穿透式管理，实时计算各项风险指标。
[持仓概览]
<img width="2440" height="1245" alt="持仓" src="https://github.com/user-attachments/assets/97433614-7ebb-4b6d-882b-97e0bf61ba79" />


### 3. 历史成交追踪
完整记录每一笔交易指令，支持对过往决策的复盘与归因分析。
[交易记录]
<img width="2559" height="1396" alt="交易记录" src="https://github.com/user-attachments/assets/c4711b70-a3f3-462a-8748-f48d350da146" />


---

## 🧠 智能体系统：Fin-Insight-Expert Pro
系统内嵌了基于 RAG（检索增强生成）技术的智能体，能够直接调取用户私有财务数据并提供专业分析。

* **多轮交互诊断**：实时分析当前系统日期下的市场行情。
* **私有数据联通**：智能体可直接读取 `Simulation_Holding` 等数据库表，实现精准的持仓建议。

[智能体交互1]
<img width="570" height="676" alt="智能体1" src="https://github.com/user-attachments/assets/40ea1c6e-827a-4522-a2ed-5acd12c67d5b" />

[智能体交互2]
<img width="580" height="782" alt="智能体2" src="https://github.com/user-attachments/assets/0671babc-869f-4cbc-9233-79c8d056233e" />

json文件
[agent.json](https://github.com/user-attachments/files/27721724/agent.json)



---

💻 核心技术：数据库驱动的金融仿真引擎
本项目是数据库系统课程的实践成果，核心在于构建了一个高性能、高一致性的模拟交易底层架构。系统通过 Django ORM 与后端数据库（MySQL/PostgreSQL）深度集成，实现了复杂的金融业务逻辑。

📊 数据库架构亮点
关系模型设计：严格遵循第三范式（3NF），涵盖了用户（User）、公司（Company）、持仓（Holding）、交易订单（Order）以及账户表现历史（Performance）等核心实体。

事务一致性保证：在执行买入/卖出操作时，通过数据库事务确保“扣除余额”与“增加持仓”的原子性，防止在高并发模拟下的数据不一致。

高效索引优化：针对股票代码（Symbol）和时间戳（Timestamp）建立了复合索引，大幅提升了 K 线展示及历史账单的查询效率。

🤖 AI 智能体：基于私有数据的文本转 SQL (Text-to-SQL) 增强
系统内嵌的 Fin-Insight-Expert 并非通用的聊天机器人，而是一个数据感知型智能体：

私有语义检索：智能体能够理解用户的自然语言指令，并将其映射为对数据库 Simulation_Holding 和 Financials 表的查询逻辑。

自动化报表生成：用户只需提问“我的账户盈亏如何？”，智能体即可实时聚合数据库中的成交记录并计算出精准的百分比结果。

🧪 实验验证（数据集说明）
为了模拟真实的金融数据环境，本项目导入了多组经过清洗的财务指标数据，并针对不同的数据规模（Data Ratio）进行了查询性能测试，确保系统在海量历史数据下仍能秒级响应。

---

## 💻 技术栈
* **后端**: Django (Python 3.14.2)
* **前端**: Bootstrap 5 + Chart.js (响应式金融看板)
* **数据库**: MySQL / PostgreSQL (支持复杂事务处理)
* **AI/算法**: PyTorch + AdaRHD-S 优化器
* **开发环境**: WSL (Windows Subsystem for Linux) + VS Code

---

### 📦 安装与运行指南

# 1. 克隆仓库并进入项目目录
```bash
git clone https://github.com/JQ-ux/DataBase_Project
cd DataBase_Project
```

# 2. 创建并激活虚拟环境 (Windows)
```bash
python -m venv venv
.\venv\Scripts\activate
```

# 3. 安装项目依赖与初始化数据库
```bash
pip install -r requirements.txt
python manage.py migrate
```

# 4. 启动 Django 开发服务器
```bash
python manage.py runserver
```

# 5. 访问系统：请在浏览器输入 http://127.0.0.1:8000
