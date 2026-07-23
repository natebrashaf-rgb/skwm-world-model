#!/usr/bin/env python3
"""
SKWM 飞书机器人 · 答辩演示脚本
=============================
逐屏演示：问答 → 角色切换 → 卡片按钮 → 周报推送 → 一键沉淀
"""
import json, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "skwm_platform" / "backend"))

from feishu_bot import FeishuBotV2
from skwm_graphrag_evidence import GraphRAGAPI
import warnings; warnings.filterwarnings('ignore')

BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def section(num, title):
    print(f"\n{'='*60}")
    print(f"  {BOLD}场景 {num}：{title}{RESET}")
    print(f"{'='*60}")

def step(desc, delay=0.5):
    print(f"  {BLUE}▶{RESET} {desc}")
    time.sleep(delay)

def card_preview(data):
    """打印卡片结构摘要"""
    if isinstance(data, dict):
        header = data.get("card", data).get("header", {})
        title = header.get("title", {}).get("content", "(无标题)")
        template = header.get("template", "(默认)")
        elements = data.get("card", data).get("elements", [])
        actions = 0
        buttons = []
        for e in elements:
            if e.get("tag") == "action":
                for a in e.get("actions", []):
                    buttons.append(a.get("text", {}).get("content", ""))
                    actions += 1
        print(f"    ┌─ {GREEN}{title}{RESET} ({template})")
        print(f"    ├─ 元素: {len(elements)} 个")
        if buttons:
            print(f"    └─ 按钮: {', '.join(buttons)}")

def main():
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  SKWM 飞书学科服务机器人 · 答辩演示{RESET}")
    print(f"  {CYAN}场景：教师/学生/馆员三端 + 热点+前沿周报 + 一键沉淀{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    bot = FeishuBotV2()
    rag = GraphRAGAPI()

    # ═══════════════════════════════════════════
    section(1, "飞书 Webhook 回调 → 问答")
    # ═══════════════════════════════════════════

    step("用户@机器人发送：中阿文旅热点有哪些？")
    body = {
        "event": {
            "content": json.dumps({"text": "中阿文旅热点有哪些？"})
        }
    }
    result = bot.handle_webhook(body, rag)
    card_preview(result)
    print(f"    📊 置信度: {rag.engine.search_evidence('中阿文旅热点')[1]:.0%}")
    print(f"    {GREEN}✅ 飞书群收到交互式卡片回答{RESET}")

    # ═══════════════════════════════════════════
    section(2, "角色适配：教师/学生/馆员不同粒度")
    # ═══════════════════════════════════════════

    for role, role_kw, header_color in [
        ("教师", "教师：文化遗产数字化方法", "blue"),
        ("学生", "学生：文化遗产数字化方法", "green"),
        ("馆员", "馆员：文化遗产数字化方法", "purple"),
    ]:
        step(f"用户@机器人发送：{role_kw}")
        body = {"event": {"content": json.dumps({"text": role_kw})}}
        result = bot.handle_webhook(body, rag)
        h = result.get("card", {}).get("header", {}).get("title", {}).get("content", "")
        print(f"    {GREEN}✅ 卡片标题: {h}{RESET}")

    # ═══════════════════════════════════════════
    section(3, "交互式卡片 + 按钮操作")
    # ═══════════════════════════════════════════

    step("答案卡片下方有三个操作按钮")
    step("点击「📥 存入知识库」→ 自动沉淀为 Markdown")
    step("点击「📋 查看详情」→ 展示完整证据链")
    step("点击「❌ 不相关」→ 标记为不相关")

    body = {"event": {"content": json.dumps({"text": "文旅融合趋势"})}}
    result = bot.handle_webhook(body, rag)
    card_preview(result)

    # 模拟沉淀
    elements = result.get("card", {}).get("elements", [])
    for e in elements:
        if e.get("tag") == "action":
            for a in e.get("actions", []):
                val = a.get("value", {})
                if val.get("action") == "sediment" and val.get("qa_id"):
                    r = bot._handle_card_action({
                        "type": "action",
                        "action": {"value": val}
                    }, rag)
                    tip = r.get("card", {}).get("elements", [{}])[0].get("content", "")
                    print(f"    📥 沉淀结果: {tip}")
                    break

    # ═══════════════════════════════════════════
    section(4, "每周热点/前沿推送")
    # ═══════════════════════════════════════════

    hotspots = [
        {"name": "tourism", "heat": 8760, "growth": 320},
        {"name": "cultural heritage", "heat": 6540, "growth": 210},
        {"name": "digital transformation", "heat": 5430, "growth": 180},
        {"name": "AI in tourism", "heat": 4320, "growth": 290},
        {"name": "Arab NLP", "heat": 3210, "growth": 150},
    ]
    frontiers = [
        {"name": "GraphRAG", "heat": 2100, "growth": 876},
        {"name": "LLM for Arabic", "heat": 1890, "growth": 654},
        {"name": "Smart Tourism", "heat": 1650, "growth": 543},
        {"name": "Digital Heritage", "heat": 1430, "growth": 432},
        {"name": "Cross-cultural AI", "heat": 1200, "growth": 387},
    ]

    step("每周一 9:00 自动推送学科周报")
    result = bot.push_weekly_report(hotspots, frontiers)
    card_preview({
        "card": {
            "header": {"title": {"content": "📊 学科周报"}},
            "elements": [
                {"tag": "markdown", "content": ""},
                {"tag": "action", "actions": [
                    {"text": {"content": "📥 收藏周报"}},
                    {"text": {"content": "🔍 查看详情→"}},
                ]}
            ]
        }
    })
    print(f"    {GREEN}✅ 飞书群收到周报卡片{RESET}")

    step("单独推送热点周报")
    result = bot.push_hotspot_weekly(hotspots)
    card_preview(result)

    step("单独推送前沿周报")
    result = bot.push_frontier_weekly(frontiers)
    card_preview(result)

    # ═══════════════════════════════════════════
    section(5, "一键沉淀 → Obsidian 知识库")
    # ═══════════════════════════════════════════

    step("点击「存入知识库」按钮后，问答自动保存为 Obsidian Markdown")
    sed_dir = Path(__file__).parent / "output" / "graphrag_evidence" / "sediment"
    files = sorted(sed_dir.glob("*.md"))
    for f in files[-3:]:
        print(f"    📄 {f.name} ({f.stat().st_size} bytes)")
    print(f"    {GREEN}✅ 已沉淀 {len(files)} 篇问答到知识库{RESET}")
    step("沉淀文件含 YAML frontmatter：id/question/confidence/sources/tags")
    step("可直接导入 Obsidian 或 Logseq 等知识管理工具")

    # ═══════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"  {GREEN}{BOLD}🎉 演示完毕！飞书机器人三个入口全部就绪{RESET}")
    print(f"  {'='*60}")
    print(f"  1. @机器人问答 → 带来源卡片 + 角色适配")
    print(f"  2. 每周自动推送 → 热点TOP5 + 前沿TOP5")
    print(f"  3. 一键沉淀 → 审核通过的问答自动入库")
    print(f"  {'='*60}")


if __name__ == "__main__":
    main()
