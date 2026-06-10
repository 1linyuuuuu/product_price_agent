from urllib.parse import quote

from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from ..utils import (
    emit_progress, get_llm, extract_json,
    NON_STORE_DOMAINS, PRICE_AGGREGATOR_DOMAINS, PRICE_AGGREGATOR_NAMES,
)
from ..graph.state import AnalysisState
from ..prompts.comparison_advisor import SYSTEM_PROMPT

llm = get_llm(0.3)


def _format_price_table(price_data: dict) -> str:
    """将 price_data 格式化为全新/二手分区 Markdown 表格"""
    if not price_data:
        return "（暂无价格数据）"

    new_prices: list[dict] = []
    used_prices: list[dict] = []

    for prices in price_data.values():
        for p in prices:
            if p.get("is_secondhand"):
                used_prices.append(p)
            else:
                new_prices.append(p)

    lines = []

    def _build_table(title: str, items: list[dict]):
        if not items:
            lines.append(f"\n### {title}\n（暂无数据）\n")
            return
        lines.append(f"\n### {title}")
        lines.append("| 平台 | 店铺 | 价格 | 原价 | 促销/备注 |")
        lines.append("|------|------|------|------|-----------|")
        for p in items:
            platform = p.get("platform", "未知")
            shop = p.get("shop_name", "-") or "-"
            price = p.get("price") or 0
            orig = f"¥{(p.get('original_price') or 0):.0f}" if (p.get('original_price') or 0) > 0 else "-"
            promo = p.get("promotion", "")
            condition = p.get("condition", "")
            note = f"{promo} | 成色:{condition}" if promo and condition else (promo or condition or "-")
            lines.append(f"| {platform} | {shop} | ¥{price:.0f} | {orig} | {note} |")
        lines.append("")

    _build_table("全新市场", new_prices)
    _build_table("二手市场", used_prices)

    return "\n".join(lines)


def _format_history(history_data: dict) -> str:
    """格式化历史价格数据，区分外部来源和本地积累"""
    if not history_data:
        return "（暂无历史价格数据）"

    lines = []
    for spec, records in history_data.items():
        if not records:
            continue

        external = [r for r in records if "本地记录" not in str(r.get("source", ""))]
        local = [r for r in records if "本地记录" in str(r.get("source", ""))]

        lines.append(f"\n### {spec} 历史趋势")

        if external:
            lines.append("\n**外部数据源**（慢慢买/什么值得买/新闻等）：")
            for r in external[:5]:
                lines.append(f"- {r.get('date', '')[:10]} | {r.get('source', '')} | ¥{(r.get('price') or 0):.0f}")

        if local:
            lines.append(f"\n**本地监测数据**（{len(local)} 条）：")
            # 按日期去重，取最近 5 条
            seen = set()
            count = 0
            for r in sorted(local, key=lambda x: x.get("date", ""), reverse=True):
                key = (r.get("date", "")[:10], r.get("price"))
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {r.get('date', '')[:10]} | {r.get('source', '')} | ¥{(r.get('price') or 0):.0f}")
                count += 1
                if count >= 5:
                    break

        lines.append("")

    return "\n".join(lines)


def _describe_trend_data(td: dict) -> str:
    if not td:
        return "无数据"
    parts = []
    pc = td.get("platformComparison")
    if pc and pc.get("series"):
        parts.append(f"柱状图({len(pc['series'])}条series×{len(pc.get('xAxis',{}).get('data',[]))}平台)")
    ph = td.get("priceHistory")
    if ph and ph.get("series"):
        parts.append(f"折线图({len(ph['series'])}条series×{len(ph.get('xAxis',{}).get('data',[]))}日)")
    return ", ".join(parts) if parts else "无有效图表"


# 各平台搜索链接模板
_PLATFORM_SEARCH_URLS: dict[str, str] = {
    "京东": "https://search.jd.com/Search?keyword=",
    "淘宝": "https://s.taobao.com/search?q=",
    "天猫": "https://list.tmall.com/search_product.htm?q=",
    "拼多多": "https://mobile.yangkeduo.com/search_result.html?search_key=",
    "闲鱼": "https://s.2.taobao.com/list/list.htm?q=",
    "转转": "https://m.zhuanzhuan.com/platform/search?keyword=",
}


def _is_price_aggregator_name(name: str) -> bool:
    """检查 shop_name 是否是价格聚合站/非店铺名称"""
    name_lower = name.lower()
    return any(b.lower() in name_lower for b in PRICE_AGGREGATOR_NAMES)


