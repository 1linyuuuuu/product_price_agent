import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from tavily import TavilyClient

from ..config import settings
from .serpapi_search import _serpapi_search_with_retry
from .duckduckgo_search import _ddg_search_raw

# Tavily 已超额时跳过，避免每次等待报错
_tavily_dead = False
_tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

_QUOTA_KEYWORDS = ["usage limit", "exceed", "quota", "rate limit", "429", "billing"]


def _is_quota_exhausted(err_msg: str) -> bool:
    """检测 Tavily 额度是否耗尽"""
    lower = err_msg.lower()
    return any(kw in lower for kw in _QUOTA_KEYWORDS)


def _tavily_search_raw(query: str, max_results: int = 5, include_images: bool = False, include_raw_content: bool = True) -> dict:
    """Tavily 搜索"""
    return _tavily_client.search(
        query=query,
        max_results=max_results,
        include_images=include_images,
        include_raw_content=include_raw_content,
    )


def _merge_results(sources: list[tuple[str, dict | None]]) -> dict:
    """合并多个搜索结果，按 URL 去重，保持优先级顺序"""
    seen_urls = set()
    merged = []
    all_images = []

    for source_label, result in sources:
        if not result:
            continue
        for r in result.get("results", []):
            url = r.get("url", "")
            if url and url in seen_urls:
                continue
            seen_urls.add(url)
            r["source"] = source_label
            merged.append(r)

        for img in result.get("images", []):
            if img and img not in all_images:
                all_images.append(img)

    labels = [s for s, r in sources if r]
    logger.info(f"混合搜索: {' + '.join(labels)} -> {len(merged)} 条（去重后）")

    return {"results": merged, "images": all_images, "answer": ""}


def hybrid_search(query: str, max_results: int = 5, include_images: bool = False, include_raw_content: bool = True) -> str:
    """混合搜索：并行调用 Tavily + SerpAPI + DuckDuckGo（免费永久兜底），合并去重返回 JSON"""
    global _tavily_dead
    use_serpapi = bool(settings.SERPAPI_API_KEY)

    tasks: dict = {}
    results_map: dict[str, dict | None] = {"tavily": None, "serpapi": None, "duckduckgo": None}

    with ThreadPoolExecutor(max_workers=3) as executor:
        # 1) Tavily（额度耗尽后自动跳过）
        if not _tavily_dead:
            tavily_future = executor.submit(_tavily_search_raw, query, max_results, include_images, include_raw_content)
            tasks[tavily_future] = "tavily"

        # 2) SerpAPI（有 key 时参与）
        if use_serpapi:
            serpapi_future = executor.submit(_serpapi_search_with_retry, query, max_results)
            tasks[serpapi_future] = "serpapi"

        # 3) DuckDuckGo — 免费，不需要 key，永远作为兜底
        ddg_future = executor.submit(_ddg_search_raw, query, max_results)
        tasks[ddg_future] = "duckduckgo"

        # 收集结果
        for future in as_completed(tasks):
            source = tasks[future]
            try:
                results_map[source] = future.result()
            except Exception as e:
                err_msg = str(e)
                logger.warning(f"混合搜索 {source} 失败: {e}")
                if source == "tavily" and _is_quota_exhausted(err_msg):
                    _tavily_dead = True
                    logger.warning("Tavily 额度已耗尽，后续搜索将跳过 Tavily")

    ordered_sources: list[tuple[str, dict | None]] = [
        ("tavily", results_map.get("tavily")),
        ("serpapi", results_map.get("serpapi")),
        ("duckduckgo", results_map.get("duckduckgo")),
    ]

    successful = [(s, r) for s, r in ordered_sources if r]

    if not successful:
        raise RuntimeError("所有搜索引擎均失败 (Tavily + SerpAPI + DuckDuckGo)")

    if len(successful) == 1:
        _, result = successful[0]
        return json.dumps(result, ensure_ascii=False)

    merged = _merge_results(successful)
    return json.dumps(merged, ensure_ascii=False)
