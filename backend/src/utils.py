"""共享工具函数，供所有 agent 使用"""

import json
import re
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

# === 域名/店铺过滤常量（统一维护，避免多处不一致） ===

# 非商品链接域名（社交/视频/资讯站）
NON_STORE_DOMAINS = [
    "t.me", "douyin.com", "zhihu.com", "geekpark.net", "facebook.com",
]

# 价格聚合站/中间页域名（不是真实店铺地址）
PRICE_AGGREGATOR_DOMAINS = [
    "smzdm.com", "zol.com.cn", "guangdiu.com", "zhuanzhuan.com",
    "post.smzdm", "p.yiqifa.com", "faxian.smzdm",
]

# 非店铺名称（价格聚合站/资讯站等）
PRICE_AGGREGATOR_NAMES = [
    "什么值得买", "慢慢买", "逛丢", "今日热榜", "Telegram", "知乎",
    "smzdm", "manmanbuy", "guangdiu", "zhihu", "facebook", "闲鱼商家",
]


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    """按 temperature 缓存 LLM 实例，避免重复创建"""
    from .config import settings
    return ChatOpenAI(
        model=settings.LLM_MODEL_ID,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
    )


def extract_json(text: str, expect_list: bool = False) -> Any:
    """从 LLM 返回文本中提取 JSON，兼容 ```json ... ``` 包裹格式

    Args:
        text: LLM 原始输出
        expect_list: True 时默认返回 []，否则返回 {}
    """
    default: Any = [] if expect_list else {}

    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError:
        pass

    # 从 ```json ... ``` 中提取
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试 { } 或 [ ] 包裹
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return default


def emit_progress(node: str, config: RunnableConfig | None, event: str, message: str) -> None:
    """向 SSE 队列推送进度事件（线程安全）"""
    queue = config.get("configurable", {}).get("_progress_queue") if config else None
    if queue:
        try:
            queue.put_nowait({"event": event, "data": {"node": node, "message": message}})
        except Exception:
            pass
