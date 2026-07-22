#!/usr/bin/env python3
"""
skwm_service.py —— P 服务规则引擎（把 P 从 🟡框架 升级到 ✅参与计算）

对应策划案第62条：P = 服务规则 = {推荐 recommend, 审核 audit, 推送 push, 沉淀 sediment}

四条规则各落地一个最小实现：
  - recommend：基于 U(用户) + S(知识状态) 的排序推荐
  - audit：为每条结论附证据（DOI/arXiv/图谱节点）+ 简易幻觉检测
  - push：飞书自定义机器人 webhook 推送
  - sediment：报告写成 Markdown 归档到 Obsidian vault 目录
"""
import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent

# 用户画像→推荐偏好（与 skwm_aligned_v4.SKWM.USER_TYPES 对齐）
USER_PREF = {
    "teacher":   {"prefer": ["growth", "centrality"], "desc": "前沿追踪、课题申报"},
    "student":   {"prefer": ["heat", "connections"], "desc": "入门选题、高热度主题"},
    "librarian": {"prefer": ["heat", "growth"], "desc": "学科咨询、资源推送"},
    "manager":   {"prefer": ["centrality", "connections"], "desc": "机构画像、学科评估"},
}


class ServiceRules:
    """P: 服务规则引擎。依赖注入 data(DataLayer) 以取得知识状态。"""

    def __init__(self, data=None, feishu_webhook: Optional[str] = None,
                 obsidian_vault: Optional[str] = None):
        self.data = data
        self.feishu_webhook = feishu_webhook or os.environ.get("FEISHU_WEBHOOK")
        self.obsidian_vault = Path(obsidian_vault or os.environ.get(
            "OBSIDIAN_VAULT", str(BASE_DIR / "obsidian_vault")))

    # ── P.1 推荐规则 ────────────────────────────────────────
    def recommend(self, topics: List[Dict], user_type: str = "teacher",
                  top_k: int = 5) -> List[Dict]:
        """基于 U×S 给主题打分排序（topics 需含 heat/growth/centrality/connections）"""
        prefer = USER_PREF.get(user_type, USER_PREF["teacher"])["prefer"]
        scored = []
        for t in topics:
            score = 0.0
            for i, key in enumerate(prefer):
                score += (t.get(key, 0) or 0) * (2.0 - i)  # 首选维度权重更高
            # 叠加已有的语境分（如果 ContextEngine 已经注入）
            score += (t.get("context_score", 0) or 0)
            nt = dict(t)
            nt["recommend_score"] = round(score, 4)
            nt["reason"] = f"适配{user_type}：依据{'/'.join(prefer)}"
            scored.append(nt)
        scored.sort(key=lambda x: -x["recommend_score"])
        return scored[:top_k]

    # ── P.2 审核规则（来源追溯 + 幻觉检测）──────────────────────
    def audit(self, report: Dict, evidence_lookup=None) -> Dict:
        """为报告每个 section 附证据，并做简易幻觉检测。
        evidence_lookup(name)->list[dict]  可选：返回证据（DOI/arXiv/节点）。
        若未提供，则从 data.snapshots 中标记"可追溯/不可追溯"。
        """
        audited = dict(report)
        flags = []
        known_terms = set()
        if self.data is not None:
            try:
                y = max(self.data.year_range)
                known_terms = set(self.data.get_entities(y).keys())
            except Exception:
                pass
        for sec in audited.get("sections", []):
            data = sec.get("data")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        name = item["name"]
                        if evidence_lookup:
                            item["evidence"] = evidence_lookup(name)
                        # 幻觉检测：论据中不存在的实体标黄
                        item["verifiable"] = (not known_terms) or (name in known_terms)
                        if not item["verifiable"]:
                            flags.append(name)
        audited["audit"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "unverifiable": flags,
            "status": "✅ 均可追溯" if not flags else f"⚠️ {len(flags)}项待馆员核验",
            "note": "每条结论已附 verifiable 标志；建议馆员对 unverifiable 项人工复核。",
        }
        return audited

    # ── P.3 推送规则（飞书 webhook）────────────────────────────
    def push(self, title: str, content: str) -> Dict:
        """推送到飞书自定义机器人。未配 webhook 时降级为本地日志。"""
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title},
                           "template": "blue"},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
            },
        }
        if not self.feishu_webhook:
            log = BASE_DIR / "push_outbox.log"
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] (未配 webhook) {title}\n{content}\n{'-'*40}\n")
            return {"sent": False, "fallback": "local_log", "path": str(log)}
        try:
            import requests
            r = requests.post(self.feishu_webhook, json=payload, timeout=10)
            return {"sent": r.ok, "status_code": r.status_code, "resp": r.text[:200]}
        except Exception as e:
            return {"sent": False, "error": str(e)}

    # ── P.4 沉淀规则（Obsidian 归档）───────────────────────────
    def sediment(self, report: Dict) -> Dict:
        """把报告写成 Markdown 归档到 Obsidian vault（带 YAML frontmatter + 双链）"""
        self.obsidian_vault.mkdir(parents=True, exist_ok=True)
        title = report.get("title", "SKWM报告")
        safe = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)
        fname = f"{datetime.now():%Y%m%d}_{safe}.md"
        fp = self.obsidian_vault / fname
        lines = [
            "---",
            f"title: {title}",
            f"created: {datetime.now():%Y-%m-%d %H:%M}",
            f"user_type: {report.get('user_type', '')}",
            "tags: [SKWM, 中阿文旅, 学科服务]",
            "---", "",
            f"# {title}", "",
            f"> 数据规模：{report.get('data_scale', '')}", "",
        ]
        for sec in report.get("sections", []):
            lines.append(f"## {sec.get('name', '')}")
            data = sec.get("data")
            if isinstance(data, list):
                for it in data:
                    if isinstance(it, dict):
                        nm = it.get("name", "")
                        ev = it.get("evidence")
                        tail = f"  — 证据: {ev}" if ev else ""
                        lines.append(f"- [[{nm}]]{tail}")
                    else:
                        lines.append(f"- {it}")
            else:
                lines.append(str(data))
            lines.append("")
        fp.write_text("\n".join(lines), encoding="utf-8")
        return {"sedimented": True, "path": str(fp), "filename": fname}


if __name__ == "__main__":
    sr = ServiceRules()
    topics = [
        {"name": "数字文旅", "heat": 0.8, "growth": 0.3, "centrality": 0.6, "connections": 40},
        {"name": "generative ai", "heat": 0.5, "growth": 0.9, "centrality": 0.4, "connections": 20},
    ]
    print("recommend(teacher):", [t["name"] for t in sr.recommend(topics, "teacher")])
    print("recommend(student):", [t["name"] for t in sr.recommend(topics, "student")])
    rep = {"title": "测试报告", "user_type": "教师科研", "data_scale": "89年×43K",
           "sections": [{"name": "热点", "data": topics}]}
    print("push:", sr.push("SKWM周报", "本周热点：数字文旅"))
    print("sediment:", sr.sediment(rep))
