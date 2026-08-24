#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible Task C/D handover and report generator.

Task C rebuilds both state-vector variants from one frozen B1 source. Task D
uses the same tourism predicate and canonical topic labels for both languages.
Running this file refreshes every v3 JSON, log, and Markdown deliverable.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


VERSION = "v3"
DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
RANDOM_SEED = 20260825
COMPARISON_YEARS = (2020, 2022, 2024)
WINDOW_YEARS = 5

TOURISM_KEYWORDS_UNIFIED = (
    "旅游", "遗产", "文化", "tourism", "heritage", "culture",
    "destination", "博物馆", "丝绸之路", "arab", "沙漠",
    "صحراو", "سياح", "واحة", "تراث", "مخطوط", "سياحة",
)

TOPIC_KEYWORDS = {
    "旅游": ("旅游", "tourism", "travel", "tourist", "سياحة", "سياح"),
    "文化遗产": ("文化遗产", "遗产", "heritage", "museum", "博物馆", "تراث", "مخطوط"),
    "阿拉伯文化": ("arab", "arabic", "阿拉伯", "عربي"),
    "伊斯兰文化": ("islam", "islamic", "伊斯兰", "إسلام"),
    "教育": ("education", "university", "教育", "大学", "جامعة"),
    "数字化": ("digital", "digitization", "数字化", "智能", "artificial intelligence"),
    "可持续发展": ("sustainable", "sustainability", "可持续", "sdg"),
    "历史": ("history", "historical", "历史", "تاريخ", "ancient"),
}

