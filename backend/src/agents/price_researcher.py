import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from ..graph.state import AnalysisState
from ..tools.search_price import search_price
from ..tools.extract_price import extract_price
from ..tools.history_lookup import history_lookup
from ..db.repository import insert_price
from ..utils import extract_json, emit_progress, get_llm

llm = get_llm(0.1)


def _search_single_platform(
    search_query: str,
    platform: str,
    is_secondhand: bool,
) -> list[dict]:
    """搜索单个平台并提取价格，返回 PriceInfo 列表"""
    raw = search_price.invoke({
        "query": search_query,
        "platform": platform,
        "is_secondhand": is_secondhand,
    })

    extracted = extract_price.invoke({
        "search_results_json": raw,
        "platform": platform,
        "is_secondhand": is_secondhand,
    })

    try:
        return json.loads(extracted)
    except json.JSONDecodeError:
        return []


HISTORY_EXTRACT_PROMPT = """你是一个价格历史数据提取专家。从搜索结果摘要中提取价格+时间数据。

## 数据可信度层级（高→低）
1. 价格追踪站（慢慢买/比价网）— 日期-价格对照表，最可靠
2. 导购/评测/新闻 — "X月最低价XX""双11降至XX""发布价XX""现已降致XX"
3. 常识推断 — 无搜索结果时，根据典型电子产品贬值规律估算（标记 source="LLM估算"）

## 提取规则
- 至少精确到月，只有年份填 01-01
- 价格去除非数字字符，转为 float
- 每条必须同时有日期和价格，缺一不可
- 同一日期多个价格时各单独列出
- source 标注来源网站名，LLM估算标 "LLM估算"

## 常见格式
- "2024年11月发布 6999元" -> {"date": "2024-11-15", "price": 6999.0, "source": "IT之家"}
- "双11最低5999" -> {"date": "2025-11-11", "price": 5999.0, "source": "什么值得买"}
- "首发价7999，半年后降至6499" -> [{"date": "...", "price": 7999}, {"date": "...", "price": 6499}]
- "目前京东6599元" -> {"date": "CURRENT_MONTH", "price": 6599.0, "source": "京东"}  （用当前月份）

## 输出格式（纯 JSON 数组）
[{"date": "2025-01-15", "price": 6999.0, "source": "什么值得买"}]"""


PRICE_ANCHOR_PROMPT = """你是一个商品价格分析专家。根据以下搜索结果，提取该商品在生命周期中的关键价格锚点。

## 需要寻找的锚点（按优先级）
1. **发售价/上市价** — 该商品刚发布时的官方定价（通常出现在评测/新闻中）
2. **当前市场价** — 当前主流平台的价格水平
3. **大促低价** — 618/双11/年货节期间的最低成交价（如有）

## 提取规则
- 对每个锚点，推断大致日期（至少到月）和价格
- 如果某个锚点搜索不到，不要编造，跳过
- 如果搜索结果很少，可以根据商品品类常识和当前价格反推（来源标"LLM估算"）

## 输出格式（纯 JSON 数组）
[
  {"date": "2024-09-15", "price": 7999.0, "source": "发售价-中关村在线"},
  {"date": "2025-06-01", "price": 6599.0, "source": "当前价-京东"},
  {"date": "2024-11-11", "price": 6899.0, "source": "双11-什么值得买"}
]"""


