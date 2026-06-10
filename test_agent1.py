"""
Agent 1 商品解析 — 快速测试脚本
用法: E:/anaconda/envs/price_agent/python.exe test_agent1.py
"""
import sys, os, json

# 把 backend/src 加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))  # 让 .env 加载正常

from dotenv import load_dotenv
load_dotenv(".env")

from src.agents.product_parser import parse_product_node

TEST_QUERIES = [
    "华为Mate 70 Pro 256G vs 512G 哪个更值得买",
    "iPhone 15 Pro 256GB 深空黑 京东淘宝拼多多价格",
    "索尼 WH-1000XM5 耳机 二手",
    "联想拯救者 Y9000P i9-13900HX RTX4060",
]

for q in TEST_QUERIES:
    print("=" * 70)
    print(f"输入: {q}")
    state = {"query": q}
    result = parse_product_node(state)

    print(f"  商品名: {result['product_name']}")
    print(f"  型号数: {len(result['variants'])}")
    for v in result["variants"]:
        print(f"    - [{v['id']}] {v['spec']} → 搜索词: {v['search_query']}")
    print(f"  全新平台: {result['platforms_new']}")
    print(f"  二手平台: {result['platforms_used']}")
    print(f"  用户关注: {result['user_concern']}")
    if result["errors"]:
        print(f"  错误: {result['errors']}")
    print()
