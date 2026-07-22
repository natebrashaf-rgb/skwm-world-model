#!/usr/bin/env python3
"""
skwm_service.py —— P 服务规则引擎（增强版：审核风险标注 + KG回写）

对应策划案第62条：P = {推荐 recommend, 审核 audit, 推送 push, 沉淀 sediment}
新增 writeback: 高质量问答回写知识图谱（闭环）
"""
import json, re, os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

BASE_DIR = Path(__file__).parent

USER_PREF = {
    "teacher":   {"prefer": ["growth", "centrality"], "desc": "前沿追踪、课题申报"},
    "student":   {"prefer": ["heat", "connections"], "desc": "入门选题、高热度主题"},
    "librarian": {"prefer": ["heat", "growth"], "desc": "学科咨询、资源推送"},
    "manager":   {"prefer": ["centrality", "connections"], "desc": "机构画像、学科评估"},
}


class ServiceRules:
    """P: 服务规则引擎（增强版）"""

    def __init__(self, data=None, feishu_webhook: Optional[str] = None,
                 obsidian_vault: Optional[str] = None):
        self.data = data
        self.feishu_webhook = feishu_webhook or os.environ.get("FEISHU_WEBHOOK")
        self.obsidian_vault = Path(obsidian_vault or os.environ.get(
            "OBSIDIAN_VAULT", str(BASE_DIR / "obsidian_vault")))

    # ── P.1 推荐 ──────────────────────────────────────────
    def recommend(self, topics: List[Dict], user_type: str = "teacher",
                  top_k: int = 5) -> List[Dict]:
        prefer = USER_PREF.get(user_type, USER_PREF["teacher"])["prefer"]
        scored = []
        for t in topics:
            score = 0.0
            for i, key in enumerate(prefer):
                score += (t.get(key, 0) or 0) * (2.0 - i)
            score += (t.get("context_score", 0) or 0)
            nt = dict(t)
            nt["recommend_score"] = round(score, 4)
            nt["reason"] = f"适配{user_type}：依据{'/'.join(prefer)}"
            scored.append(nt)
        scored.sort(key=lambda x: -x["recommend_score"])
        return scored[:top_k]

    # ── P.2 审核（增强版：3级风险标注 + 馆员复核建议）─────────────
    def audit(self, report: Dict, known_terms: Optional[Set[str]] = None) -> Dict:
        """
        三级审核：
          ✅ 安全 — 实体在知识库中
          ⚠️ 低风险 — 实体不在知识库但可接受
          🚫 高风险 — 疑似幻觉（无来源、无证据链）
        """
        audited = dict(report)
        safe, warn, danger = [], [], []

        if known_terms is None and self.data is not None:
            try:
                y = max(self.data.year_range)
                known_terms = set(self.data.get_entities(y).keys())
            except Exception:
                known_terms = set()
        if known_terms is None:
            known_terms = set()

        for sec in audited.get("sections", []):
            data = sec.get("data")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        name = item["name"]
                        has_evidence = bool(item.get("evidence") or item.get("doi") or item.get("arxiv_id"))
                        in_kb = name in known_terms
                        if in_kb and has_evidence:
                            item["audit_level"] = "safe"
                            safe.append(name)
                        elif in_kb:
                            item["audit_level"] = "safe"
                            safe.append(name)
                        elif has_evidence:
                            item["audit_level"] = "warn"
                            warn.append(name)
                        else:
                            item["audit_level"] = "danger"
                            danger.append(name)

        status = "✅ 全部可追溯"
        if danger:
            status = f"🚫 {len(danger)}项高风险（疑似幻觉，建议驳回）"
        elif warn:
            status = f"⚠️ {len(warn)}项低风险（建议馆员复核）"

        audited["audit"] = {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "safe": safe,
            "warn": warn,
            "danger": danger,
            "status": status,
            "note": "三级审核：safe=可追溯 | warn=低风险需复核 | danger=疑似幻觉建议驳回",
            "review_required": len(warn) > 0 or len(danger) > 0,
            "review_action": "建议学科馆员人工复核" if warn else ("建议驳回重生成" if danger else "无需复核"),
        }
        return audited

    # ── P.3 推送 ──────────────────────────────────────────
    def push(self, title: str, content: str) -> Dict:
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

    # ── P.4 沉淀 ──────────────────────────────────────────
    def sediment(self, report: Dict) -> Dict:
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
                        al = it.get("audit_level", "")
                        tail = f"  — 证据: {ev}" if ev else ""
                        tag = f" [{al}]" if al else ""
                        lines.append(f"- [[{nm}]]{tag}{tail}")
                    else:
                        lines.append(f"- {it}")
            else:
                lines.append(str(data))
            lines.append("")
        fp.write_text("\n".join(lines), encoding="utf-8")
        return {"sedimented": True, "path": str(fp), "filename": fname}

    # ── P.5 知识回写（闭环）─────────────────────────────────
    def writeback(self, qa_pairs: List[Dict]) -> Dict:
        """
        将经过馆员确认的高质量问答对回写知识图谱。
        写入 _writeback_log.json，后续由知识图谱构建脚本消费。
        """
        log_path = BASE_DIR / "_writeback_log.json"
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        new_entries = []
        for qa in qa_pairs:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "question": qa.get("question", ""),
                "answer_snippet": (qa.get("answer", "") or "")[:200],
                "entities": qa.get("entities", []),
                "relation": qa.get("relation", "qa_pair"),
                "confidence": qa.get("confidence", 0.8),
                "reviewed_by": qa.get("reviewed_by", "system"),
            }
            new_entries.append(entry)
        combined = existing + new_entries
        log_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": len(new_entries), "total": len(combined), "path": str(log_path)}


if __name__ == "__main__":
    sr = ServiceRules()
    topics = [
        {"name": "数字文旅", "heat": 0.8, "growth": 0.3, "centrality": 0.6, "connections": 40},
        {"name": "generative ai", "heat": 0.5, "growth": 0.9, "centrality": 0.4, "connections": 20},
    ]
    print("✅ ServiceRules 增强版加载完成")
    print("recommend:", [t["name"] for t in sr.recommend(topics, "teacher")])
    rep = {"title": "测试", "user_type": "教师科研", "data_scale": "89年×43K",
           "sections": [{"name": "热点", "data": topics}]}
    au = sr.audit(rep, known_terms={"数字文旅", "旅游"})
    print("audit:", au["audit"]["status"])
    wb = sr.writeback([{"question": "测试", "answer": "这是测试", "entities": ["测试"]}])
    print("writeback:", wb)
