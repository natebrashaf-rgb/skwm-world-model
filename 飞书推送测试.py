"""
飞书推送测试 — 命令行模式
直接测试推送热点/简报到飞书群，无需启动 API 服务

用法:
  python 飞书推送测试.py hotspot     # 推送热点
  python 飞书推送测试.py briefing    # 推送简报
  python 飞书推送测试.py test        # 测试连接
  python 飞书推送测试.py all         # 全部跑一遍
"""
import sys, os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from feishu_bot import FeishuBot
from skwm_aligned_v4 import DataLayer

# 加载数据
print("📦 加载世界模型数据...")
DATA = DataLayer().load(verbose=False)
bot = FeishuBot()

y = max(DATA.year_range) if DATA.year_range else 2026


def test_hotspot():
    print("\n🔥 推送热点...")
    hot = DATA.get_hot_topics(y, 10)
    r = bot.push_hotspot_alert(hot, y)
    print(f"  结果: {r}")
    return r


def test_briefing():
    print("\n📅 推送简报...")
    hot = DATA.get_hot_topics(y, 3)
    em = DATA.get_emerging(y, 3)
    total_nodes = sum(s.get("n_nodes", 0) for s in DATA.snapshots.values())
    total_edges = sum(s.get("n_edges", 0) for s in DATA.snapshots.values())
    r = bot.push_daily_briefing(hot, em, total_nodes, total_edges)
    print(f"  结果: {r}")
    return r


def test_frontier():
    print("\n🚀 推送前沿...")
    em = DATA.get_emerging(y, 10)
    r = bot.push_frontier_alert(em, y)
    print(f"  结果: {r}")
    return r


def test_connection():
    print("\n✅ 测试连接...")
    r = bot.push_test()
    print(f"  结果: {r}")
    return r


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "all":
        test_connection()
        test_hotspot()
        test_frontier()
        test_briefing()
    elif mode == "hotspot":
        test_hotspot()
    elif mode == "briefing":
        test_briefing()
    elif mode == "frontier":
        test_frontier()
    elif mode == "test":
        test_connection()
    else:
        print(f"用法: python {sys.argv[0]} [hotspot|briefing|frontier|test|all]")
        sys.exit(1)

    if not bot.is_configured():
        print(f"\n⚠️  FEISHU_WEBHOOK_URL 未配置")
        print(f"   推送已写入 push_outbox.log（日志回退模式）")
        print(f"   配置后自动生效 → 设置方法见 .env.example")
    else:
        print(f"\n✅ 推送成功！共推送 {bot.push_count} 条消息到飞书群")
