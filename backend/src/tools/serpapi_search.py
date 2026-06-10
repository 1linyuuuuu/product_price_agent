import time
from loguru import logger
from serpapi import GoogleSearch

from ..config import settings

MAX_RETRIES = 2
RETRY_DELAY = 1.5


def _serpapi_search_with_retry(query: str, max_results: int = 5) -> dict:
    """带重试的 SerpAPI 搜索，返回与 Tavily 统一格式的 dict"""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            params = {
                "q": query,
                "api_key": settings.SERPAPI_API_KEY,
                "num": max_results,
                "hl": "zh-CN",
                "gl": "cn",
                "engine": "google",
            }
            search = GoogleSearch(params)
            raw = search.get_dict()
            return _normalize(raw)
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning(f"SerpAPI 搜索失败 (第{attempt+1}次)，{RETRY_DELAY}s 后重试: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))
    raise last_err


def _normalize(raw: dict) -> dict:
    """将 SerpAPI 原始结果标准化为 Tavily 格式 {results: [{title, url, content, score}]}"""
    results = []
    organic = raw.get("organic_results", [])

    for r in organic:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "content": r.get("snippet", "") or "",
            "score": 1.0 - (r.get("position", 0) / 20),  # 位置越前分数越高
            "source": "serpapi",
        })

    logger.info(f"SerpAPI 返回 {len(results)} 条结果")

    return {
        "results": results,
        "images": [],
        "answer": raw.get("answer_box", {}).get("answer", ""),
    }
