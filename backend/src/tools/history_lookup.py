import json
from langchain_core.tools import tool
from ..db.repository import query_history


@tool
def history_lookup(product_keyword: str, days: int = 30) -> str:
    """查询本地 SQLite 中的商品历史价格记录。

    Args:
        product_keyword: 商品搜索关键词
        days: 查询最近多少天的记录，默认 30 天
    """
    records = query_history(product_keyword, days)
    return json.dumps(records, ensure_ascii=False)
