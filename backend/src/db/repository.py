import json
from datetime import datetime, timedelta
from .database import get_connection


def insert_price(
    product_keyword: str,
    platform: str,
    price: float,
    original_price: float = 0.0,
    source_url: str = "",
    is_secondhand: bool = False,
    condition: str = "",
):
    """写入一条价格记录"""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO price_history
        (product_keyword, platform, price, original_price, source_url, is_secondhand, condition, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            product_keyword,
            platform,
            price,
            original_price,
            source_url,
            1 if is_secondhand else 0,
            condition,
            datetime.now().isoformat(),
        ],
    )
    conn.commit()
    conn.close()


def query_history(product_keyword: str, days: int = 30) -> list[dict]:
    """查询历史价格记录"""
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """
        SELECT * FROM price_history
        WHERE product_keyword = ? AND fetched_at >= ?
        ORDER BY fetched_at
        """,
        [product_keyword, since],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
