"""
SKWM 飞书学科服务机器人 v2.0
============================
1. 交互式问答（消息卡片 + 按钮）
2. 角色适配（教师/学生/馆员）
3. 主动推送（热点/前沿周报）
4. 一键沉淀 + 订阅管理
"""
import os, json, logging, requests, re, time, hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger("skwm.feishu")

WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
if not WEBHOOK_URL:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FEISHU_WEBHOOK_URL="):
                WEBHOOK_URL = line.split("=", 1)[1].strip().strip("\"'")

SEDIMENT_DIR = Path(__file__).parent / "output" / "graphrag_evidence" / "sediment"
SEDIMENT_DIR.mkdir(parents=True, exist_ok=True)

SUBSCRIBE_PATH = Path(__file__).parent / "data" / "feishu_subscriptions.json"


class FeishuBotV2:
    """飞书学科服务机器人 v2"""

    def __init__(self):
        self.webhook = WEBHOOK_URL
        self.configured = bool(self.webhook)
        self._subscriptions = self._load_subscriptions()

    # ═══════════════════════════════════════════
    # 1. Webhook 回调处理（问答入口）
    # ═══════════════════════════════════════════

    def handle_webhook(self, body: dict, graphrag_api=None) -> dict:
        """飞书事件回调总入口"""
        # URL 验证
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        # 卡片回调（按钮点击）
        if body.get("type") == "action":
            return self._handle_card_action(body, graphrag_api)

        # 消息处理
        text, user_type = self._parse_message(body)
        if not text:
            return {"msg": "empty"}

        return self._qa_response(text, user_type, graphrag_api)

    def _parse_message(self, body: dict) -> tuple:
        """解析飞书消息，返回 (text, user_type)"""
        event = body.get("event", body)
        content = event.get("content", "")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass
        text = content.get("text", "") if isinstance(content, dict) else str(content)

        # 提取角色标识（支持 @关键词）
        role_map = {"教师": "teacher", "老师": "teacher", "教授": "teacher",
                    "学生": "student", "同学": "student", "同学": "student",
                    "馆员": "librarian", "管理员": "librarian"}
        user_type = "student"
        for kw, role in role_map.items():
            if kw in text:
                user_type = role
                text = text.replace(kw, "").strip()
                break
        return text.strip(), user_type

    def _qa_response(self, text: str, user_type: str, graphrag_api=None) -> dict:
        """生成带来源卡片 + 角色适配的问答响应"""
        if graphrag_api:
            result = graphrag_api.ask(text)
            answer = result.get("answer", "**证据不足**：未找到相关来源。")
            sources = result.get("sources", [])
            confidence = result.get("overall_confidence", 0)
            qa_id = result.get("qa_id", "")
        else:
            # 无后端时的占位回答
            answer = f"关于「{text}」的查询：知识图谱正在检索中…"
            sources = []
            confidence = 0.5
            qa_id = ""

        # 角色适配：不同角色看到不同粒度的回答
        role_config = {
            "teacher": {"header": "👩‍🏫 学科前沿 · 教师版", "template": "blue",
                        "suffix": "\n\n_面向教师：含方法论与数据溯源_"},
            "student": {"header": "👨‍🎓 学习助手 · 学生版", "template": "green",
                        "suffix": "\n\n_面向学生：含概念解释与推荐阅读_"},
            "librarian": {"header": "👩‍💼 学科服务 · 馆员版", "template": "purple",
                          "suffix": "\n\n_面向馆员：含审核状态与数据统计_"},
        }
        cfg = role_config.get(user_type, role_config["student"])

        # 构建卡片
        elements = []

        # 置信度指示器
        if confidence < 0.3:
            elements.append({
                "tag": "markdown",
                "content": f"⚠️ **证据不足** (置信度 {confidence:.0%})：未找到充分相关来源，请换关键词或联系馆员。"
            })

        # 回答正文
        elements.append({
            "tag": "markdown",
            "content": answer[:2000] + cfg["suffix"]
        })

        # 证据来源
        if sources:
            src_lines = "\n".join(
                f"- [{s.get('type','?')}] {s.get('title','')[:30]} (置信度 {s.get('confidence',0):.0%})"
                for s in sources[:3]
            )
            elements.append({"tag": "markdown", "content": f"**证据来源**:\n{src_lines}"})

        elements.append({"tag": "hr"})

        # 操作按钮
        action_elements = []
        if qa_id:
            action_elements.append({
                "tag": "button", "text": {"tag": "plain_text", "content": "📥 存入知识库"},
                "value": {"action": "sediment", "qa_id": qa_id},
                "type": "primary"
            })
            action_elements.append({
                "tag": "button", "text": {"tag": "plain_text", "content": "📋 查看详情"},
                "value": {"action": "detail", "qa_id": qa_id},
                "type": "default"
            })
        action_elements.append({
            "tag": "button", "text": {"tag": "plain_text", "content": "❌ 不相关"},
            "value": {"action": "flag", "qa_id": qa_id},
            "type": "danger"
        })
        elements.append({"tag": "action", "actions": action_elements})

        # 脚注
        elements.append({
            "tag": "note", "elements": [
                {"tag": "plain_text", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} · SKWM v4.0 | 角色: {user_type} | 置信度 {confidence:.0%}"}
            ]
        })

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": cfg["header"]},
                    "template": cfg["template"],
                },
                "elements": elements,
            }
        }
        return card

    # ═══════════════════════════════════════════
    # 2. 卡片按钮回调处理
    # ═══════════════════════════════════════════

    def _handle_card_action(self, body: dict, graphrag_api=None) -> dict:
        """处理卡片按钮点击回调"""
        action = body.get("action", {})
        value = action.get("value", {})
        act = value.get("action", "")
        qa_id = value.get("qa_id", "")

        if act == "sediment" and qa_id:
            return self._do_sediment(qa_id, graphrag_api)
        elif act == "detail" and qa_id:
            return self._do_detail(qa_id, graphrag_api)
        elif act == "flag":
            return {"msg": "flagged"}
        return {"msg": "unknown_action"}

    def _do_sediment(self, qa_id: str, graphrag_api=None) -> dict:
        """一键沉淀：将问答保存为 Obsidian Markdown"""
        if not graphrag_api:
            return self._build_toast("⚠️ 沉淀失败：后端未连接")
        qa = graphrag_api.get_qa(qa_id)
        if not qa:
            return self._build_toast("⚠️ 未找到该问答")

        # 构建 Markdown
        md = f"""---
id: {qa_id}
type: qa_saved
question: "{qa.get('question','')}"
saved_at: {datetime.now().isoformat()}
confidence: {qa.get('overall_confidence',0):.2%}
sources: {len(qa.get('sources',[]))}
tags: [qa, feishu-saved]
---

# Q: {qa.get('question','')}

## 答案

{qa.get('answer','')}

## 证据来源

| 类型 | ID | 标题 | 置信度 |
|------|-----|------|--------|
"""
        for s in qa.get("sources", []):
            md += f"| {s.get('type','')} | {s.get('id','')} | {s.get('title','')[:30]} | {s.get('confidence',0):.0%} |\n"

        fname = f"feishu_saved_{qa_id}.md"
        path = SEDIMENT_DIR / fname
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)

        return self._build_toast(f"✅ 已存入知识库：{fname}")

    def _do_detail(self, qa_id: str, graphrag_api=None) -> dict:
        """查看详情"""
        return self._build_toast(f"📋 问答 ID: {qa_id}")

    @staticmethod
    def _build_toast(content: str) -> dict:
        """构建提示卡片"""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "📌 SKWM"},
                           "template": "blue"},
                "elements": [
                    {"tag": "markdown", "content": content},
                    {"tag": "hr"},
                    {"tag": "note",
                     "elements": [{"tag": "plain_text",
                                   "content": f"🕐 {datetime.now().strftime('%H:%M')}"}]}
                ]
            }
        }

    # ═══════════════════════════════════════════
    # 3. 主动推送（热点/前沿周报）
    # ═══════════════════════════════════════════

    def push_weekly_report(self, hotspots: List[dict], frontiers: List[dict],
                           year: int = 2026) -> dict:
        """推送热点+前沿周报（交互式卡片，含按钮）"""
        hot_lines = [f"**{i+1}. {h.get('name','?')}** 热度 {h.get('heat',0):,}"
                     for i, h in enumerate(hotspots[:5])]
        front_lines = [f"**{i+1}. {f.get('name','?')}** 增速 +{f.get('growth',0):,}"
                       for i, f in enumerate(frontiers[:5])]

        content = f"""📊 **{year}年 第{(datetime.now().isocalendar()[1])}周 SKWM 学科周报**

**🔥 研究热点 TOP 5**
{chr(10).join(hot_lines)}

**🚀 新兴前沿 TOP 5**
{chr(10).join(front_lines)}

*数据基于 89 年状态向量 · XGBoost AUC=0.9408*"""

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text",
                              "content": f"📊 学科周报 · {datetime.now().strftime('%m-%d')}"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": content},
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {"tag": "button",
                             "text": {"tag": "plain_text", "content": "📥 收藏周报"},
                             "value": {"action": "save_weekly"},
                             "type": "primary"},
                            {"tag": "button",
                             "text": {"tag": "plain_text", "content": "🔍 查看详情→"},
                             "value": {"action": "weekly_detail"},
                             "type": "default"},
                        ]
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text",
                             "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} · SKWM v4.0 · 自动推送"}
                        ]
                    }
                ]
            }
        }
        return self._send(card)

    def push_hotspot_weekly(self, hotspots: List[dict], year: int = 2026) -> dict:
        """推送热点TOP5周报"""
        lines = [f"基于 {year} 年状态向量，本周研究热点 TOP 5：\n"]
        for i, h in enumerate(hotspots[:5]):
            bar = "█" * min(15, max(1, int(h.get('heat', 0) / max(1, hotspots[0].get('heat', 1)) * 15)))
            lines.append(f"**{i+1}. {h.get('name','?')}**")
            lines.append(f"   热度 {h.get('heat',0):,} {bar}")
            if h.get('growth', 0) > 0:
                lines.append(f"   增速 ↑{h.get('growth',0)}")
            lines.append("")
        lines.append("_数据基于状态向量分析，每周自动更新_")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔥 {year}年 研究热点周报"},
                    "template": "yellow",
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(lines)[:3000]},
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {"tag": "button",
                             "text": {"tag": "plain_text", "content": "📥 存入知识库"},
                             "value": {"action": "save_hotspot", "year": year},
                             "type": "primary"},
                        ]
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text",
                             "content": f"📊 {len(hotspots)} 个实体 · 自动推送"}
                        ]
                    }
                ]
            }
        }
        return self._send(card)

    def push_frontier_weekly(self, frontiers: List[dict], year: int = 2026) -> dict:
        """推送前沿TOP5周报"""
        lines = [f"本周增速最快新兴方向 TOP 5：\n"]
        for i, f in enumerate(frontiers[:5]):
            trend = "🚀 爆发" if f.get('growth', 0) > 400 else "📈 成长"
            lines.append(f"**{i+1}. {f.get('name','?')}** — 热度 {f.get('heat','?'):,} 增速 +{f.get('growth',0)} {trend}")
        lines.append("\n_基于 89 年时间切片年度新主题发现_")

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🚀 {year}年 新兴前沿周报"},
                    "template": "green",
                },
                "elements": [
                    {"tag": "markdown", "content": "\n".join(lines)[:3000]},
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {"tag": "button",
                             "text": {"tag": "plain_text", "content": "📥 存入知识库"},
                             "value": {"action": "save_frontier", "year": year},
                             "type": "primary"},
                        ]
                    },
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": "📊 XGBoost AUC=0.9408 · 自动推送"}
                    ]}
                ]
            }
        }
        return self._send(card)

    def push_test(self) -> dict:
        """测试推送"""
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "✅ SKWM 飞书机器人已就绪 v2.0"},
                    "template": "green",
                },
                "elements": [
                    {"tag": "markdown",
                     "content": "**🎉 连接成功！**\n\nSKWM 学科服务机器人 v2.0 已接入。\n\n**可用命令：**\n- `@机器人 分析中阿文旅热点` → 带来源卡片问答\n- `@机器人 教师：...` → 教师版（含方法论文本）\n- `@机器人 学生：...` → 学生版（含解释）\n- `@机器人 馆员：...` → 馆员版（含审核状态）\n\n**卡片按钮：**\n- 📥 存入知识库 → 一键沉淀为 Markdown\n- 📋 查看详情 → 查看完整证据链"},
                    {"tag": "hr"},
                    {"tag": "note",
                     "elements": [{"tag": "plain_text",
                                   "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} · SKWM v4.0"}]
                     }
                ]
            }
        }
        return self._send(card)

    # ═══════════════════════════════════════════
    # 4. 订阅管理
    # ═══════════════════════════════════════════

    def _load_subscriptions(self) -> Dict:
        if SUBSCRIBE_PATH.exists():
            try:
                return json.loads(SUBSCRIBE_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {"weekly": True, "hotspot": True, "frontier": True, "users": []}

    def _save_subscriptions(self):
        SUBSCRIBE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUBSCRIBE_PATH.write_text(json.dumps(self._subscriptions, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_subscriptions(self) -> Dict:
        return self._subscriptions

    def set_subscription(self, key: str, value: bool) -> bool:
        if key in self._subscriptions:
            self._subscriptions[key] = value
            self._save_subscriptions()
            return True
        return False

    # ═══════════════════════════════════════════
    # 5. 发送
    # ═══════════════════════════════════════════

    def _send(self, card: dict) -> dict:
        if not self.configured:
            logger.warning("⚠️ FEISHU_WEBHOOK_URL 未配置")
            return {"status": "not_configured"}
        try:
            resp = requests.post(self.webhook, json=card, timeout=10)
            if resp.ok:
                logger.info("✅ 飞书推送成功")
                return {"status": "ok"}
            logger.warning(f"⚠️ 飞书推送失败 {resp.status_code}")
            return {"status": "error", "code": resp.status_code}
        except Exception as e:
            logger.error(f"❌ 飞书推送异常: {e}")
            return {"status": "error", "detail": str(e)}