def _search_history_for_variant(search_query: str, product_name: str) -> list[dict]:
    """搜索单个 variant 的历史价格 — 锚点拼凑策略

    策略：不依赖单一的价格追踪站（大多数商品没有），而是从多个可靠锚点拼出趋势线：

    第一步：搜索结构化历史数据（慢慢买/比价网/什么值得买价格曲线）
    第二步：搜索生命周期锚点（发售价/大促价/当前价）— 这些几乎所有商品都有文章提及
    第三步：如果仍不足 3 个点，用 LLM 常识按品类折旧规律估算（标记为"LLM估算"）
    """
    logger.info(f"  [历史搜索] {search_query}")
    try:
        from ..tools.hybrid_search import hybrid_search

        all_snippets: list[str] = []
        seen_urls: set[str] = set()

        # — 第一步：搜索结构化历史价格 —
        phase1_queries = [
            f"{product_name} {search_query} 慢慢买 价格走势 历史最低 价格曲线",
            f"{search_query} site:smzdm.com 历史低价 降价时间线",
        ]
        for tq in phase1_queries:
            try:
                raw = hybrid_search(query=tq, max_results=3)
                for r in json.loads(raw).get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append(f"[来源:{r.get('source','web')}] [{r.get('title','')}] {r.get('content','')}")
            except Exception:
                continue

        # — 第二步：搜索生命周期锚点 —
        phase2_queries = [
            f"{product_name} {search_query} 发售价 上市价格 首发价 发布价格",
            f"{product_name} {search_query} 618 双11 大促 最低价 降价 目前价格",
            f"{product_name} {search_query} 当前价格 京东 淘宝 多少钱",
        ]
        for tq in phase2_queries:
            try:
                raw = hybrid_search(query=tq, max_results=3)
                for r in json.loads(raw).get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_snippets.append(f"[来源:{r.get('source','web')}] [{r.get('title','')}] {r.get('content','')}")
            except Exception:
                continue

        if not all_snippets:
            logger.info(f"  [历史搜索] {search_query} -> 无任何搜索结果")
            return []

        combined = "\n---\n".join(all_snippets[:15])
        logger.info(f"  [历史搜索] {search_query} -> {len(all_snippets)} 条摘要")

        # 先用历史提取 prompt 尝试
        response = llm.invoke([
            SystemMessage(content=HISTORY_EXTRACT_PROMPT),
            HumanMessage(content=combined),
        ])

        extracted = extract_json(response.content, expect_list=True)
        logger.info(f"  [历史搜索] {search_query} -> 提取到 {len(extracted)} 个点")

        # — 第三步：不足 3 个点时，用锚点 prompt 二次提取（更宽松）—
        if len(extracted) < 3:
            logger.info(f"  [历史搜索] {search_query} 数据点不足(<3)，尝试锚点二次提取...")
            try:
                response2 = llm.invoke([
                    SystemMessage(content=PRICE_ANCHOR_PROMPT),
                    HumanMessage(content=combined),
                ])
                anchors = extract_json(response2.content, expect_list=True)
                # 合并去重（按日期）
                existing_dates = {e.get("date", "")[:7] for e in extracted}
                for a in anchors:
                    if a.get("date", "")[:7] not in existing_dates and a.get("price", 0) > 0:
                        extracted.append(a)
                        existing_dates.add(a.get("date", "")[:7])
                logger.info(f"  [历史搜索] {search_query} -> 二次提取后共 {len(extracted)} 个点")
            except Exception:
                pass

        return extracted

    except Exception as e:
        logger.warning(f"  [历史搜索] {search_query} 失败: {e}")
        return []


def _search_one(variant: dict, platform: str, is_secondhand: bool, all_prices: list[dict]):
    """搜索单个平台并追加结果，异常时写入哨兵条目"""
    try:
        prices = _search_single_platform(variant["search_query"], platform, is_secondhand)
        all_prices.extend(prices)
        logger.info(f"  [{variant['spec']}] {platform} -> {len(prices)} 条价格")
    except Exception as e:
        logger.warning(f"  [{variant['spec']}] {platform} 搜索异常: {e}")
        all_prices.append({
            "platform": platform,
            "shop_name": "搜索失败",
            "price": 0.0,
            "is_secondhand": is_secondhand,
            "promotion": str(e),
        })


def _search_variant(
    variant: dict,
    platforms_new: list[str],
    platforms_used: list[str],
) -> tuple[str, list[dict]]:
    """对单个 variant 搜索所有平台，返回 (spec, price_list)"""
    all_prices: list[dict] = []

    for p in platforms_new:
        _search_one(variant, p, False, all_prices)
    for p in platforms_used:
        _search_one(variant, p, True, all_prices)

    return variant["spec"], all_prices


