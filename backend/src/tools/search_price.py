import time
from langchain_core.tools import tool
from tavily import TavilyClient
from loguru import logger
from ..config import settings
from ..utils import NON_STORE_DOMAINS
from .hybrid_search import hybrid_search

client = TavilyClient(api_key=settings.TAVILY_API_KEY)

MAX_RETRIES = 2
RETRY_DELAY = 1.5  # 秒


def _tavily_search_with_retry(**kwargs):
    """带重试的 Tavily 搜索（图片搜索专用，不对用户开放 SerpAPI 图片）"""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.search(**kwargs)
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning(f"Tavily 搜索失败 (第{attempt+1}次)，{RETRY_DELAY}s 后重试: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
    raise last_err


@tool
def search_price(query: str, platform: str = "京东", is_secondhand: bool = False) -> str:
    """搜索指定商品在指定平台的价格。使用混合搜索引擎（Tavily + SerpAPI）。

    Args:
        query: 搜索关键词，如 "华为Mate 70 Pro 256GB"
        platform: 平台名称，如 京东/淘宝/拼多多/闲鱼/转转
        is_secondhand: 是否搜索二手市场
    """
    condition_suffix = " 二手 95新" if is_secondhand else ""
    search_query = f"{query} {platform}{condition_suffix} 价格"

    return hybrid_search(
        query=search_query,
        max_results=settings.MAX_SEARCH_RESULTS,
        include_raw_content=True,
    )


def search_product_images(product_name: str, max_images: int = 4) -> list[str]:
    """用 Tavily 搜索商品图片，优先电商源，返回图片 URL 列表"""
    queries = [
        f"{product_name} site:taobao.com OR site:jd.com 商品图片",
        f"{product_name} 商品实拍图 开箱",
    ]
    all_images: list[str] = []

    for q in queries:
        if len(all_images) >= max_images:
            break
        try:
            result = _tavily_search_with_retry(
                query=q,
                include_images=True,
                max_results=3,
            )
            images = result.get("images", [])
            for url in images:
                if url and url.startswith("http") and url not in all_images:
                    if not any(d in url for d in NON_STORE_DOMAINS):
                        all_images.append(url)
                        if len(all_images) >= max_images:
                            break
        except Exception as e:
            logger.warning(f"图片搜索 '{q}' 失败: {e}")

    return all_images[:max_images]