def _is_valid_store_url(url: str, platform: str) -> bool:
    """检查 URL 是否为有效的店铺/商品直链，而非价格聚合站"""
    if not url or not url.startswith("http"):
        return False
    for domain in PRICE_AGGREGATOR_DOMAINS:
        if domain in url:
            return False
    for d in NON_STORE_DOMAINS:
        if d in url:
            return False
    return True


def _build_store_search_url(platform: str, variant: str, shop_name: str = "") -> str:
    """生成平台搜索结果链接，优先用店铺名+商品名"""
    base = _PLATFORM_SEARCH_URLS.get(platform)
    if not base:
        return f"https://www.google.com/search?q={quote(variant)}"
    query = f"{shop_name} {variant}" if shop_name else variant
    return base + quote(query.strip())


def _enrich_recommend_cards(cards: list[dict], price_data: dict, product_images: dict[str, list[str]]) -> list[dict]:
    """用 price_data 丰富 LLM 推荐卡片：匹配真实 URL 或生成店铺搜索链接"""
    if not cards:
        return []

    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    # 构建 price_data 查找索引：(spec, platform, is_used, shop_name) → url
    # 同时存一份不带 shop_name 的索引作为回退
    price_index: dict[tuple, str] = {}
    price_index_no_shop: dict[tuple, str] = {}
    for spec, prices in price_data.items():
        for p in prices:
            plat = _norm(p.get("platform", ""))
            is_used = bool(p.get("is_secondhand"))
            sn = _norm(p.get("shop_name", ""))
            url = (p.get("source_url") or "").strip()
            if not url:
                continue
            key_full = (_norm(spec), plat, is_used, sn)
            key_no_shop = (_norm(spec), plat, is_used)
            if key_full not in price_index:
                price_index[key_full] = url
            if key_no_shop not in price_index_no_shop:
                price_index_no_shop[key_no_shop] = url

    def _match_url(variant: str, platform: str, is_used: bool, shop_name: str) -> str:
        """三层匹配：精确(含店铺) → 精确(不含店铺) → 模糊(variant 子串)"""
        v = _norm(variant)
        plat = _norm(platform)
        sn = _norm(shop_name)

        # 1. 精确匹配：variant + platform + is_used + shop_name
        url = price_index.get((v, plat, is_used, sn), "")
        if url:
            return url

        # 2. 精确匹配：variant + platform + is_used（不含 shop_name）
        url = price_index_no_shop.get((v, plat, is_used), "")
        if url:
            return url

        # 3. 模糊匹配：platform + is_used 一致，variant 有交集
        for (spec, p, used), u in price_index_no_shop.items():
            if p != plat or used != is_used:
                continue
            # 要求较短一方至少 3 字符且在较长一方中作为连续子串出现
            shorter = v if len(v) < len(spec) else spec
            longer = spec if len(v) < len(spec) else v
            if len(shorter) >= 3 and shorter in longer:
                return u

        return ""

    def _find_images(variant: str) -> list[str]:
        """按 variant 名匹配图片：精确匹配 → 模糊匹配 → 任意图片"""
        vlow = variant.lower().strip()
        for spec, imgs in product_images.items():
            if spec.lower().strip() == vlow:
                return imgs
        for spec, imgs in product_images.items():
            if vlow in spec.lower() or spec.lower() in vlow:
                return imgs
        all_imgs: list[str] = []
        for imgs in product_images.values():
            all_imgs.extend(imgs)
        return all_imgs

    enriched = []
    for card in cards:
        variant = (card.get("variant") or "").strip()
        platform = (card.get("platform") or "").strip()
        shop_name = (card.get("shop_name") or "").strip()
        is_used = bool(card.get("is_used"))

        source_url = _match_url(variant, platform, is_used, shop_name)

        if _is_valid_store_url(source_url, platform):
            buy_url = source_url
        else:
            buy_url = _build_store_search_url(platform, variant, shop_name)

        # 不带 shop_name 时从 price_data 补充
        if not shop_name:
            v = _norm(variant)
            plat = _norm(platform)
            for spec, prices in price_data.items():
                if v in _norm(spec) or _norm(spec) in v:
                    for p in prices:
                        if _norm(p.get("platform", "")) == plat and bool(p.get("is_secondhand")) == is_used:
                            sn = (p.get("shop_name") or "").strip()
                            if sn and not _is_price_aggregator_name(sn):
                                shop_name = sn
                                break
                    if shop_name:
                        break

        matched_images = _find_images(variant)
        card["buy_url"] = buy_url
        card["shop_name"] = shop_name
        card["image"] = matched_images[0] if matched_images else ""
        card["all_images"] = matched_images
        enriched.append(card)

    return enriched


