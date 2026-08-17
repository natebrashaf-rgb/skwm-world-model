#!/usr/bin/env python3
"""
frontier_report_generator.py — 学科前沿报告生成器
==================================================
服务产品：带预测、证据、置信度和风险提示的学科前沿报告
服务对象：中阿文旅相关教师和科研团队
服务提供者：学科馆员

报告结构：
  1. 热点概览（当前状态）
  2. 新兴方向识别（预测）
  3. 证据链（文献支撑）
  4. 置信度评估（预测可靠性）
  5. 风险提示（失败边界）
  6. 服务建议（馆员审核意见）

用法:
    python frontier_report_generator.py
    python frontier_report_generator.py --year 2024 --output report_2024.md
"""
import json
import os
import re
import time
import argparse
from collections import defaultdict
from pathlib import Path
from datetime import datetime

import numpy as np

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "frontier_reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_state_vectors():
    path = DATA_DIR / "state_vectors.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_b1():
    path = DATA_DIR / "B1_文献主表.json"
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    if idx > 0:
        return json.loads('[' + raw[idx:])
    return []


def detect_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF]', text):
        return "ar"
    if re.search(r'[\u4e00-\u9fff]', text):
        return "zh"
    return "en"


class FrontierReportGenerator:
    """学科前沿报告生成器"""

    def __init__(self, as_of_year: int = 2023):
        self.as_of_year = as_of_year
        self.sv = load_state_vectors()
        self.b1 = load_b1()
        self.model = self._load_model()

    def _load_model(self):
        model_path = BASE / "model_rssm.pt"
        if model_path.exists():
            try:
                from skwm_world_model import WorldModel
                model = WorldModel.load(str(model_path))
                model.eval()
                return model
            except Exception:
                pass
        return None

    def _get_papers(self, max_year: int = None) -> list:
        my = max_year or self.as_of_year
        return [p for p in self.b1
                if isinstance(p.get("year"), (int, float))
                and int(p.get("year", 0)) <= my]

    def _get_sv(self, year: int = None) -> dict:
        y = year or self.as_of_year
        data = self.sv.get(str(y), {})
        return data if isinstance(data, dict) else {}

    def _linear_forecast(self, topic: str, horizon: int) -> tuple:
        years = sorted(
            int(k) for k in self.sv.keys()
            if k != "_wm" and isinstance(self.sv[k], dict)
        )
        heats = []
        for y in years:
            v = self.sv[str(y)].get(topic)
            heats.append(v[0] if v and len(v) >= 1 else 0)

        if len(heats) < 3:
            return [heats[-1]] * horizon if heats else [0] * horizon, [0] * horizon

        x = np.arange(len(heats), dtype=float)
        slope, intercept = np.polyfit(x, heats, 1)
        preds = [float(max(0, intercept + slope * (len(heats) + h - 1)))
                 for h in range(1, horizon + 1)]
        stds = [abs(p * 0.15) for p in preds]
        return preds, stds

    def _rssm_forecast(self, topic: str, horizon: int, B: int = 5) -> tuple:
        if self.model is None:
            return self._linear_forecast(topic, horizon)

        import torch

        years = sorted(
            int(k) for k in self.sv.keys()
            if k != "_wm" and isinstance(self.sv[k], dict)
        )
        vecs = []
        for y in years[-8:]:
            v = self.sv[str(y)].get(topic, [0, 0, 0, 0])
            if isinstance(v, (list, tuple)) and len(v) >= 4:
                vecs.append(np.array([
                    np.log1p(v[0]), v[1], np.log1p(v[2]), np.log1p(v[3])
                ], dtype=np.float32))

        if len(vecs) < 4:
            return self._linear_forecast(topic, horizon)

        all_preds = []
        for _ in range(B):
            x0 = torch.tensor(vecs[-1:], dtype=torch.float32)
            a_future = torch.zeros(1, horizon, self.model.c.a_dim)
            try:
                with torch.no_grad():
                    pred = self.model.imagine(x0, a_future)
                all_preds.append(pred[0].numpy())
            except Exception:
                break

        if not all_preds:
            return self._linear_forecast(topic, horizon)

        stacked = np.stack(all_preds, axis=0)
        mean_pred = stacked.mean(axis=0)
        std_pred = stacked.std(axis=0)

        preds = [float(max(0, np.expm1(mean_pred[t, 0]))) for t in range(horizon)]
        stds = [float(std_pred[t, 0]) for t in range(horizon)]

        return preds, stds

    def generate_section_hotspots(self, top_k: int = 10) -> str:
        sv = self._get_sv()
        items = sorted(sv.items(), key=lambda x: -x[1][0])[:top_k]

        lines = ["## 一、热点概览\n"]
        lines.append(f"基于截至 {self.as_of_year} 年的数据，当前中阿文旅领域热点主题 Top-{top_k}：\n")
        lines.append("| 排名 | 主题 | 热度 | 增速 | 中心度 |")
        lines.append("|:----:|:-----|-----:|-----:|-------:|")

        for i, (name, vec) in enumerate(items, 1):
            lines.append(f"| {i} | {name} | {vec[0]} | {vec[1]:+.1f} | {vec[2]:.4f} |")

        lines.append(f"\n**数据来源**: state_vectors.json, 截止年份 {self.as_of_year}")
        return "\n".join(lines)

    def generate_section_emerging(self, top_k: int = 10, horizon: int = 3) -> str:
        sv = self._get_sv()
        items = sorted(sv.items(), key=lambda x: -abs(x[1][1]))[:top_k * 2]

        forecast_results = []
        for name, vec in items[:top_k]:
            if self.model:
                preds, stds = self._rssm_forecast(name, horizon)
            else:
                preds, stds = self._linear_forecast(name, horizon)

            current_heat = vec[0]
            predicted_heat = preds[-1] if preds else current_heat
            predicted_growth = predicted_heat - current_heat
            confidence = max(0.1, min(0.9, 0.7 - stds[-1] * 0.5)) if stds else 0.5

            forecast_results.append({
                "name": name,
                "current_heat": current_heat,
                "current_growth": vec[1],
                "predicted_heat": predicted_heat,
                "predicted_growth": predicted_growth,
                "confidence": confidence,
                "uncertainty": stds[-1] if stds else 0,
            })

        forecast_results.sort(key=lambda x: -x["predicted_growth"])

        lines = ["\n## 二、新兴方向识别（预测）\n"]
        lines.append(f"基于 RSSM 世界模型 {horizon} 年预测，识别新兴交叉方向：\n")
        lines.append("| 排名 | 主题 | 当前热度 | 预测增长 | 置信度 | 不确定性 |")
        lines.append("|:----:|:-----|--------:|--------:|-------:|--------:|")

        for i, r in enumerate(forecast_results[:top_k], 1):
            lines.append(
                f"| {i} | {r['name']} | {r['current_heat']} | "
                f"{r['predicted_growth']:+.0f} | {r['confidence']:.0%} | "
                f"±{r['uncertainty']:.1f} |"
            )

        lines.append(f"\n**预测方法**: {'RSSM多步预测' if self.model else '线性趋势外推'}")
        lines.append(f"**预测视野**: {horizon} 年")
        return "\n".join(lines)

    def generate_section_evidence(self, topics: list = None, papers_per_topic: int = 5) -> str:
        if not topics:
            sv = self._get_sv()
            topics = sorted(sv.keys(), key=lambda t: -sv[t][1])[:5]

        papers = self._get_papers()
        lines = ["\n## 三、证据链（文献支撑）\n"]
        lines.append("以下为各新兴方向的核心文献证据：\n")

        for topic in topics[:5]:
            lines.append(f"### {topic}\n")
            matched = []
            for p in papers:
                title = str(p.get("title", "")).lower()
                kws = p.get("keywords") or p.get("normalized_keywords") or []
                if isinstance(kws, str):
                    kws = [k.strip() for k in kws.split(",")]
                kw_text = " ".join(k.lower() for k in kws)
                if topic.lower() in title or any(topic.lower() in k for k in kw_text):
                    matched.append(p)

            matched.sort(key=lambda x: -(x.get("citations") or 0))

            if matched:
                lines.append(f"| 标题 | 年份 | DOI | 引用 | 语种 |")
                lines.append(f"|:-----|:----:|:----|-----:|:----:|")
                for p in matched[:papers_per_topic]:
                    title = str(p.get("title", ""))[:50]
                    doi = p.get("doi", "N/A")[:20]
                    year = p.get("year", "N/A")
                    cite = p.get("citations", 0)
                    lang = detect_language(p.get("title", ""))
                    lines.append(f"| {title} | {year} | {doi} | {cite} | {lang} |")
            else:
                lines.append("*未找到直接相关文献*\n")

        return "\n".join(lines)

    def generate_section_confidence(self) -> str:
        lines = ["\n## 四、置信度评估\n"]
        lines.append("### 预测可靠性分析\n")

        sv = self._get_sv()
        papers = self._get_papers()

        data_density = len(papers) / max(1, self.as_of_year - 1990)
        arab_ratio = sum(1 for p in papers if detect_language(p.get("title", "")) == "ar") / max(1, len(papers))
        topic_coverage = len(sv)

        lines.append(f"| 指标 | 数值 | 评估 |")
        lines.append(f"|:-----|-----:|:-----|")
        lines.append(f"| 年均文献密度 | {data_density:.0f} 篇/年 | {'充足' if data_density > 100 else '中等' if data_density > 50 else '稀疏'} |")
        lines.append(f"| 阿语文献占比 | {arab_ratio:.1%} | {'充足' if arab_ratio > 0.2 else '不足' if arab_ratio < 0.1 else '中等'} |")
        lines.append(f"| 活跃主题数 | {topic_coverage} | {'丰富' if topic_coverage > 500 else '有限'} |")

        overall_confidence = min(0.8, 0.3 + data_density / 500 + arab_ratio)
        lines.append(f"\n**整体预测置信度**: {overall_confidence:.0%}")
        lines.append("\n**置信度说明**: 基于数据密度、语种覆盖、主题丰富度综合评估")

        return "\n".join(lines)

    def generate_section_risks(self) -> str:
        lines = ["\n## 五、风险提示（失败边界）\n"]
        lines.append("### 以下情况预测可能失效：\n")

        risks = [
            ("数据稀疏", "阿拉伯语文献覆盖不足，相关子方向预测可靠性降低"),
            ("高频主题自增强", "头部主题（如'旅游'）可能因惯性持续领先，掩盖新兴方向"),
            ("长期预测衰减", "1年预测可信度 > 3年预测 > 5年预测"),
            ("突发事件不可预测", "政策变化、疫情、冲突等无法纳入模型"),
            ("相关性≠因果", "共现关系不代表因果关系，需谨慎解读"),
            ("低置信度预警", "置信度 < 40% 的预测仅供参考，不应作为决策依据"),
            ("模型加载失败降级", "RSSM 不可用时自动降级为线性趋势，预测能力下降"),
        ]

        lines.append("| 风险类型 | 说明 |")
        lines.append("|:---------|:-----|")
        for risk, desc in risks:
            lines.append(f"| {risk} | {desc} |")

        lines.append("\n**建议**: 对低置信度预测进行人工核实，结合领域专家判断")

        return "\n".join(lines)

    def generate_section_recommendations(self) -> str:
        lines = ["\n## 六、服务建议（馆员审核意见）\n"]
        lines.append("### 面向科研团队的使用建议：\n")

        recommendations = [
            "优先关注置信度 > 60% 的新兴方向",
            "对阿语相关研究保持谨慎，数据覆盖有限",
            "结合本文献报告与领域专家讨论，避免单一数据驱动决策",
            "定期（每半年）更新前沿报告，跟踪预测准确性",
            "对于基金申请选题，建议结合多维度证据（文献、政策、产业需求）",
        ]

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")

        lines.append("\n---")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append(f"*服务提供者: 学科馆员*")
        lines.append(f"*数据来源: SKWM 世界模型 (RSSM)*")

        return "\n".join(lines)

    def generate_full_report(self, output_path: str = None) -> str:
        sections = [
            f"# 中阿文旅学科前沿报告\n",
            f"**报告年份**: {self.as_of_year}",
            f"**服务对象**: 中阿文旅相关教师和科研团队",
            f"**服务提供者**: 学科馆员\n",
            "---\n",
            self.generate_section_hotspots(),
            self.generate_section_emerging(),
            self.generate_section_evidence(),
            self.generate_section_confidence(),
            self.generate_section_risks(),
            self.generate_section_recommendations(),
        ]

        report = "\n".join(sections)

        if output_path:
            Path(output_path).write_text(report, encoding="utf-8")
            print(f"[OK] 报告已保存: {output_path}")
        else:
            default_path = OUT_DIR / f"frontier_report_{self.as_of_year}.md"
            default_path.write_text(report, encoding="utf-8")
            print(f"[OK] 报告已保存: {default_path}")
            output_path = str(default_path)

        return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2023, help="截止年份")
    parser.add_argument("--output", type=str, help="输出路径")
    args = parser.parse_args()

    print("=" * 60)
    print("  学科前沿报告生成器")
    print("=" * 60)
    print(f"  截止年份: {args.year}")

    gen = FrontierReportGenerator(as_of_year=args.year)
    path = gen.generate_full_report(args.output)

    print(f"\n[完成] 报告生成: {path}")


if __name__ == "__main__":
    main()
