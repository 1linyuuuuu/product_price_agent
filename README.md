# 商品价格智能分析助手

多平台商品比价 Agent，输入商品查询自动搜索京东/淘宝/拼多多/闲鱼/转转等平台价格，生成比价表格、趋势分析和购买建议。

## 功能

- **智能商品解析** — 自然语言输入自动拆解为型号、配置、平台搜索任务
- **多平台比价** — 同时搜索京东、淘宝、拼多多（全新）和闲鱼、转转（二手）
- **价格趋势分析** — 历史价格锚点拼凑 + ECharts 柱状图/折线图可视化
- **购买建议** — LLM 生成比价报告 + 结构化推荐卡片，含入手时机和风险提示
- **多商品集合** — 支持装机配置等复合查询，逐一分析后汇总
- **SSE 流式推送** — 进度实时可见，解析 → 搜索 → 分析三阶段可感知

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 框架 | LangChain + LangGraph |
| LLM | DeepSeek（可热切换千问/OpenAI） |
| 后端 | FastAPI + SSE 流式推送 |
| 前端 | Vue 3 + TypeScript + Vite + ECharts |
| 搜索 | Tavily → SerpAPI → DuckDuckGo 三级降级 |
| 数据库 | SQLite（价格历史积累） |

## 架构

```
用户输入 → Agent 1(商品解析) → Agent 2(价格调研) → Agent 3(对比推荐) → 结果
              │                    │                    │
              ▼                    ▼                    ▼
         LLM 拆分型号         当前价格: 并行搜索    整合比价表+趋势+建议
         输出 variants         历史价格: 锚点拼凑    Markdown 报告
         支持多商品集合         写入 SQLite          ECharts 可视化
```

## 快速开始

### 环境要求

- Python 3.10+、Conda
- Node.js 18+

### 1. 后端

```bash
conda create -n price_agent python=3.10 -y
conda activate price_agent
cd backend
pip install -e .
cp .env.example .env   # 编辑 .env 填入 API Key
python src/main.py      # → http://localhost:8000/docs
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev             # → http://localhost:5175
```

### 3. 一键启动

双击 `start.bat`

## 配置

编辑 `backend/.env`：

```ini
# LLM（必填）
LLM_MODEL_ID=deepseek-chat
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.deepseek.com/v1

# 搜索（至少配一个）
TAVILY_API_KEY=tvly-xxx      # 推荐，付费
SERPAPI_API_KEY=xxx          # 可选，付费
                              # DuckDuckGo 免费，无需 Key，自动兜底

# 可选
MAX_SEARCH_RESULTS=5
HOST=0.0.0.0
PORT=8000
```

LLM 支持热切换：改 `LLM_MODEL_ID` + `LLM_API_KEY` + `LLM_BASE_URL` 即可换千问/OpenAI。

## 局限

### 1. 无法获取电商平台 API

京东、淘宝、拼多多等平台的商品搜索和价格 API 均不对第三方开放。当前价格数据完全依赖搜索引擎（Tavily/SerpAPI/DuckDuckGo）返回的网页摘要片段，再由 LLM 从中提取价格信息。这导致：

- **价格覆盖不完整** — 搜索引擎不一定收录每个商品的最新 listing
- **时效性不可控** — 搜索引擎索引更新有延迟，价格可能不是当日实价
- **二手市场数据稀疏** — 闲鱼/转转的 listing 在搜索引擎中覆盖率低，很多条目无法获取精确价格

### 2. 反爬机制无法直接定位店铺页面

主流电商平台均有严格的爬虫检测（验证码、JS 挑战、IP 风控等），本系统**不直接爬取任何平台页面**。所有价格均来自搜索引擎的公开摘要，这意味着：

- **无法验证价格真实性** — 摘要中的价格可能是促销价、划线价或已过期价格
- **"去购买"链接为搜索页** — 推荐卡片中的购买链接指向的是平台搜索结果页而非具体商品页，因为搜索引擎摘要中通常不包含真实的商品直链
- **店铺信息可能缺失** — 很多搜索结果的摘要不含店铺名称，推荐卡片中的店铺名由 LLM 尝试推断

## 许可证

MIT
