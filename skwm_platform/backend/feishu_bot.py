"""
飞书问答机器人 — Webhook + 消息卡片
"""
import os, json, logging
from typing import Optional
from graph_rag import GraphRAG

logger = logging.getLogger("skwm.feishu")


class FeishuBot:
    def __init__(self):
        self.webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
        self.verify_token = os.getenv("FEISHU_VERIFY_TOKEN", "")

    def handle(self, body: dict, graph_rag: GraphRAG) -> dict:
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}
        text = self._extract_text(body)
        if not text:
            return {"msg": "empty"}
        result = graph_rag.answer(question=text)
        return self._build_card(result)

    def _extract_text(self, body: dict) -> str:
        event = body.get("event", {})
        content = event.get("content", body.get("content", ""))
        if isinstance(content, str):
            try:
                return json.loads(content).get("text", "")
            except:
                return content
        return ""

    def _build_card(self, result: dict) -> dict:
        return {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": "🧠 SKWM 智能助手"}, "template": "blue"},
                "elements": [
                    {"tag": "markdown", "content": result.get("answer", "")[:2000]},
                    {"tag": "markdown", "content": f"置信度: {int(result.get('confidence',0)*100)}% | 规则: {'是' if result.get('rule_triggered') else '否'}"},
                ],
            },
        }
