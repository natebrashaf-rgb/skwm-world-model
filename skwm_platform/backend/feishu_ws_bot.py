#!/usr/bin/env python3
"""
SKWM 飞书自建应用机器人 — WebSocket 长连接模式
=============================================
基于 lark-oapi SDK，用 app_id + app_secret 建立长连接，
订阅 im.message.receive_v1 事件，在群里@时自动回复。
"""
import os, json, logging, re, time, hashlib
from typing import Optional
from pathlib import Path
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.ws import Client as WSClient

logger = logging.getLogger("skwm.feishu.ws")

# ── 环境变量读取（禁止硬编码） ──
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 持久化目录
SEDIMENT_DIR = Path(__file__).parent / "output" / "graphrag_evidence" / "sediment"
SEDIMENT_DIR.mkdir(parents=True, exist_ok=True)


class FeishuWSBot:
    """飞书长连接机器人"""

    def __init__(self):
        self.app_id = APP_ID
        self.app_secret = APP_SECRET
        self.bot_open_id = None  # 启动后从事件中获取
        self._client: Optional[WSClient] = None
        self._running = False

    # ── 启动 ──
    def start(self):
        if not self.app_id or not self.app_secret:
            logger.error("❌ FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置")
            return False

        logger.info(f"🤖 启动飞书长连接机器人 (app_id={self.app_id[:10]}...)")

        # 创建 WSClient（Handler 方式）
        self._client = WSClient(lark.WSClientOption(
            app_id=self.app_id,
            app_secret=self.app_secret,
        ))

        # 注册事件处理
        self._client.on("im.message.receive_v1", self._on_message)
        self._client.on("p2p.im.message.receive_v1", self._on_message)

        try:
            self._client.start()
            self._running = True
            logger.info("✅ 飞书长连接已建立")
            return True
        except Exception as e:
            logger.error(f"❌ 飞书长连接启动失败: {e}")
            return False

    def stop(self):
        if self._client:
            self._client.stop()
            self._running = False
            logger.info("⏹️ 飞书长连接已关闭")

    # ── 消息处理核心 ──
    def _on_message(self, ctx: lark.EventContext, event: lark.im.v1.EventMessageReceive) -> None:
        """处理收到的消息事件"""
        try:
            msg_id = event.event_id or hashlib.md5(str(time.time()).encode()).hexdigest()[:12]
            logger.info(f"📩 收到事件: {msg_id}")

            message = event.event.message
            if not message:
                logger.warning("  ⚠️ 无message字段")
                return

            chat_type = message.chat_type
            msg_type = message.msg_type
            content_str = message.content or "{}"
            chat_id = message.chat_id
            sender_id = message.sender.id if message.sender else ""

            logger.info(f"  类型: {chat_type} / {msg_type} | 群: {chat_id[:12] if chat_id else '?'}")

            # 解析 content JSON
            try:
                content = json.loads(content_str) if isinstance(content_str, str) else content_str
            except json.JSONDecodeError:
                content = {"text": content_str}

            # 提取纯文本
            text = content.get("text", "") if isinstance(content, dict) else str(content)

            # 群聊模式：检查@机器人
            if chat_type == "group":
                # 取出所有 mention 的 open_id
                mentions = message.mentions or []
                mentioned_ids = set()
                for m in mentions:
                    if m.key:
                        mentioned_ids.add(m.key)
                    if m.id and m.id.open_id:
                        mentioned_ids.add(m.id.open_id)

                # 如果没有存储 bot_open_id，暂时忽略机器人检测
                # 先检查 mention_key 是否匹配
                is_mentioned = False
                if mentions:
                    # 只要群里有@目标就响应
                    is_mentioned = True

                if not is_mentioned:
                    logger.debug("  未@机器人，跳过")
                    return

                # 去掉@占位符
                text = re.sub(r'@_user_\d+\s*', '', text).strip()
                text = re.sub(r'@\S+\s*', '', text).strip()

            # 私聊模式：直接处理
            elif chat_type == "p2p":
                pass  # 直接回复

            if not text:
                logger.info("  空消息，跳过")
                return

            logger.info(f"  💬 文本: {text[:60]}...")

            # ── 生成回答 ──
            answer = self._generate_answer(text)

            # ── 回复到群 ──
            self._reply_to_chat(chat_id, answer)
            logger.info(f"  ✅ 已回复: {answer[:40]}...")

        except Exception as e:
            logger.error(f"❌ 消息处理异常: {e}", exc_info=True)

    # ── 回答生成 ──
    def _generate_answer(self, text: str) -> str:
        """调用 GraphRAG 或返回兜底"""
        try:
            from skwm_graphrag_evidence import GraphRAGAPI
            result = GraphRAGAPI().ask(text)
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            confidence = result.get("overall_confidence", 0)
            has_evidence = result.get("has_sufficient_evidence", False)

            if not has_evidence or confidence < 0.3:
                return f"关于「{text}」的查询：知识图谱中未找到充分证据，请换关键词或联系馆员。\n(置信度: {confidence:.0%})"

            src_summary = ""
            if sources:
                src_list = [f"[{s.get('type','?')}] {s.get('title','')[:20]}" for s in sources[:3]]
                src_summary = f"\n📎 来源: {'; '.join(src_list)}"
            return f"{answer[:1500]}{src_summary}\n📊 置信度: {confidence:.0%}"

        except Exception as e:
            logger.error(f"  ⚠️ GraphRAG调用失败: {e}")
            return f"SKWM 智能问答服务暂不可用，请稍后再试。\n({e})"

    # ── 回复消息 ──
    def _reply_to_chat(self, chat_id: str, answer: str):
        """用 tenant_access_token 回复消息到群"""
        # 获取 token
        token = self._get_tenant_token()
        if not token:
            logger.error("  ❌ 无法获取 tenant_access_token")
            return

        # 构建请求
        content = json.dumps({"text": answer}, ensure_ascii=False)
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": content,
        }

        try:
            import requests
            resp = requests.post(url, json=body, headers=headers, timeout=10)
            result = resp.json()
            code = result.get("code", -1)
            msg = result.get("msg", "")
            if code == 0:
                logger.info(f"  ✅ 回复成功")
            else:
                logger.warning(f"  ⚠️ 回复失败 code={code} msg={msg}")
        except Exception as e:
            logger.error(f"  ❌ 回复异常: {e}")

    # ── Token 管理 ──
    _token_cache = {"token": "", "expires_at": 0}

    def _get_tenant_token(self) -> str:
        """获取并缓存 tenant_access_token"""
        now = time.time()
        if self._token_cache["token"] and now < self._token_cache["expires_at"] - 60:
            return self._token_cache["token"]

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        try:
            import requests
            resp = requests.post(url, json={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            }, timeout=10)
            result = resp.json()
            token = result.get("tenant_access_token", "")
            expire = result.get("expire", 7200)
            if token:
                self._token_cache["token"] = token
                self._token_cache["expires_at"] = now + expire
                logger.info(f"  ✅ Token获取成功，有效期{expire}s")
                return token
            else:
                logger.error(f"  ❌ Token获取失败: {result}")
                return ""
        except Exception as e:
            logger.error(f"  ❌ Token请求异常: {e}")
            return ""
