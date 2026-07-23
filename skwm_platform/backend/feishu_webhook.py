#!/usr/bin/env python3
"""
SKWM 飞书自建应用机器人 — Webhook 模式
====================================
无需 lark-oapi，纯 requests + 公开HTTPS URL
"""
import os, json, logging, re, time, hashlib, requests as _req
from pathlib import Path

logger = logging.getLogger("skwm.feishu")

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE = "https://open.feishu.cn/open-apis"

SEDIMENT_DIR = Path(__file__).parent / "output" / "graphrag_evidence" / "sediment"
SEDIMENT_DIR.mkdir(parents=True, exist_ok=True)

# ── Token 缓存 ──
_token_cache = {"token": "", "expires_at": 0}

def _get_tenant_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    try:
        resp = _req.post(f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        data = resp.json()
        token = data.get("tenant_access_token", "")
        expire = data.get("expire", 7200)
        if token:
            _token_cache["token"] = token
            _token_cache["expires_at"] = now + expire
            return token
        logger.error(f"Token获取失败: {data}")
    except Exception as e:
        logger.error(f"Token异常: {e}")
    return ""

def _reply_to_chat(chat_id: str, text: str):
    """回复消息到群/私聊"""
    token = _get_tenant_token()
    if not token:
        logger.error("无token，无法回复")
        return {"error": "no_token"}
    try:
        resp = _req.post(
            f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"receive_id": chat_id, "msg_type": "text",
                  "content": json.dumps({"text": text}, ensure_ascii=False)},
            timeout=10)
        result = resp.json()
        code = result.get("code", -1)
        if code != 0:
            logger.warning(f"回复失败 code={code} msg={result.get('msg','')}")
        return result
    except Exception as e:
        logger.error(f"回复异常: {e}")
        return {"error": str(e)}


def handle_webhook(body: dict) -> dict:
    """飞书事件回调入口（供 app_legacy.py 调用）"""
    # URL 验证
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}

    # 事件回调
    event = body.get("event", {})
    header = body.get("header", {})

    # 去重：按 event_id
    event_id = header.get("event_id") or body.get("event_id", "")
    if event_id:
        # 简单去重（内存中，重启后重置）
        if hasattr(handle_webhook, "_seen"):
            if event_id in handle_webhook._seen:
                return {"msg": "duplicate"}
        else:
            handle_webhook._seen = set()
        handle_webhook._seen.add(event_id)

    event_type = header.get("event_type", "") or body.get("type", "")
    logger.info(f"📩 事件: {event_type} id={event_id[:12] if event_id else '?'}")

    if event_type != "im.message.receive_v1":
        return {"msg": f"ignore_{event_type}"}

    message = event.get("message", {})
    chat_type = message.get("chat_type", "")
    msg_type = message.get("msg_type", "")
    content_str = message.get("content", "{}")
    chat_id = message.get("chat_id", "")
    sender = message.get("sender", {})

    logger.info(f"  类型: {chat_type}/{msg_type} 群: {chat_id[:12] if chat_id else '?'}")

    # 解析 content
    try:
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
    except json.JSONDecodeError:
        content = {"text": content_str}
    text = content.get("text", "") if isinstance(content, dict) else str(content)

    # 群聊：检查@机器人
    if chat_type == "group":
        mentions = message.get("mentions", [])
        if not mentions:
            logger.debug("  未@机器人，跳过")
            return {"msg": "not_mentioned"}
        # 去掉@占位符
        text = re.sub(r'@_user_\d+\s*', '', text).strip()
        text = re.sub(r'@\S+\s*', '', text).strip()

    if not text:
        return {"msg": "empty_text"}

    logger.info(f"  💬 {text[:50]}...")

    # 调用 GraphRAG
    answer = _generate_answer(text)
    _reply_to_chat(chat_id, answer)
    logger.info(f"  ✅ 已回复")
    return {"msg": "ok"}


def _generate_answer(text: str) -> str:
    try:
        from skwm_graphrag_evidence import GraphRAGAPI
        result = GraphRAGAPI().ask(text)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        confidence = result.get("overall_confidence", 0)
        has_evidence = result.get("has_sufficient_evidence", False)

        if not has_evidence or confidence < 0.3:
            return f"关于「{text}」的查询：知识图谱中未找到充分证据，请换关键词或联系馆员。\n(置信度: {confidence:.0%})"
        src = ""
        if sources:
            src = "\n📎 " + "; ".join(f"[{s.get('type','?')}]{s.get('title','')[:15]}" for s in sources[:3])
        return f"{answer[:1500]}{src}\n📊 置信度: {confidence:.0%}"
    except Exception as e:
        logger.error(f"GraphRAG失败: {e}")
        return f"SKWM 智能服务暂不可用，请稍后再试。"
