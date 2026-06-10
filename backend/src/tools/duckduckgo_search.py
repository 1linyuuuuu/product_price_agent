"""DuckDuckGo 搜索 — 免费，不需要 API Key，通过 DDG HTML 接口实现"""
import re
import urllib.request
import urllib.parse
from loguru import logger


# DDG 的 HTML 搜索接口（无需 API key，无频率限制）
_DDG_HTML_URL = "https://html.duckduckgo.com/html/"


def _ddg_search_raw(query: str, max_results: int = 5) -> dict:
    """DuckDuckGo 文本搜索，返回与 Tavily 统一格式的 dict"""
    results: list[dict] = []

    try:
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            _DDG_HTML_URL,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"DuckDuckGo 请求失败: {e}")
        return {"results": [], "images": []}

    # 解析 HTML 搜索结果 — 提取每个 result 块
    # DDG HTML 结构的 result 块: class="result" 内包含 class="result__a"(title+url)、class="result__snippet"(摘要)
    result_blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )

    for url, title_raw, snippet in result_blocks[:max_results]:
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        body = re.sub(r'<[^>]+>', '', snippet).strip()
        if not title and not body:
            continue
        results.append({
            "title": title or query,
            "url": url,
            "content": body[:300],
            "score": 1.0,
            "source": "duckduckgo",
        })

    logger.info(f"DuckDuckGo 返回 {len(results)} 条结果 (query: {query[:50]}...)")
    return {"results": results, "images": []}
