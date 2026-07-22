"""
Obsidian 知识沉淀补充 — 自动将问答/报告/快照写成 .md
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import re

BASE_DIR = Path(__file__).parent


class ObsidianSync:
    def __init__(self, vault_dir: str = ""):
        self.vault_dir = Path(vault_dir or BASE_DIR / "obsidian_vault")
        self.vault_dir.mkdir(exist_ok=True)
        for sub in ["问答记录", "报告", "快照"]:
            (self.vault_dir / sub).mkdir(exist_ok=True)

    def save_qa(self, question: str, result: Dict) -> Optional[Path]:
        now = datetime.now()
        fp = self.vault_dir / "问答记录" / f"{now.strftime('%Y-%m-%d')}_{self._slug(question[:20])}.md"
        tags = ["问答"]
        if result.get("rule_triggered"):
            tags.append("规则命中")
        fp.write_text(
            f"---\ncreated: {now.strftime('%Y-%m-%d %H:%M:%S')}\ntags: [{', '.join(tags)}]\n"
            f"type: qa\nconfidence: {result.get('confidence', 0)}\n---\n\n"
            f"# Q: {question}\n\n{result.get('answer', '')}\n",
            encoding="utf-8"
        )
        return fp

    def save_report(self, report: Dict) -> Optional[Path]:
        fp = self.vault_dir / "报告" / f"{self._slug(report.get('title', '报告')[:40])}.md"
        fp.write_text(
            f"---\ntitle: {report.get('title','')}\ncreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\ntype: report\n---\n\n"
            f"{report.get('content', '')}\n",
            encoding="utf-8"
        )
        return fp

    def save_snapshot(self, hotspots: list, entities: int, relations: int) -> Optional[Path]:
        now = datetime.now()
        fp = self.vault_dir / "快照" / f"快照_{now.strftime('%Y-%m-%d')}.md"
        fp.write_text(
            f"---\ncreated: {now.strftime('%Y-%m-%d %H:%M:%S')}\ntags: [快照]\ntype: snapshot\n---\n\n"
            f"# SKWM 知识状态快照 ({now.strftime('%Y-%m-%d')})\n\n"
            + "\n".join([f"{i+1}. {h['name']} (热度 {h['heat']})" for i, h in enumerate(hotspots[:5])])
            + f"\n\n实体: {entities} | 关系: {relations}\n",
            encoding="utf-8"
        )
        return fp

    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r'[^\w\u4e00-\u9fff-]', '', text).strip()[:40] or "note"

    def list_recent(self, days: int = 7) -> list:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        for fp in sorted(self.vault_dir.rglob("*.md"), reverse=True):
            mtime = datetime.fromtimestamp(fp.stat().st_mtime)
            if mtime > cutoff:
                results.append({"path": str(fp.relative_to(self.vault_dir)), "title": fp.stem, "date": mtime.strftime("%Y-%m-%d %H:%M")})
        return results
