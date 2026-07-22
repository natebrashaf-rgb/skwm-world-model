"""
报告生成器 — Jinja2 模板，生成学科分析/热点/趋势报告
"""
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).parent


class ReportGenerator:
    def __init__(self, template_dir: str = ""):
        self.template_dir = Path(template_dir or BASE_DIR / "report_templates")
        self.template_dir.mkdir(exist_ok=True)
        self._init_templates()
        self.jinja = Environment(loader=FileSystemLoader(str(self.template_dir)))

    def _init_templates(self):
        templates = {
            "学科分析报告.md.j2": (
                "# {{ topic }} — 学科分析报告\n"
                "> 生成时间: {{ date }}\n\n"
                "## 热点主题\n"
                "{% for h in hotspots %}- **{{ h.name }}** — 热度 {{ h.heat }} | 增长 {{ h.growth }}%\n{% endfor %}\n"
                "## 年度趋势\n"
                "{% for y,d in timeline %}| {{ y }} | {{ d.nodes }} 节点 | {{ d.edges }} 关系 |\n{% endfor %}\n"
            ),
            "热点快报.md.j2": (
                "# 🔥 {{ topic }} — 热点快报\n> {{ date }}\n\n"
                "{% for h in hotspots[:3] %}### {{ loop.index }}. {{ h.name }}\n- 热度: {{ h.heat }}/100\n- 增长: {{ h.growth }}%\n{% endfor %}\n"
            ),
        }
        for name, content in templates.items():
            fp = self.template_dir / name
            if not fp.exists():
                fp.write_text(content, encoding="utf-8")

    def generate(self, topic: str, report_type: str = "学科分析报告", data=None) -> dict:
        d = data or {}
        tpl = self.jinja.get_template(f"{report_type}.md.j2")
        content = tpl.render(
            topic=topic, date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            hotspots=d.get("hotspots", []),
            timeline=sorted(d.get("timeline", {}).items(), key=lambda x: x[0]),
        )
        return {"title": f"{topic} — {report_type}", "content": content, "word_count": len(content)}