def _build_trend_data(price_data: dict, history_data: dict, variants: list) -> dict:
    """构建 ECharts 可视化数据：平台比价柱状图 + 历史价格折线图"""
    # --- 1. 平台比价柱状图 ---
    all_platforms = []
    seen_platforms = set()
    for prices in price_data.values():
        for p in prices:
            plat = p.get("platform", "未知")
            if plat not in seen_platforms:
                seen_platforms.add(plat)
                all_platforms.append(plat)

    bar_series = []
    legend_data = []
    for v in variants:
        spec = v.get("spec", "")
        prices = price_data.get(spec, [])

        new_prices = [p for p in prices if not p.get("is_secondhand")]
        used_prices = [p for p in prices if p.get("is_secondhand")]

        if new_prices:
            legend_data.append(f"{spec} 全新")
            ppm = {p.get("platform"): p.get("price") for p in new_prices}
            bar_series.append({
                "name": f"{spec} 全新",
                "type": "bar",
                "data": [ppm.get(plat) for plat in all_platforms],
            })

        if used_prices:
            legend_data.append(f"{spec} 二手")
            ppm = {p.get("platform"): p.get("price") for p in used_prices}
            bar_series.append({
                "name": f"{spec} 二手",
                "type": "bar",
                "data": [ppm.get(plat) for plat in all_platforms],
            })

    platform_comparison = {
        "title": {"text": "各平台价格对比"},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": legend_data},
        "xAxis": {"type": "category", "data": all_platforms},
        "yAxis": {"type": "value", "name": "价格 (¥)"},
        "series": bar_series,
    } if bar_series else None

    # --- 2. 历史价格折线图 ---
    all_dates = []
    seen_dates = set()
    for records in history_data.values():
        for r in records:
            date = str(r.get("fetched_at", "") or r.get("date", ""))[:10]
            if date and date not in seen_dates:
                seen_dates.add(date)
                all_dates.append(date)

    all_dates.sort()

    line_series = []
    line_legend = []
    for v in variants:
        spec = v.get("spec", "")
        records = history_data.get(spec, [])
        if not records:
            continue

        date_price_map: dict[str, list] = {}
        for r in records:
            date = str(r.get("fetched_at", "") or r.get("date", ""))[:10]
            price = r.get("price", 0)
            if date and price:
                date_price_map.setdefault(date, []).append(price)

        date_avg = {d: sum(ps) / len(ps) for d, ps in date_price_map.items()}

        line_legend.append(spec)
        line_series.append({
            "name": spec,
            "type": "line",
            "data": [date_avg.get(d) for d in all_dates],
            "smooth": True,
            "connectNulls": True,
        })

    price_history = {
        "title": {"text": "历史价格走势"},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": line_legend},
        "xAxis": {"type": "category", "data": all_dates},
        "yAxis": {"type": "value", "name": "价格 (¥)"},
        "series": line_series,
    } if line_series else None

    return {
        "platformComparison": platform_comparison,
        "priceHistory": price_history,
    }


def _compute_summary(price_data: dict) -> str:
    """计算价格摘要：每个 variant 的最低/最高/均价"""
    if not price_data:
        return ""

    lines = []
    for spec, prices in price_data.items():
        if not prices:
            continue
        valid = [p["price"] for p in prices if p.get("price", 0) > 0]
        if not valid:
            continue

        new_p = [p["price"] for p in prices if not p.get("is_secondhand") and p.get("price", 0) > 0]
        used_p = [p["price"] for p in prices if p.get("is_secondhand") and p.get("price", 0) > 0]

        lines.append(f"- **{spec}**: 总 {len(prices)} 条价格")
        if new_p:
            lines.append(f"  - 全新最低 ¥{min(new_p):.0f}，最高 ¥{max(new_p):.0f}，均价 ¥{sum(new_p)/len(new_p):.0f}")
        if used_p:
            lines.append(f"  - 二手最低 ¥{min(used_p):.0f}，最高 ¥{max(used_p):.0f}，均价 ¥{sum(used_p)/len(used_p):.0f}")
        lines.append("")

    return "\n".join(lines)