TOPIC_ONTOLOGY = {
    "L1_文旅核心": ("旅游", "文化遗产"),
    "L2_文化认同": ("阿拉伯文化", "伊斯兰文化", "历史"),
    "L3_方法论": ("教育", "数字化", "可持续发展"),
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_b1(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    data = json.loads(clean)
    return [paper for paper in data if isinstance(paper, dict)]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def paper_text(paper: dict) -> str:
    keywords = paper.get("keywords") or []
    return f"{paper.get('title', '')} {' '.join(map(str, keywords))}".lower()


def is_tourism_related(paper: dict) -> bool:
    text = paper_text(paper)
    return any(keyword in text for keyword in TOURISM_KEYWORDS_UNIFIED)


def classify_topics(text: str) -> list[str]:
    normalized = text.lower()
    return [
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]


def topic_levels(topics: Iterable[str]) -> list[str]:
    topic_set = set(topics)
    return [
        level
        for level, level_topics in TOPIC_ONTOLOGY.items()
        if topic_set.intersection(level_topics)
    ]


def primary_topic_level(topics: Iterable[str]) -> str:
    levels = topic_levels(topics)
    return levels[0] if levels else "L4_其他"


def normalized_keywords(paper: dict) -> tuple[str, ...]:
    values = paper.get("keywords") or paper.get("normalized_keywords") or []
    return tuple(sorted({str(value).strip().lower() for value in values if str(value).strip()}))


def build_state_vectors(papers: list[dict], window: int = WINDOW_YEARS) -> dict:
    """Rebuild the online model's five-year co-occurrence state vectors."""
    by_year: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    for paper in papers:
        try:
            year = int(paper.get("year"))
        except (TypeError, ValueError):
            continue
        keywords = normalized_keywords(paper)
        if keywords:
            by_year[year].append(keywords)

    years = sorted(by_year)
    if not years:
        return {}

    state_vectors: dict[str, dict[str, list[float]]] = {}
    previous_degree: Counter = Counter()
    for year in range(years[0] + window - 1, years[-1] + 1):
        edges: Counter = Counter()
        for source_year in range(year - window + 1, year + 1):
            for keywords in by_year.get(source_year, []):
                for left, right in itertools.combinations(keywords, 2):
                    edges[(left, right)] += 1

        degree: Counter = Counter()
        neighbors: dict[str, set[str]] = defaultdict(set)
        for (left, right), weight in edges.items():
            degree[left] += weight
            degree[right] += weight
            neighbors[left].add(right)
            neighbors[right].add(left)

        node_count = len(neighbors)
        vectors = {}
        for node in sorted(neighbors):
            connection_count = len(neighbors[node])
            centrality = connection_count / (node_count - 1) if node_count > 1 else 0.0
            vectors[node] = [
                degree[node],
                degree[node] - previous_degree.get(node, 0),
                round(centrality, 6),
                connection_count,
            ]
        state_vectors[str(year)] = vectors
        previous_degree = degree

    return state_vectors


def top_topics(state_vectors: dict, year: int, limit: int = 20) -> list[tuple[str, float]]:
    scored = [
        (topic, vector[0] if isinstance(vector, list) else vector)
        for topic, vector in state_vectors.get(str(year), {}).items()
    ]
    return sorted(scored, key=lambda item: (-item[1], item[0]))[:limit]


def run_task_c(data_dir: Path = DATA_DIR) -> dict:
    source = data_dir / "B1_文献主表_含阿语_20260819.json"
    papers = load_b1(source)
    arabic = [paper for paper in papers if paper.get("language") == "ar"]
    baseline = [paper for paper in papers if paper.get("language") != "ar"]

    baseline_vectors = build_state_vectors(baseline)
    augmented_vectors = build_state_vectors(papers)
    baseline_sha = sha256_json(baseline_vectors)
    augmented_sha = sha256_json(augmented_vectors)
    if baseline_sha == augmented_sha:
        raise RuntimeError(
            "Invalid Task C comparison: rebuilt baseline and augmented state vectors are identical"
        )

    yearly_comparison = {}
    for year in COMPARISON_YEARS:
        baseline_year = baseline_vectors.get(str(year), {})
        augmented_year = augmented_vectors.get(str(year), {})
        baseline_names = {topic for topic, _ in top_topics(baseline_vectors, year)}
        augmented_names = {topic for topic, _ in top_topics(augmented_vectors, year)}
        union = baseline_names | augmented_names
        baseline_heat = sum(vector[0] for vector in baseline_year.values())
        augmented_heat = sum(vector[0] for vector in augmented_year.values())
        yearly_comparison[str(year)] = {
            "jaccard": round(len(baseline_names & augmented_names) / len(union), 4) if union else None,
            "common_topics": len(baseline_names & augmented_names),
            "baseline_total_heat": baseline_heat,
            "augmented_total_heat": augmented_heat,
            "total_heat_delta": augmented_heat - baseline_heat,
            "baseline_top20": sorted(baseline_names),
            "augmented_top20": sorted(augmented_names),
        }

    valid_jaccards = [
        item["jaccard"] for item in yearly_comparison.values() if item["jaccard"] is not None
    ]
    average_jaccard = sum(valid_jaccards) / len(valid_jaccards)
    baseline_topics = {
        topic
        for year in range(2020, 2025)
        for topic in baseline_vectors.get(str(year), {})
    }
    augmented_topics = {
        topic
        for year in range(2020, 2025)
        for topic in augmented_vectors.get(str(year), {})
    }
    new_topics = sorted(augmented_topics - baseline_topics)

    year_distribution = Counter(
        str(paper.get("year")) for paper in arabic if paper.get("year") is not None
    )
    tourism_count = sum(is_tourism_related(paper) for paper in arabic)
    return {
        "meta": {
            "version": VERSION,
            "generated_at": utc_timestamp(),
            "experiment_type": "descriptive_perturbation_analysis",
            "random_seed": RANDOM_SEED,
            "state_builder": "five_year_keyword_cooccurrence",
            "source_sha256": sha256_file(source),
        },
        "data_version": {
            "v1_baseline_count": len(baseline),
            "v2_with_arabic_count": len(papers),
            "arabic_count": len(arabic),
            "baseline_membership_sha256": sha256_json(baseline),
            "augmented_membership_sha256": sha256_json(papers),
            "baseline_state_sha256": baseline_sha,
            "augmented_state_sha256": augmented_sha,
        },
        "arabic_analysis": {
            "total": len(arabic),
            "tourism_related": tourism_count,
            "year_distribution": dict(sorted(year_distribution.items())),
        },
        "top20_comparison": yearly_comparison,
        "conclusions": {
            "q1_state_vector_changed": True,
            "q1_top20_membership_changed": average_jaccard < 0.95,
            "q1_average_jaccard": round(average_jaccard, 4),
            "q2_new_topics_count": len(new_topics),
            "q2_new_topics": new_topics,
            "q3_independent_model_recommended": len(arabic) >= 50,
            "q3_sample_size": len(arabic),
            "q3_year_coverage": len(year_distribution),
        },
    }


def match_paper_to_text(paper: dict, pdf_texts: dict) -> str:
    doi = str(paper.get("doi") or "")
    title = str(paper.get("title") or "")
    for key in (doi, doi.replace("/", "_")):
        if key and key in pdf_texts:
            return str(pdf_texts[key])
    if title:
        for key, text in pdf_texts.items():
            if not key.startswith("Extra_"):
                continue
            key_title = key[6:].strip()
            if len(title) >= 15 and len(key_title) >= 15:
                if title[:15] in key_title or key_title[:15] in title:
                    return str(text)
    return ""


def run_task_d(data_dir: Path = DATA_DIR) -> dict:
    papers = load_b1(data_dir / "B1_文献主表_含阿语_20260819.json")
    pdf_texts = load_json(data_dir / "pdf_texts_arabic_20260819.json")
    arabic = [paper for paper in papers if paper.get("language") == "ar"]
    english = [paper for paper in papers if paper.get("language") == "en"]
    english_arab_related = [
        paper
        for paper in english
        if any(term in paper_text(paper) for term in ("arab", "arabic", "middle east", "islam"))
    ]

    analyses = []
    for paper in arabic:
        full_text = match_paper_to_text(paper, pdf_texts)
        topics = classify_topics(f"{paper_text(paper)} {full_text[:500]}")
        levels = topic_levels(topics)
        analyses.append({
            "doi": paper.get("doi", ""),
            "title": str(paper.get("title", ""))[:80],
            "year": paper.get("year"),
            "has_pdf": bool(paper.get("has_pdf")),
            "text_extracted": len(full_text) > 100,
            "human_read": False,
            "topics": topics,
            "levels": levels,
            "primary_level": primary_topic_level(topics),
            "tourism_related": is_tourism_related(paper),
            "excerpt": full_text[:300].replace("\n", " ").strip(),
        })

    arabic_topic_distribution = Counter(
        topic for analysis in analyses for topic in analysis["topics"]
    )
    english_topic_distribution = Counter(
        topic
        for paper in english_arab_related
        for topic in classify_topics(paper_text(paper))
    )
    primary_level_distribution = Counter(
        analysis["primary_level"] for analysis in analyses
    )
    level_mention_distribution = Counter(
        level for analysis in analyses for level in analysis["levels"]
    )
    comparison = [
        {
            "topic": topic,
            "arabic": arabic_topic_distribution.get(topic, 0),
            "english": english_topic_distribution.get(topic, 0),
            "level": primary_topic_level([topic]),
        }
        for topic in TOPIC_KEYWORDS
    ]

    summary = {
        "total_arabic_papers": len(arabic),
        "english_arab_related_papers": len(english_arab_related),
        "has_pdf": sum(analysis["has_pdf"] for analysis in analyses),
        "text_extracted": sum(analysis["text_extracted"] for analysis in analyses),
        "human_read": sum(analysis["human_read"] for analysis in analyses),
        "tourism_related": sum(analysis["tourism_related"] for analysis in analyses),
    }
    if sum(primary_level_distribution.values()) != len(arabic):
        raise RuntimeError("Primary level distribution must contain exactly one row per Arabic paper")

    return {
        "meta": {"version": VERSION, "generated_at": utc_timestamp()},
        "summary": summary,
        "analyses": analyses,
        "topic_distribution": {
            "arabic": dict(arabic_topic_distribution),
            "english": dict(english_topic_distribution),
        },
        "primary_level_distribution": dict(primary_level_distribution),
        "level_mention_distribution": dict(level_mention_distribution),
        "comparison": comparison,
        "readable_texts": [
            {
                "doi": analysis["doi"],
                "title": analysis["title"],
                "year": analysis["year"],
                "excerpt": analysis["excerpt"],
            }
            for analysis in analyses
            if analysis["text_extracted"]
        ],
        "difference_explanation": "Descriptive observation only; validate with >=100 Arabic papers and controlled statistical tests.",
    }


def render_task_d_report(result: dict) -> str:
    summary = result["summary"]
    lines = [
        "# Task D: 阿语文献内容分析与英阿对照 (v3)",
        "",
        f"生成时间: {result['meta']['generated_at']}",
        "",
        "## 数据概况",
        "",
        f"- 阿语文献总数: {summary['total_arabic_papers']}",
        f"- has_pdf: {summary['has_pdf']}",
        f"- text_extracted: {summary['text_extracted']}",
        f"- human_read: {summary['human_read']}",
        f"- 文旅相关（统一口径）: {summary['tourism_related']}",
        "",
        "## 主层级分布（每篇只计一次）",
        "",
        "| 层级 | 篇数 |",
        "|---|---:|",
    ]
    for level, count in result["primary_level_distribution"].items():
        lines.append(f"| {level} | {count} |")
    lines.extend(["", "## 英阿主题对照（相同标签与分类器）", "", "| 主题 | 阿语 | 英文 | 层级 |", "|---|---:|---:|---|"])
    for row in result["comparison"]:
        lines.append(f"| {row['topic']} | {row['arabic']} | {row['english']} | {row['level']} |")
    lines.extend(["", "## 可读取文本", ""])
    for item in result["readable_texts"]:
        lines.extend([
            f"### {item['title']}",
            "",
            f"- DOI: {item['doi']}",
            f"- 年份: {item['year']}",
            f"- 原文摘录: {item['excerpt']}",
            "",
        ])
    lines.extend([
        "## 解释边界",
        "",
        "当前差异仅为描述性观察。样本扩展到至少 100 篇并控制年份、期刊等变量后，方可检验研究传统差异假设。",
        "",
    ])
    return "\n".join(lines)


def render_final_report(task_c: dict, task_d: dict) -> str:
    c = task_c["conclusions"]
    d = task_d["summary"]
    versions = task_c["data_version"]
    lines = [
        "# Task C & D 最终报告：阿语文献对世界模型的影响 (v3)",
        "",
        f"生成时间: {task_c['meta']['generated_at']}",
        "",
        "## Task C：有效扰动对照",
        "",
        "基线和含阿语状态向量均由同一冻结 B1 数据、同一五年窗口算法重建。基线明确排除阿语记录。",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| V1 基线记录 | {versions['v1_baseline_count']} |",
        f"| V2 含阿语记录 | {versions['v2_with_arabic_count']} |",
        f"| 基线状态 SHA-256 | `{versions['baseline_state_sha256']}` |",
        f"| 含阿语状态 SHA-256 | `{versions['augmented_state_sha256']}` |",
        f"| 共现状态向量变化 | {c['q1_state_vector_changed']} |",
        f"| Top-20 成员变化（Jaccard <0.95） | {c['q1_top20_membership_changed']} |",
        f"| Top-20 平均 Jaccard | {c['q1_average_jaccard']} |",
        f"| 2020-2024 新主题数 | {c['q2_new_topics_count']} |",
        "",
        "本实验仍属于描述性扰动分析，不宣称 RSSM 性能提升。",
        "",
        "## Task D：内容分析",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
        f"| 阿语文献 | {d['total_arabic_papers']} |",
        f"| has_pdf | {d['has_pdf']} |",
        f"| text_extracted | {d['text_extracted']} |",
        f"| human_read | {d['human_read']} |",
        f"| 文旅相关（与 Task C 同一函数） | {d['tourism_related']} |",
        "",
        "## 英阿主题对照",
        "",
        "| 主题 | 阿语 | 英文 | 层级 |",
        "|---|---:|---:|---|",
    ]
    for row in task_d["comparison"]:
        lines.append(f"| {row['topic']} | {row['arabic']} | {row['english']} | {row['level']} |")
    lines.extend([
        "",
        "## 结论边界",
        "",
        "英阿两侧现使用完全相同的主题标签与分类器。当前阿语样本不足以支持研究传统差异或独立 RSSM 建模结论。",
        "",
    ])
    return "\n".join(lines)


def write_outputs(task_c: dict, task_d: dict) -> None:
    c_dir = OUTPUT_DIR / "experiment_c"
    d_dir = OUTPUT_DIR / "experiment_d"
    write_json(c_dir / "experiment_c_results_v3.json", task_c)
    write_json(d_dir / "experiment_d_results_v3.json", task_d)
    write_json(OUTPUT_DIR / "task_cd_handover_v3.json", {
        "meta": {
            "version": VERSION,
            "tourism_keywords": TOURISM_KEYWORDS_UNIFIED,
            "topic_ontology": TOPIC_ONTOLOGY,
        },
        "task_c_results": task_c,
        "task_d_results": task_d,
    })
    c_dir.mkdir(parents=True, exist_ok=True)
    (c_dir / "experiment_c_log_v3.txt").write_text(
        "\n".join([
            "Task C reproducibility log v3",
            f"generated_at={task_c['meta']['generated_at']}",
            f"source_sha256={task_c['meta']['source_sha256']}",
            f"baseline_state_sha256={task_c['data_version']['baseline_state_sha256']}",
            f"augmented_state_sha256={task_c['data_version']['augmented_state_sha256']}",
            f"average_jaccard={task_c['conclusions']['q1_average_jaccard']}",
            f"new_topics={task_c['conclusions']['q2_new_topics_count']}",
            "",
        ]),
        encoding="utf-8",
    )
    d_dir.mkdir(parents=True, exist_ok=True)
    (d_dir / "experiment_d_report_v3.md").write_text(
        render_task_d_report(task_d), encoding="utf-8"
    )
    (OUTPUT_DIR / "experiment_cd_final_report_v3.md").write_text(
        render_final_report(task_c, task_d), encoding="utf-8"
    )


def run_all(data_dir: Path = DATA_DIR, write: bool = True) -> tuple[dict, dict]:
    task_c = run_task_c(data_dir)
    task_d = run_task_d(data_dir)
    c_tourism = task_c["arabic_analysis"]["tourism_related"]
    d_tourism = task_d["summary"]["tourism_related"]
    if c_tourism != d_tourism:
        raise RuntimeError(f"Task C/D tourism counts diverged: C={c_tourism}, D={d_tourism}")
    if write:
        write_outputs(task_c, task_d)
    return task_c, task_d


def main() -> None:
    task_c, task_d = run_all()
    print("SKWM Task C/D handover v3 complete")
    print(f"Task C: Jaccard={task_c['conclusions']['q1_average_jaccard']}, new_topics={task_c['conclusions']['q2_new_topics_count']}")
    print(f"Task D: tourism={task_d['summary']['tourism_related']}, extracted={task_d['summary']['text_extracted']}")
    print("Outputs: output/*v3*")


if __name__ == "__main__":
    main()
