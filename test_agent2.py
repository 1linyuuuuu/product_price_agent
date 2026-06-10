"""
Agent 2 价格调研 — 测试脚本
用法: conda activate price_agent && python test_agent2.py

会真实调用 Tavily 搜索 + LLM 提取价格 + 写入 SQLite，注意 API 消耗。
"""
import sys, os, json, time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv(".env")

from src.db.database import init_db
from src.agents.price_researcher import research_price_node

# —— 初始化数据库 ——
init_db()
print("SQLite 数据库已就绪\n")

# —— 测试用例 ——
# 模拟 Agent 1 的输出，跳过 Agent 1 直接测 Agent 2
TEST_STATES = [
    {
        "name": "iPhone 单型号对比",
        "state": {
            "query": "iPhone 15 Pro 256GB 价格",
            "product_name": "iPhone 15 Pro",
            "variants": [
                {"id": 1, "spec": "256GB 深空黑", "search_query": "iPhone 15 Pro 256GB", "status": "pending"},
            ],
            "platforms_new": ["京东", "淘宝", "拼多多"],
            "platforms_used": ["闲鱼"],
            "user_concern": "全新和二手对比",
        },
    },
    # 可增加更多测试用例，例如:
    # {
    #     "name": "耳机 二手为主",
    #     "state": {
    #         "query": "索尼 WH-1000XM5 二手价格",
    #         "product_name": "索尼 WH-1000XM5",
    #         "variants": [
    #             {"id": 1, "spec": "XM5 黑色", "search_query": "索尼 WH-1000XM5 黑色", "status": "pending"},
    #         ],
    #         "platforms_new": ["京东"],
    #         "platforms_used": ["闲鱼", "转转"],
    #         "user_concern": "二手性价比",
    #     },
    # },
]

for case in TEST_STATES:
    print("=" * 70)
    print(f"用例: {case['name']}")
    print(f"商品: {case['state']['product_name']}")
    print(f"型号: {len(case['state']['variants'])} 个")
    print(f"全新平台: {case['state']['platforms_new']}")
    print(f"二手平台: {case['state']['platforms_used']}")
    print("-" * 70)

    t0 = time.time()
    result = research_price_node(case["state"])
    elapsed = time.time() - t0

    # 展示价格数据
    price_data = result.get("price_data", {})
    total_prices = 0
    for spec, prices in price_data.items():
        print(f"\n  [{spec}] 共 {len(prices)} 条价格:")
        for p in prices:
            total_prices += 1
            tag = "二手" if p.get("is_secondhand") else "全新"
            shop = p.get("shop_name", "未知")
            price = p.get("price") or 0
            orig = p.get("original_price") or 0
            promo = p.get("promotion") or ""
            url = (p.get("source_url") or "")[:60]
            plat = (p.get("platform") or "未知")[:4]
            print(f"    {tag} | {plat:4s} | {shop:16s} | {price:>8.2f} 元", end="")
            if orig > 0:
                print(f" (原价 {orig:.2f} 元)", end="")
            if promo:
                print(f" [{promo}]", end="")
            print()
            if p.get("condition"):
                print(f"           成色: {p['condition']}", end="")
                if p.get("seller_rating"):
                    print(f" | 卖家: {p['seller_rating']}", end="")
                print()

    # 历史数据
    history_data = result.get("history_data", {})
    for spec, records in history_data.items():
        if records:
            print(f"\n  [历史趋势] {spec}: {len(records)} 个数据点")
            for r in records[:5]:
                src = r.get("source", r.get("platform", "未知"))
                price = r.get("price", 0)
                date = r.get("date", r.get("fetched_at", ""))[:10]
                print(f"    {date} | {src:20s} | {price:>8.2f} 元")
    hist_count = sum(len(v) for v in history_data.values())
    print(f"\n  历史记录合计: {hist_count} 条 (外部搜索 + 本地积累)")

    # 错误
    if result.get("errors"):
        print(f"  错误: {result['errors']}")

    print(f"\n  耗时: {elapsed:.1f}s | 共获取 {total_prices} 条价格")
    print()
