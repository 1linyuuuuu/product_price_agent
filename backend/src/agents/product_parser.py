from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ..config import settings
from ..graph.state import AnalysisState
from ..prompts.product_parser import SYSTEM_PROMPT
from ..tools.search_price import search_product_images
from ..utils import extract_json, emit_progress, get_llm

DEFAULT_PLATFORMS_NEW = ["京东", "淘宝", "拼多多"]
DEFAULT_PLATFORMS_USED = ["闲鱼", "转转"]

llm = get_llm(0.1)


def parse_product_node(state: AnalysisState, config: RunnableConfig = None) -> dict:
    """Agent 1: 商品解析 — 将自然语言拆解为结构化搜索任务"""
    query = state.get("query", "").strip()

    emit_progress("parse_product", config, "node_start", "正在解析商品型号...")

    if not query:
        return {
            "is_multi": False,
            "sub_products": [],
            "product_name": "",
            "variants": [],
            "platforms_new": DEFAULT_PLATFORMS_NEW,
            "platforms_used": DEFAULT_PLATFORMS_USED,
            "user_concern": "",
            "product_images": {},
            "errors": ["输入为空"],
        }

    logger.info(f"[Agent 1] 解析商品: {query}")

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])

        parsed = extract_json(response.content)

        # --- 多商品集合路径 ---
        if parsed.get("is_multi") and parsed.get("sub_products"):
            sub_products_raw = parsed["sub_products"]
            emit_progress("parse_product", config, "progress", f"识别为多商品组合，共 {len(sub_products_raw)} 个子商品")
            sub_products = []
            for sp in sub_products_raw:
                variants = []
                for i, v in enumerate(sp.get("variants", [])):
                    variants.append({
                        "id": v.get("id", i + 1),
                        "spec": v.get("spec", ""),
                        "search_query": v.get("search_query", f"{sp.get('product_name', '')} {v.get('spec', '')}"),
                        "status": "pending",
                    })
                if not variants:
                    variants.append({
                        "id": 1, "spec": "默认",
                        "search_query": sp.get("product_name", ""),
                        "status": "pending",
                    })
                sub_products.append({
                    "product_name": sp.get("product_name", ""),
                    "category": sp.get("category", ""),
                    "variants": variants,
                    "platforms_new": sp.get("platforms_new") or DEFAULT_PLATFORMS_NEW,
                    "platforms_used": sp.get("platforms_used") or DEFAULT_PLATFORMS_USED,
                    "user_concern": sp.get("user_concern", parsed.get("user_concern", "")),
                    "product_images": {},
                    "price_data": {},
                })
                emit_progress("parse_product", config, "progress",
                      f"  {sp.get('product_name', '')}: {len(variants)} 个型号")

            return {
                "is_multi": True,
                "sub_products": sub_products,
                "product_name": parsed.get("product_name", query),
                "user_concern": parsed.get("user_concern", ""),
                "product_images": {},
                "errors": [],
            }

        # --- 单一商品路径（原逻辑）---
        variants = []
        for i, v in enumerate(parsed.get("variants", [])):
            variants.append({
                "id": v.get("id", i + 1),
                "spec": v.get("spec", ""),
                "search_query": v.get("search_query", f"{parsed.get('product_name', query)} {v.get('spec', '')}"),
                "status": "pending",
            })

        if not variants:
            variants.append({
                "id": 1,
                "spec": "默认",
                "search_query": parsed.get("product_name", query),
                "status": "pending",
            })

        product_name = parsed.get("product_name", query)

        variant_names = [v["spec"] for v in variants]
        emit_progress("parse_product", config, "progress", f"识别到 {len(variants)} 个型号: {', '.join(variant_names)}")

        emit_progress("parse_product", config, "progress", "正在搜索商品图片...")
        product_images: dict[str, list[str]] = {}
        total_images = 0
        for v in variants:
            spec = v["spec"]
            sq = v.get("search_query", spec)
            imgs = search_product_images(sq)
            product_images[spec] = imgs
            total_images += len(imgs)
        emit_progress("parse_product", config, "progress", f"获取到 {total_images} 张商品图片")

        return {
            "is_multi": False,
            "sub_products": [],
            "product_name": product_name,
            "variants": variants,
            "platforms_new": parsed.get("platforms_new") or DEFAULT_PLATFORMS_NEW,
            "platforms_used": parsed.get("platforms_used") or DEFAULT_PLATFORMS_USED,
            "user_concern": parsed.get("user_concern", ""),
            "product_images": product_images,
            "errors": [],
        }

    except Exception as e:
        logger.error(f"[Agent 1] 解析失败: {e}")
        emit_progress("parse_product", config, "progress", f"解析异常，使用降级策略: {e}")
        # 降级：把整段 query 当作一个 variant
        return {
            "is_multi": False,
            "sub_products": [],
            "product_name": query,
            "variants": [{
                "id": 1,
                "spec": "默认",
                "search_query": query,
                "status": "pending",
            }],
            "platforms_new": DEFAULT_PLATFORMS_NEW,
            "platforms_used": DEFAULT_PLATFORMS_USED,
            "user_concern": "",
            "product_images": {},
            "errors": [str(e)],
        }
