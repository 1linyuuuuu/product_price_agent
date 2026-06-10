import sqlite3
import os
from ..config import settings


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_keyword TEXT NOT NULL,
            platform TEXT NOT NULL,
            price REAL NOT NULL,
            original_price REAL,
            source_url TEXT,
            is_secondhand INTEGER DEFAULT 0,
            condition TEXT,
            fetched_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_time
            ON price_history(product_keyword, fetched_at DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_product_platform
            ON price_history(product_keyword, platform)
    """)
    conn.commit()
    conn.close()