def research_price_node(state: AnalysisState, config: RunnableConfig = None) -> dict:
    """Agent 2: 价格调研 — 搜索当前价格 + 历史价格，并存储历史"""
    is_multi = state.get("is_multi", False)
    sub_products: list[dict] = state.get("sub_products", [])

    # --- 多商品集合路径：逐个处理 ---
    if is_multi and sub_products:
        emit_progress("research_price", config, "node_start",
                    f"开始多商品价格调研，共 {len(sub_products)} 个子商品")
        all_errors: list[str] = []
        for sp in sub_products:
            sp_name = sp.get("product_name", "")
            sp_variants = sp.get("variants", [])
            sp_new = sp.get("platforms_new", [])
            sp_used = sp.get("platforms_used", [])
            if not sp_variants:
                continue

            emit_progress("research_price", config, "progress", f"正在搜索 {sp_name}...")

            # 搜索当前价格
            sp_price_data: dict[str, list[dict]] = {}
            try:
                for v in sp_variants:
                    spec, prices = _search_variant(v, sp_new, sp_used)
                    sp_price_data[spec] = prices
                    emit_progress("research_price", config, "progress",
                                f"  {sp_name} {spec}: {len(prices)} 条价格")
            except Exception as e:
                all_errors.append(f"{sp_name} 搜索失败: {e}")

            sp["price_data"] = sp_price_data

            # 写入 SQLite
            spec_to_query = {v["spec"]: v["search_query"] for v in sp_variants}
            for spec, prices in sp_price_data.items():
                keyword = spec_to_query.get(spec, spec)
                for p in prices:
                    if p.get("price", 0) > 0:
                        try:
                            insert_price(
                                product_keyword=keyword,
                                platform=p.get("platform", ""),
                                price=p["price"],
                                original_price=p.get("original_price", 0.0),
                                source_url=p.get("source_url", ""),
                                is_secondhand=p.get("is_secondhand", False),
                                condition=p.get("condition", ""),
                            )
                        except Exception:
                            pass

            # 搜索历史价格
            sp_history: dict[str, list[dict]] = {}
            for v in sp_variants:
                try:
                    hp = _search_history_for_variant(v["search_query"], sp_name)
                    sp_history[v["spec"]] = hp
                except Exception:
                    sp_history[v["spec"]] = []

            # 合并本地历史
            for v in sp_variants:
                try:
                    records = history_lookup.invoke({
                        "product_keyword": v["search_query"],
                        "days": 90,
                    })
                    local = json.loads(records) if isinstance(records, str) else records
                    external = sp_history.get(v["spec"], [])
                    merged = []
                    for r in local:
                        merged.append({
                            "date": r.get("fetched_at", "")[:10],
                            "price": r.get("price", 0),
                            "source": f"{r.get('platform', '')} 本地记录",
                        })
                    for r in external:
                        merged.append({
                            "date": r.get("date", "")[:10],
                            "price": r.get("price", 0),
                            "source": f"{r.get('source', '外部参考')}",
                        })
                    sp_history[v["spec"]] = merged
                except Exception:
                    pass

            sp["history_data"] = sp_history

        emit_progress("research_price", config, "progress",
                    f"多商品搜索完成: {len(sub_products)} 个子商品")

        return {
            "sub_products": sub_products,
            "errors": all_errors,
        }

    # --- 单一商品路径（原逻辑）---
    variants: list[dict] = state.get("variants", [])
    platforms_new: list[str] = state.get("platforms_new", [])
    platforms_used: list[str] = state.get("platforms_used", [])
    product_name = state.get("product_name", "")

    emit_progress("research_price", config, "node_start", f"开始价格调研: {product_name}, {len(variants)} 个型号")

    if not variants or (not platforms_new and not platforms_used):
        return {
            "price_data": {},
            "history_data": {},
            "errors": ["缺少 variants 或平台列表"],
        }

    logger.info(f"[Agent 2] 开始价格调研: {product_name}, {len(variants)} 个型号")

    price_data: dict[str, list[dict]] = {}
    history_data: dict[str, list[dict]] = {}
    errors: list[str] = []

    # 并行执行：当前价格搜索 + 历史价格搜索
    try:
        with ThreadPoolExecutor(max_workers=min(len(variants) * 2, 8)) as executor:
            # 提交所有搜索任务
            variant_futures: dict = {}

            for v in variants:
                # 当前价格
                variant_futures[executor.submit(
                    _search_variant, v, platforms_new, platforms_used
                )] = ("current", v)

                # 历史价格
                variant_futures[executor.submit(
                    _search_history_for_variant, v["search_query"], product_name
                )] = ("history", v)

            # 收集结果
            for future in as_completed(variant_futures):
                task_type, v = variant_futures[future]
                try:
                    if task_type == "current":
                        spec, prices = future.result()
                        price_data[spec] = prices
                        logger.info(f"[Agent 2] {spec}: 共获取 {len(prices)} 条当前价格")
                        emit_progress("research_price", config, "progress", f"{spec}: 获取到 {len(prices)} 条当前价格")
                    else:
                        history_points = future.result()
                        history_data[v["spec"]] = history_points
                        emit_progress("research_price", config, "progress", f"{v['spec']}: 获取到 {len(history_points)} 条历史价格")
                except Exception as e:
                    errors.append(f"{v['spec']} {task_type} 搜索失败: {e}")
                    logger.error(f"[Agent 2] {v['spec']} {task_type} 失败: {e}")

    except Exception as e:
        errors.append(f"价格调研异常: {e}")
        logger.error(f"[Agent 2] 调研异常: {e}")

    # spec -> search_query 映射，统一用 search_query 作为 DB key
    spec_to_query = {v["spec"]: v["search_query"] for v in variants}

    # 存入 SQLite（当前价格） + 查询本地历史
    try:
        for spec, prices in price_data.items():
            keyword = spec_to_query.get(spec, spec)
            for p in prices:
                if p.get("price", 0) > 0:
                    insert_price(
                        product_keyword=keyword,
                        platform=p.get("platform", ""),
                        price=p["price"],
                        original_price=p.get("original_price", 0.0),
                        source_url=p.get("source_url", ""),
                        is_secondhand=p.get("is_secondhand", False),
                        condition=p.get("condition", ""),
                    )

        # 合并外部搜索的历史数据 + 本地 SQLite 历史
        # 本地 DB 数据优先（最可靠），外部搜索作为补充（标记为"外部参考"）
        for v in variants:
            records = history_lookup.invoke({
                "product_keyword": v["search_query"],
                "days": 90,
            })
            local_history = json.loads(records) if isinstance(records, str) else records

            external = history_data.get(v["spec"], [])

            merged = []
            # 本地数据优先（最可靠的信息源）
            for r in local_history:
                merged.append({
                    "date": r.get("fetched_at", "")[:10],
                    "price": r.get("price", 0),
                    "source": f"{r.get('platform', '')} 本地记录",
                })
            # 外部数据作为参考补充，标记来源
            for r in external:
                merged.append({
                    "date": r.get("date", "")[:10],
                    "price": r.get("price", 0),
                    "source": f"{r.get('source', '外部参考')}",
                })

            history_data[v["spec"]] = merged

        total_current = sum(len(v) for v in price_data.values())
        total_history = sum(len(v) for v in history_data.values())
        emit_progress("research_price", config, "progress", f"数据汇总完成: {total_current} 条当前价格, {total_history} 条历史记录")

    except Exception as e:
        errors.append(f"数据库操作异常: {e}")
        logger.error(f"[Agent 2] 数据库异常: {e}")

    return {
        "price_data": price_data,
        "history_data": history_data,
        "errors": errors,
    }
