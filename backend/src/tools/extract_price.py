import json
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from ..utils import extract_json, get_llm

llm = get_llm(0.0)

EXTRACT_SYSTEM_PROMPT = """你是一个价格数据提取专家。从搜索引擎返回的商品搜索摘要中提取价格信息。

## 核心规则（最重要）
- **只提取摘要中明确包含具体价格数字的条目**
- **如果某条摘要完全没有价格数字，直接跳过，不要编造**
- **如果所有摘要都没有价格数字，返回空列表 []**
- 忽略明显不合理的价格：1元、99999元等异常值，以及明显不是该商品的标价

## 提取字段
- 平台、店铺名称、价格（必填，必须是从摘要中找到的真实数字）
- 原价（如有划线价）、是否官方店、是否有货、促销信息
- 二手商品额外：成色描述、拆修情况、发票、保修、卖家信誉

## 输出格式（纯 JSON 数组，不要 markdown 包裹，找不到价格就输出 []）
[
  {
    "platform": "京东",
    "shop_name": "华为官方旗舰店",
    "price": 6999.0,
    "original_price": 7999.0,
    "is_official": true,
    "in_stock": true,
    "promotion": "满3000减200",
    "source_url": "https://...",
    "is_secondhand": false,
    "condition": null,
    "repairs": null,
    "has_invoice": null,
    "warranty_left": null,
    "seller_rating": null
  }
]"""


@tool
def extract_price(search_results_json: str, platform: str, is_secondhand: bool = False) -> str:
    """从 Tavily 搜索结果中提取结构化价格信息。

    Args:
        search_results_json: search_price 返回的 JSON 字符串
        platform: 平台名称
        is_secondhand: 是否为二手搜索
    """
    try:
        data = json.loads(search_results_json)
    except json.JSONDecodeError:
        return json.dumps([], ensure_ascii=False)

    results = data.get("results", [])
    if not results:
        return json.dumps([], ensure_ascii=False)

    # 拼接摘要文本
    snippets = []
    for r in results[:settings.MAX_SEARCH_RESULTS]:
        snippet = f"[{r.get('title', '')}] {r.get('content', '')} (url: {r.get('url', '')})"
        snippets.append(snippet)

    combined = "\n---\n".join(snippets)

    condition_hint = "注意：这是二手商品搜索，请提取二手相关信息（成色、拆修、发票等）。" if is_secondhand else "注意：这是全新商品搜索。"

    try:
        response = llm.invoke([
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=f"平台：{platform}\n{condition_hint}\n\n搜索结果：\n{combined}"),
        ])

        parsed = extract_json(response.content, expect_list=True)
        if not isinstance(parsed, list):
            return json.dumps([], ensure_ascii=False)

        # 修正字段 + 过滤无效条目
        cleaned = []
        for item in parsed:
            # 没有有效价格 → 跳过
            price = item.get("price")
            if price is None or price <= 0:
                continue

            if not item.get("platform"):
                item["platform"] = platform
            if item.get("is_secondhand") is None:
                item["is_secondhand"] = is_secondhand
            if not item.get("shop_name"):
                item["shop_name"] = ""
            cleaned.append(item)

        return json.dumps(cleaned, ensure_ascii=False)

    except Exception:
        return json.dumps([], ensure_ascii=False)
