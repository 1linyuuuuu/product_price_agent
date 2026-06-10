# CLAUDE.md — 商品价格智能分析助手

## 项目概述

多平台商品价格智能分析助手。用户输入商品查询（如"华为Mate 70 Pro 256G vs 512G"），系统通过三个 LangGraph Agent 协作，搜索京东/淘宝/拼多多/闲鱼/转转等平台价格，生成比价表格、趋势分析和购买建议。支持单一商品比价和多商品集合（装机配置等）分析。

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 框架 | **LangChain + LangGraph**（不用 hello-agents） |
| LLM | DeepSeek deepseek-chat（OpenAI 兼容接口，可热切换千问） |
| 后端 | FastAPI + SSE 流式推送 |
| 前端 | Vue 3 + TypeScript + Vite + ECharts |
| 搜索 | Tavily（付费）→ SerpAPI（付费）→ **DuckDuckGo（免费永久兜底）**，三路并行 |
| 数据库 | SQLite（价格历史积累） |
| 环境 | Conda: `price_agent`，Python 3.10 |

## 目录结构

```
product_price_agent/
├── CLAUDE.md
├── backend/
│   ├── pyproject.toml
│   ├── .env                          # API Key（不入 git）
│   └── src/
│       ├── main.py                   # FastAPI 入口
│       ├── config.py                 # Settings（读 .env）
│       ├── models.py                 # Pydantic 数据模型
│       ├── agents/                   # 三 Agent 节点
│       │   ├── product_parser.py     # Agent 1: 商品解析
│       │   ├── price_researcher.py   # Agent 2: 价格调研（含历史锚点搜索）
│       │   └── comparison_advisor.py # Agent 3: 对比推荐 + trend_data
│       ├── tools/                    # 搜索工具
│       │   ├── hybrid_search.py      # 混合搜索编排（Tavily + SerpAPI + DDG 三路并行）
│       │   ├── search_price.py       # 当前价格搜索（调用 hybrid_search）
│       │   ├── serpapi_search.py     # SerpAPI Google 搜索
│       │   ├── duckduckgo_search.py  # DuckDuckGo 免费搜索（urllib + regex，零依赖）
│       │   ├── extract_price.py      # LLM 价格结构化提取
│       │   └── history_lookup.py     # 本地 SQLite 历史查询
│       ├── graph/
│       │   ├── state.py              # AnalysisState TypedDict
│       │   └── workflow.py           # StateGraph 构建
│       ├── services/                 # 业务逻辑
│       ├── db/                       # SQLite 操作
│       └── prompts/                  # Prompt 模板
├── frontend/
│   ├── vite.config.ts                # Vite 配置（含 /api 代理到 127.0.0.1:8000）
│   └── src/
│       ├── App.vue                   # 主布局 + 空结果状态
│       ├── components/
│       │   ├── SearchInput.vue       # 搜索输入框
│       │   ├── ProgressPanel.vue     # 进度条 + 步骤指示器 + 日志
│       │   ├── PriceTable.vue        # 比价汇总表（全新/二手分区，可折叠）
│       │   ├── TrendChart.vue        # ECharts 柱状图 + 折线图（数据不足自动隐藏）
│       │   ├── Recommendation.vue    # 比价报告 + 购买建议卡片（区块交替背景色）
│       │   └── ProductCard.vue       # 推荐商品卡片
│       └── composables/useAnalysis.ts # SSE hook（5分钟超时）
└── docs/（方案/流程/开发 文档）
```

## 启动命令

```bash
# 后端
conda activate price_agent
cd backend && python src/main.py
# → http://localhost:8000/docs

# 前端
cd frontend && npm run dev
# → http://localhost:5175

# 一键启动
start.bat
```

## 核心架构

三 Agent 流水线（LangGraph StateGraph）：

```
用户输入 → Agent 1(商品解析) → Agent 2(价格调研) → Agent 3(对比推荐) → 结果
              │                    │                    │
              ▼                    ▼                    ▼
         LLM 拆分型号         当前价格: 代码并行搜索    整合比价表+趋势+建议
         输出 variants         历史价格: 锚点拼凑搜索    Markdown 报告
         支持多商品集合         写入 SQLite 积累        ECharts 可视化数据
         (is_multi=true)       三搜索引擎并行兜底       (trend_data)
```

State 定义在 `graph/state.py`（TypedDict），图构建在 `graph/workflow.py`。Agent 节点函数签名统一为 `(AnalysisState) -> dict`（返回部分 state 更新）。

## 关键设计决策

