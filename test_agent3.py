"""
Agent 3 对比推荐 — 测试脚本
用法: conda activate price_agent && python test_agent3.py

默认用 mock 数据（不耗搜索 API）。设置 USE_REAL_DATA=True 走完整流水线。
"""
import sys, os, json, time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv
load_dotenv(".env")

USE_REAL_DATA = False  # 改为 True 则先跑 Agent1→Agent2→Agent3 全流程

if USE_REAL_DATA:
    from src.db.database import init_db
    from src.agents.product_parser import parse_product_node
    from src.agents.price_researcher import research_price_node
    from src.agents.comparison_advisor import compare_advise_node

    init_db()
    print("=== 完整流水线测试 ===\n")

    query = "华为Mate 70 Pro 256G vs 512G"
    print(f"输入: {query}")

    s1 = parse_product_node({"query": query})
    print(f"[Agent1] 解析完成: {len(s1['variants'])} 个型号")
    for v in s1["variants"]:
        print(f"  - {v['spec']}")

    s1.update({"price_data": {}, "history_data": {}, "errors": []})
    s2 = research_price_node(s1)
    price_count = sum(len(v) for v in s2.get("price_data", {}).values())
    print(f"[Agent2] 搜索完成: {price_count} 条价格")

    s1.update(s2)
    s3 = compare_advise_node(s1)
    print(f"\n{'='*70}")
    print(s3["comparison_report"])
    print(s3["recommendation"])
    if s3.get("errors"):
        print(f"错误: {s3['errors']}")
    td = s3.get("trend_data", {})
    if td:
        print(f"\n[trend_data] 柱状图: {td.get('platformComparison',{}).get('legend',{}).get('data',[])}")
        print(f"[trend_data] 折线图: {td.get('priceHistory',{}).get('legend',{}).get('data',[])}")
    print(f"\n[Agent3] 报告生成完成")

else:
    from src.agents.comparison_advisor import compare_advise_node

    print("=== Mock 数据测试（不消耗搜索 API）===\n")

    # 模拟 Agent 2 的输出
    mock_state = {
        "query": "华为Mate 70 Pro 256G vs 512G",
        "product_name": "华为Mate 70 Pro",
        "variants": [
            {"id": 1, "spec": "256GB 黑色", "search_query": "华为Mate 70 Pro 256GB"},
            {"id": 2, "spec": "512GB 黑色", "search_query": "华为Mate 70 Pro 512GB"},
        ],
        "platforms_new": ["京东", "淘宝", "拼多多"],
        "platforms_used": ["闲鱼", "转转"],
        "user_concern": "关注性价比和大存储需求，不确定256G是否够用",
        "price_data": {
            "256GB 黑色": [
                {"platform": "京东", "shop_name": "华为官方旗舰店", "price": 6499, "original_price": 6999, "is_official": True, "is_secondhand": False, "promotion": "满5000减500"},
                {"platform": "京东", "shop_name": "京东自营", "price": 6399, "original_price": 6999, "is_official": True, "is_secondhand": False, "promotion": "限时直降600"},
                {"platform": "淘宝", "shop_name": "华为天猫旗舰店", "price": 6499, "original_price": 6999, "is_official": True, "is_secondhand": False, "promotion": ""},
                {"platform": "拼多多", "shop_name": "拼多多百亿补贴", "price": 5799, "original_price": 0, "is_official": False, "is_secondhand": False, "promotion": "百亿补贴"},
                {"platform": "闲鱼", "shop_name": "个人卖家A", "price": 4800, "original_price": 0, "is_official": False, "is_secondhand": True, "promotion": "", "condition": "95新 箱说全 无拆修"},
                {"platform": "闲鱼", "shop_name": "个人卖家B", "price": 4400, "original_price": 0, "is_official": False, "is_secondhand": True, "promotion": "", "condition": "9新 轻微划痕"},
            ],
            "512GB 黑色": [
                {"platform": "京东", "shop_name": "华为官方旗舰店", "price": 7499, "original_price": 7999, "is_official": True, "is_secondhand": False, "promotion": "满5000减500"},
                {"platform": "京东", "shop_name": "京东自营", "price": 7299, "original_price": 7999, "is_official": True, "is_secondhand": False, "promotion": "限时直降700"},
                {"platform": "淘宝", "shop_name": "华为天猫旗舰店", "price": 7499, "original_price": 7999, "is_official": True, "is_secondhand": False, "promotion": ""},
                {"platform": "拼多多", "shop_name": "拼多多百亿补贴", "price": 6699, "original_price": 0, "is_official": False, "is_secondhand": False, "promotion": "百亿补贴"},
                {"platform": "闲鱼", "shop_name": "个人卖家C", "price": 5600, "original_price": 0, "is_official": False, "is_secondhand": True, "promotion": "", "condition": "99新 仅拆封 有发票"},
                {"platform": "转转", "shop_name": "转转验机店", "price": 5500, "original_price": 0, "is_official": False, "is_secondhand": True, "promotion": "平台验机", "condition": "95新 无拆修 平台认证"},
            ],
        },
        "history_data": {
            "256GB 黑色": [
                {"platform": "京东", "price": 6899, "fetched_at": "2026-05-15"},
                {"platform": "拼多多", "price": 5899, "fetched_at": "2026-05-20"},
            ],
            "512GB 黑色": [
                {"platform": "京东", "price": 7799, "fetched_at": "2026-05-01"},
                {"platform": "京东", "price": 7699, "fetched_at": "2026-05-15"},
            ],
        },
    }

    print(f"商品: {mock_state['product_name']}")
    print(f"型号: {len(mock_state['variants'])} 个")
    print(f"价格数据: {sum(len(v) for v in mock_state['price_data'].values())} 条")
    print(f"历史数据: {sum(len(v) for v in mock_state['history_data'].values())} 条")
    print("-" * 70)

    t0 = time.time()
    result = compare_advise_node(mock_state)
    elapsed = time.time() - t0

    print(f"\n{'='*70}")
    print("【对比报告】")
    print("=" * 70)
    print(result["comparison_report"])
    print()
    print("=" * 70)
    print("【购买建议】")
    print("=" * 70)
    print(result["recommendation"])
    if result.get("errors"):
        print(f"\n错误: {result['errors']}")

    # 验证 trend_data
    print(f"\n{'='*70}")
    print("【可视化数据 trend_data】")
    print("=" * 70)
    td = result.get("trend_data", {})
    if td:
        pc = td.get("platformComparison")
        if pc:
            print(f"\n--- 平台比价柱状图 ---")
            print(f"  图例: {pc.get('legend', {}).get('data', [])}")
            print(f"  X轴: {pc.get('xAxis', {}).get('data', [])}")
            for s in pc.get("series", []):
                print(f"  {s['name']}: {s['data']}")

        ph = td.get("priceHistory")
        if ph:
            print(f"\n--- 历史价格折线图 ---")
            print(f"  图例: {ph.get('legend', {}).get('data', [])}")
            print(f"  X轴: {ph.get('xAxis', {}).get('data', [])}")
            for s in ph.get("series", []):
                print(f"  {s['name']}: {s['data']}")
    else:
        print("  ⚠ trend_data 为空（可能是 mock 模式未传递）")

    # 断言验证
    assert result.get("trend_data") is not None, "trend_data 不应为 None"
    if td:
        pc = td.get("platformComparison")
        if pc:
            assert len(pc.get("series", [])) > 0, "柱状图应有至少一条 series"
            print("\n✅ trend_data 验证通过")
    print(f"\n耗时: {elapsed:.1f}s")
