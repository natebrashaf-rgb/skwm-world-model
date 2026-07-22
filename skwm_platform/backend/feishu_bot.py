"""
飞书机器人 — 双模式
1. Passive: Webhook 回调 → 回答问题（走 GraphRAG）
2. Active: 主动推送报告/热点/前沿到飞书群

配置:
  环境变量 FEISHU_WEBHOOK_URL = https://open.feishu.cn/open-apis/bot/v2/hook/xxx
  或 .env 文件
"""
import os, json, logging, requests
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger("skwm.feishu")


def _read_webhook_url() -> str:
    """读取飞书 Webhook URL，优先级: 环境变量 > .env 文件"""
    url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if url:
        return url
    # 尝试从 .env 读取
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FEISHU_WEBHOOK_URL="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


class FeishuBot:
    """飞书机器人: 被动问答 + 主动推送"""

    TEMPLATE_MAP = {
        "blue": "blue",
        "green": "green",
        "red": "red",
        "purple": "purple",
        "yellow": "yellow",
        "grey": "grey",
    }

    def __init__(self):
        self.webhook_url = _read_webhook_url()
        self._configured = bool(self.webhook_url)
        self.push_count = 0
        if not self._configured:
            logger.warning("⚠️ FEISHU_WEBHOOK_URL 未配置 — 推送进入日志回退模式")

    # ═══════════════════════════════════════════════════
    #  Passive: Webhook 回调处理
    # ═══════════════════════════════════════════════════

    def handle(self, body: dict, graph_rag) -> dict:
        """处理飞书 Webhook 回调（消息接收）"""
        # URL 验证
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        text = self._extract_text(body)
        if not text:
            return {"msg": "empty"}

        result = graph_rag.answer(question=text)
        return self._build_card(result)

    def _extract_text(self, body: dict) -> str:
        """从飞书回调 body 中提取用户消息文本"""
        event = body.get("event", {})
        content = event.get("content", body.get("content", ""))
        if isinstance(content, str):
            try:
                return json.loads(content).get("text", "")
            except json.JSONDecodeError:
                return content
        return ""

    def _build_card(self, result: dict) -> dict:
        """构建飞书消息卡片响应"""
        answer = result.get("answer", "")[:2000]
        confidence = int(result.get("confidence", 0) * 100)
        rule_triggered = result.get("rule_triggered", False)

        elements = [
            {"tag": "markdown", "content": answer},
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"🧠 SKWM 世界模型 | 置信度 {confidence}% | {datetime.now().strftime('%H:%M')}"}
                ]
            }
        ]

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "🧠 SKWM 智能助手"},
                    "template": "blue",
                },
                "elements": elements,
            },
        }

    # ═══════════════════════════════════════════════════
    #  Active: 主动推送（定时发到飞书群）
    # ═══════════════════════════════════════════════════

    def _send(self, card: dict) -> dict:
        """发送卡片消息到飞书 Webhook"""
        if not self._configured:
            self.push_count += 1
            entry = f"[{datetime.now().isoformat()}] (未配 webhook) [推送#{self.push_count}] {card.get('header',{}).get('title',{}).get('content','')[:40]}"
            self._log_fallback(entry)
            return {"status": "fallback_log", "count": self.push_count}

        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            if resp.ok:
                self.push_count += 1
                logger.info(f"✅ 飞书推送成功 #{self.push_count}")
                return {"status": "ok", "push_count": self.push_count}
            else:
                logger.warning(f"⚠️ 飞书推送失败 HTTP {resp.status_code}: {resp.text[:200]}")
                return {"status": "error", "code": resp.status_code, "detail": resp.text[:200]}
        except requests.RequestException as e:
            logger.error(f"❌ 飞书推送异常: {e}")
            return {"status": "exception", "detail": str(e)}

    def _log_fallback(self, entry: str):
        """当 webhook 未配置时，写日志文件代替推送"""
        log_path = Path(__file__).parent / "push_outbox.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n" + "-" * 40 + "\n")

    # ─── 卡片模板 ─────────────────────────────────

    def push_report(self, title: str, content: str, data_summary: str = "",
                    user_type: str = "librarian") -> dict:
        """推送完整报告卡片"""
        user_icons = {"teacher": "👩‍🏫", "student": "👨‍🎓", "librarian": "👩‍💼", "manager": "👨‍💼"}
        icon = user_icons.get(user_type, "📋")

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"{icon} {title}"},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": content[:3000]},
                {"tag": "hr"},
            ]
        }

        if data_summary:
            card["elements"].append({
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"📊 {data_summary}"}
                ]
            })

        card["elements"].append({
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} · SKWM 世界模型"}
            ]
        })

        return self._send(card)

    def push_hotspot_alert(self, hotspots: List[dict], year: int) -> dict:
        """推送热点排行榜卡片"""
        lines = [f"基于 {year} 年状态向量，当前研究热点 TOP 10：\n"]
        for i, h in enumerate(hotspots[:10]):
            bar = "█" * min(15, max(1, int(h['heat'] / max(1, hotspots[0]['heat']) * 15)))
            lines.append(f"**{i+1}. {h['name']}**")
            lines.append(f"   热度 {h['heat']:,} {bar}")
            if h.get('growth', 0) > 0:
                lines.append(f"   增速 ↑{h['growth']}")
            lines.append("")

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"🔥 {year}年 研究热点周报"},
                "template": "yellow",
            },
            "elements": [
                {"tag": "markdown", "content": "\n".join(lines)[:3000]},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"📊 基于 {year}年 {len(hotspots)} 个实体的状态向量 | 自动推送"}
                    ]
                },
            ]
        }
        return self._send(card)

    def push_frontier_alert(self, frontier: List[dict], year: int) -> dict:
        """推送新兴前沿卡片"""
        lines = [f"增速最快的 NEW 方向 TOP 10：\n"]
        for i, e in enumerate(frontier[:10]):
            trend = "🚀 爆发" if e.get('growth', 0) > 400 else "📈 成长" if e.get('growth', 0) > 200 else "📊 稳定"
            lines.append(f"**{i+1}. {e['name']}** — 热度 {e.get('heat','?'):,} 增速 +{e.get('growth',0)} {trend}")
        lines.append("")
        lines.append("_数据基于 89 年时间切片，年度新主题发现_")

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚀 {year}年 新兴前沿发现"},
                "template": "green",
            },
            "elements": [
                {"tag": "markdown", "content": "\n".join(lines)[:3000]},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"📊 XGBoost AUC=0.9408 | 自动推送"}
                    ]
                },
            ]
        }
        return self._send(card)

    def push_daily_briefing(self, hotspots: List[dict], frontier: List[dict],
                            total_entities: int = 0, total_edges: int = 0) -> dict:
        """推送每日简报卡片"""
        # 热点 Top 3
        hot_lines = []
        for h in hotspots[:3]:
            hot_lines.append(f"  **{h['name']}** 热度 {h['heat']:,}")

        # 前沿 Top 3
        front_lines = []
        for e in frontier[:3]:
            front_lines.append(f"  **{e['name']}** 增速 +{e.get('growth',0)}")

        content = f"""📅 **SKWM 每日简报**

🔥 **热点 TOP 3**
{chr(10).join(hot_lines)}

🚀 **前沿 TOP 3**
{chr(10).join(front_lines)}

📊 **数据规模**
  实体: {total_entities:,} | 关系: {total_edges:,}
  时间跨度: 89 年 | XGBoost AUC=0.9408"""

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"📅 SKWM 每日简报 · {datetime.now().strftime('%m-%d')}"},
                "template": "purple",
            },
            "elements": [
                {"tag": "markdown", "content": content},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "🕐 自动推送 · 科学知识世界模型 v4.0"}
                    ]
                },
            ]
        }
        return self._send(card)

    def push_test(self) -> dict:
        """推送测试消息（验证配置是否生效）"""
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": "✅ SKWM 飞书机器人已就绪"},
                "template": "green",
            },
            "elements": [
                {"tag": "markdown", "content": "**🎉 连接成功！**\n\nSKWM 世界模型 v4.0 已接入飞书群。\n\n可用功能：\n- 🔥 热点推送（每日/每周）\n- 🚀 前沿发现推送\n- 📋 学科服务报告推送\n- 💬 @机器人 提问回答\n\n试试对我说：\n- 「分析近年中阿文旅热点」\n- 「未来什么方向会火？」\n- 「给我出一份学科报告」"},
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} · SKWM 世界模型"}
                    ]
                },
            ]
        }
        return self._send(card)

    def is_configured(self) -> bool:
        return self._configured