- **搜索引擎三级降级**：`hybrid_search.py` 并行调用 Tavily → SerpAPI → DuckDuckGo，三路结果按 URL 去重合并。Tavily 额度耗尽后自动跳过（`_tavily_dead` 标记），SerpAPI 需要 API key，**DuckDuckGo 零依赖免费永久兜底**（直接请求 `html.duckduckgo.com/html/`，urllib + regex 解析，不需要任何外部包）
- **历史价格锚点拼凑**：不做单一价格追踪站搜索（大多数商品没有），改为三步策略：① 搜结构化历史数据（慢慢买/什么值得买价格曲线）→ ② 搜生命周期锚点（发售价/大促价/当前价，评测文章几乎都提）→ ③ 不足 3 个点用 LLM 锚点 prompt 二次宽松提取。每个 variant 并行执行，失败自动降级
- **历史折线图自动隐藏**：`TrendChart.vue` 中 `showPriceHistory` 计算属性——xAxis 日期数 < 3 或跨度 < 30 天或有效数据点 < 4 → 隐藏折线图，显示提示文案。柱状图始终展示当前比价数据
- **多商品集合**：Agent 1 识别 `is_multi=true` 后，每个子商品独立解析 variants + platforms。Agent 2 逐个搜索并存入 `sub_products[i].price_data`。Agent 3 逐一生成报告后**合并所有子商品 price_data/history_data 到顶层**，统一构建 trend_data 供前端渲染
- **PriceInfo 模型**：`is_secondhand` 字段区分全新/二手，二手专属字段（condition/repairs等）通过 `Optional` 区分
- **品类通用**：`extra_attrs: dict` 承载品类特有属性（显卡→挖矿史，手机→电池健康，家电→配件），不做电子品类假设
- **降级策略**：每个 Agent 节点内部 try/except，失败写入 `errors` 列表但不阻断流水线
- **SSE 事件协议**：connected → node_start → progress → node_complete → complete/error。emit_progress() 直接往 asyncio.Queue put_nowait，run_graph 从 stream_mode="updates" 推 node_complete
- **端口**：后端 8000，前端 5175。Vite 代理 target 用 `127.0.0.1` 而非 `localhost`（避免 Windows IPv4/IPv6 不匹配 ECONNREFUSED）
- **Agent 3 trend_data**：`_build_trend_data()` 生成 ECharts 可视化数据，包含两层图表。`platformComparison`：各平台价格柱状图（variant × 全新/二手分组，null 表示该平台无数据）。`priceHistory`：历史价格折线图（日期 X 轴，variant 为 series，同日期多源取均价，smooth + connectNulls 处理断点）。不足 3 个日期时整体隐藏
- **进度条**：`ProgressPanel.vue` 用 `computed + CSS transition: 1.2s` 驱动，`currentStep` 0→1→2→3 分别映射 5%/35%/65%/90%，CSS 缓动曲线做平滑过渡
- **报告区块着色**：`Recommendation.vue` 的 `sectionColorize()` 函数在 markdown 渲染后给每个 h2/h3 区块包裹 5 色交替背景（蓝/绿/橙/紫/青），h3 子标题略微缩进沿用当前色
- **NPE 防护**：所有 `:.0f` 格式化前用 `(value or 0)` 防止 None 值炸流
- **价格数据来源**：搜索引擎摘要 + LLM 提取，不直接爬取平台页面
- **LLM 可热切换**：改 `.env` 三行（MODEL_ID/API_KEY/BASE_URL）即可在千问/DeepSeek/OpenAI 间切换

## 当前进度

- ✅ Phase 1: 环境搭建（Conda + 依赖 + .env + DeepSeek 切换）
- ✅ Phase 2: 后端骨架（models/config/main/graph）
- ✅ Phase 3: 三 Agent 实现（商品解析 + 价格调研 + 对比推荐）+ trend_data 可视化数据
- ✅ Phase 4: SSE 细粒度流式推送（emit_progress 推送 node_start/progress 事件）
- ✅ Phase 5: 前端开发（6 组件 + ECharts + SSE hook + 空状态/错误处理）
- ✅ Phase 6: 联调测试 + 边界处理（NPE 修复、IPv4/IPv6 代理修复、多商品 price_data 合并、DDG 兜底、UI 文案客服化）

### 测试脚本

| 脚本 | 用途 | 消耗 |
|------|------|------|
| `test_agent1.py` | Agent 1 商品解析（4 条用例） | 仅 LLM |
| `test_agent2.py` | Agent 2 当前+历史价格搜索 | LLM + 搜索 API |
| `test_agent3.py` | Agent 3 报告生成（mock/真实双档） | 仅 LLM（mock 模式） |

## 代码规范

- Python 使用 Pydantic BaseModel 定义数据结构，TypedDict 定义 LangGraph state
- Agent 节点是纯函数，不持有状态，不直接修改 state（通过返回 dict 让 LangGraph 归约）
- Prompt 模板放在 `prompts/` 目录，与 Agent 逻辑分离
- 前端组件通过 `useAnalysis()` composable 共享 SSE 连接和全局状态
- `errors` 字段用 `Annotated[list, operator.add]` 归约，跨节点追加
- 价格格式化前统一用 `(value or 0)` 防 None，避免 `NoneType.__format__` 异常