def compare_advise_node(state: AnalysisState, config: RunnableConfig = None) -> dict:
    """Agent 3: 对比推荐 — 整合价格数据，生成对比报告和购买建议"""
    is_multi = state.get("is_multi", False)
    sub_products: list[dict] = state.get("sub_products", [])
    errors_state = state.get("errors", [])

    # --- 多商品集合路径：合并各子商品的报告 ---
    if is_multi and sub_products:
        emit_progress("compare_advise", config, "node_start", f"正在生成多商品对比报告，共 {len(sub_products)} 项...")
        sections: list[str] = []
        all_recommend_cards: list[dict] = []

        for i, sp in enumerate(sub_products):
            sp_name = sp.get("product_name", f"商品{i+1}")
            sp_price_data = sp.get("price_data", {})
            if not sp_price_data:
                sections.append(f"## {sp_name}\n\n> 暂无价格数据")
                continue

            summary = _compute_summary(sp_price_data)
            price_table = _format_price_table(sp_price_data)
            sp_variants = sp.get("variants", [])
            variant_list = "\n".join(
                f"- **{v.get('spec', '')}**" for v in sp_variants
            )
            concern = sp.get("user_concern", "性价比优先")
            budget = state.get("user_concern", "")

            budget_hint = f"\n整体预算: {budget}" if budget else ""
            user_prompt = f"""## 商品: {sp_name}
            用户关注点: {concern}{budget_hint}

            ## 型号列表
            {variant_list}

            ## 价格摘要
            {summary}

            ## 实时价格明细
            {price_table}

            请针对 {sp_name} 给出比价分析和推荐卡片。输出 JSON：

            ```json
            {{
              "comparison_report": "简要比价分析（100字以内）",
              "recommendation": "购买建议（50字以内）",
              "recommend_cards": [
                {{
                  "variant": "具体型号",
                  "platform": "平台名",
                  "shop_name": "店铺名",
                  "is_used": false,
                  "price": 价格数字,
                  "reason": "推荐理由（10字以内）",
                  "text": "完整推荐文字，包含型号、平台、价格、理由（50-100字）",
                  "type": "primary"
                }}
              ]
            }}
            ```

            要求：
            - 从 {sp_name} 的型号中，推荐 1-2 个最优选择
            - primary 给首选，如有备选加一张 type=alternative
            - variant/platform/shop_name/price 必须与价格数据中一致
            - text 字段包含完整的推荐理由，可独立阅读"""

            try:
                response = llm.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ])

                raw = (response.content or "").strip()
                parsed = extract_json(raw)
                if not isinstance(parsed, dict) or "comparison_report" not in parsed:
                    parsed = {"comparison_report": raw, "recommendation": "", "recommend_cards": []}

            except Exception as e:
                logger.warning(f"[Agent 3] {sp_name} LLM 调用失败: {e}")
                parsed = {"comparison_report": f"## {sp_name}\n\n> 报告生成失败: {e}", "recommendation": "", "recommend_cards": []}

            section = f"## {sp_name}\n\n{price_table}\n\n{parsed.get('comparison_report', '')}"
            sections.append(section)
            cards = parsed.get("recommend_cards", [])
            if cards:
                product_images = sp.get("product_images", {})
                cards = _enrich_recommend_cards(cards, sp_price_data, product_images)
                all_recommend_cards.extend(cards)

            emit_progress("compare_advise", config, "progress", f"  {sp_name} 报告完成")

        # 合并所有子商品的 price_data 和 history_data，用于前端比价表+趋势图
        merged_price_data: dict[str, list[dict]] = {}
        merged_history_data: dict[str, list[dict]] = {}
        merged_variants: list[dict] = []
        for sp in sub_products:
            sp_name = sp.get("product_name", "")
            for spec, prices in (sp.get("price_data", {}) or {}).items():
                key = f"{sp_name} {spec}" if sp_name else spec
                merged_price_data[key] = prices
            for spec, records in (sp.get("history_data", {}) or {}).items():
                key = f"{sp_name} {spec}" if sp_name else spec
                merged_history_data[key] = records
            for v in (sp.get("variants", []) or []):
                v2 = dict(v)
                v2["spec"] = f"{sp_name} {v2.get('spec', '')}" if sp_name else v2.get("spec", "")
                merged_variants.append(v2)

        merged_trend_data = _build_trend_data(merged_price_data, merged_history_data, merged_variants)

        combined_report = "\n\n---\n\n".join(sections)
        combined_recommendation = f"以上是针对 {len(sub_products)} 个子商品的逐一分析。整体建议请参考各商品推荐卡片。"

        emit_progress("compare_advise", config, "progress", "多商品报告生成完成")

        return {
            "comparison_report": combined_report,
            "recommendation": combined_recommendation,
            "price_data": merged_price_data,
            "history_data": merged_history_data,
            "trend_data": merged_trend_data,
            "recommend_cards": all_recommend_cards,
            "sub_results": sub_products,
            "errors": errors_state,
        }

    # --- 单一商品路径（原逻辑）---
    product_name = state.get("product_name", "")
    variants = state.get("variants", [])
    price_data = state.get("price_data", {})
    history_data = state.get("history_data", {})
    user_concern = state.get("user_concern", "")

    emit_progress("compare_advise", config, "node_start", "正在生成对比报告...")

    logger.info(f"[Agent 3] 生成对比报告: {product_name}, {sum(len(v) for v in price_data.values())} 条价格, {sum(len(v) for v in history_data.values())} 条历史")

    if not price_data:
        return {
            "comparison_report": f"## {product_name} 比价分析\n\n> 暂无价格数据，请检查搜索配置后重试。",
            "recommendation": "数据不足，无法给出建议。",
            "trend_data": {},
            "errors": errors_state + ["price_data 为空"],
        }

    # 格式化所有数据
    summary = _compute_summary(price_data)
    price_table = _format_price_table(price_data)
    history_text = _format_history(history_data)
    variant_list = "\n".join(
        f"- **{v.get('spec', '')}**（搜索词: {v.get('search_query', '')}）" for v in variants
    )

    # 数据质量提示
    quality_notes = []
    if any(p.get("platform") == "闲鱼" for prices in price_data.values() for p in prices):
        quality_notes.append("- 闲鱼二手价格来自搜索引擎摘要，部分 listing 无法获取精确价格，数据可能不完整")
    if errors_state:
        quality_notes.append(f"- 数据采集过程中的异常: {'; '.join(errors_state[:3])}")
    quality_section = "\n".join(quality_notes) if quality_notes else "无特殊说明"

    user_prompt = f"""## 商品信息
- 品名: {product_name}
- 用户关注点: {user_concern or "通用比价"}

## 型号列表
{variant_list}

## 价格摘要
{summary}

## 实时价格明细
{price_table}

## 历史价格趋势
{history_text}

## 数据质量说明
{quality_section}

请按照系统提示中的报告结构，生成完整的比价分析报告和购买建议。"""

    emit_progress("compare_advise", config, "progress", "正在调用 LLM 生成分析报告...")

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = (response.content or "").strip()

        if not raw:
            logger.error("[Agent 3] LLM 返回空响应")
            return {
                "comparison_report": f"## {product_name} 比价分析\n\n> 报告生成失败：LLM 返回空响应，请重试。",
                "recommendation": "",
                "trend_data": _build_trend_data(price_data, history_data, variants),
                "recommend_cards": [],
                "errors": errors_state + ["LLM 返回空响应"],
            }

        # 尝试 JSON 解析（新 Prompt 要求返回 JSON）
        report = ""
        recommendation = ""
        json_parsed = False

        # 尝试 JSON 解析
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and (parsed.get("comparison_report") or parsed.get("recommendation")):
            report = (parsed.get("comparison_report") or "").strip()
            recommendation = (parsed.get("recommendation") or "").strip()
            recommend_cards_raw = parsed.get("recommend_cards") or []
            json_parsed = True
            logger.info(f"[Agent 3] JSON 解析成功, recommend_cards: {len(recommend_cards_raw)} 条")
        else:
            recommend_cards_raw = []

        # 回退：基于 Markdown 标记分离
        if not json_parsed:
            report = raw
            recommendation = ""
            recommend_cards_raw = []
            markers = [
                "## 5. 购买建议", "## 购买建议", "## 5.", "## 总结与建议",
                "### 5. 购买建议", "### 购买建议",
                "#### 5. 购买建议", "#### 购买建议",
            ]
            best_idx = -1
            for marker in markers:
                idx = raw.rfind(marker)
                if idx > len(raw) * 0.4:
                    best_idx = max(best_idx, idx)

            if best_idx > 0:
                report = raw[:best_idx].strip()
                recommendation = raw[best_idx:].strip()

        logger.info(f"[Agent 3] 报告: {len(report)} 字符, 建议: {len(recommendation)} 字符")

        emit_progress("compare_advise", config, "progress", "正在生成可视化数据...")

        trend_data = _build_trend_data(price_data, history_data, variants)
        logger.info(f"[Agent 3] trend_data: {_describe_trend_data(trend_data)}")

        # 用 price_data 中的真实 URL 和 product_images 丰富推荐卡片
        product_images = state.get("product_images", {})
        recommend_cards = _enrich_recommend_cards(recommend_cards_raw, price_data, product_images)

        return {
            "comparison_report": report,
            "recommendation": recommendation,
            "trend_data": trend_data,
            "recommend_cards": recommend_cards,
            "errors": errors_state,
        }

    except Exception as e:
        logger.error(f"[Agent 3] 生成报告失败: {e}")
        return {
            "comparison_report": f"## {product_name} 比价分析\n\n> 报告生成失败: {e}",
            "recommendation": "",
            "trend_data": {},
            "errors": errors_state + [str(e)],
        }
