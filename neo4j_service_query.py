#!/usr/bin/env python3
"""
neo4j_service_query.py — S0 静态知识图谱服务基线
================================================
定位：S0 基线 + 历史快照 + 预测证据追溯
职责：
  1. as_of_year 防穿越（预测2024时不读2024+数据）
  2. Paper/Topic/Author/Relation 分类返回
  3. 返回 DOI、来源、语种、年份、图谱关系路径
  4. 馆员服务问题集（真实学科服务场景）
  5. 为 S0/S1/S2 生成统一格式盲评材料

用法:
    python neo4j_service_query.py                    # 默认演示
    python neo4j_service_query.py --as-of 2022       # 指定截止年
    python neo4j_service_query.py --blind-review     # 生成盲评材料
"""
import json
import os
import sys
import time
import argparse
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "service_baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CRED_FILE = BASE / ".neo4j_cred.json"

LIBRARIAN_QUESTIONS = [
    {
        "qid": "Q1",
        "category": "前沿识别",
        "question": "中阿文旅领域近3年增速最快的交叉研究方向有哪些？",
        "expected_type": "topic_ranking",
        "requires_prediction": False,
    },
    {
        "qid": "Q2",
        "category": "前沿识别",
        "question": "数字遗产与旅游交叉领域，未来2年可能出现哪些新兴主题？",
        "expected_type": "emerging_prediction",
        "requires_prediction": True,
    },
    {
        "qid": "Q3",
        "category": "证据追溯",
        "question": "'文化遗产数字化'这一方向的核心文献有哪些？请给出DOI和引用关系。",
        "expected_type": "evidence_chain",
        "requires_prediction": False,
    },
    {
        "qid": "Q4",
        "category": "风险评估",
        "question": "阿拉伯语文旅文献的数据覆盖度如何？哪些子方向数据稀疏？",
        "expected_type": "coverage_assessment",
        "requires_prediction": False,
    },
    {
        "qid": "Q5",
        "category": "趋势预测",
        "question": "基于历史数据，预测2025-2026年中阿文旅领域的Top-10热点主题。",
        "expected_type": "forecast",
        "requires_prediction": True,
    },
    {
        "qid": "Q6",
        "category": "作者发现",
        "question": "在中阿文旅交叉领域，哪些作者的研究呈现跨学科特征？",
        "expected_type": "author_discovery",
        "requires_prediction": False,
    },
    {
        "qid": "Q7",
        "category": "反事实",
        "question": "如果移除'一带一路'相关的政策文献，中阿文旅合作网络的连通性会如何变化？",
        "expected_type": "counterfactual",
        "requires_prediction": True,
    },
    {
        "qid": "Q8",
        "category": "服务推荐",
        "question": "一位研究阿拉伯数字人文的教师，应该关注哪些新兴交叉方向和相关文献？",
        "expected_type": "recommendation",
        "requires_prediction": True,
    },
]


def load_creds():
    if not CRED_FILE.exists():
        return None
    with open(CRED_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_state_vectors():
    path = DATA_DIR / "state_vectors.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_b1():
    import re
    path = DATA_DIR / "B1_文献主表.json"
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    if idx > 0:
        return json.loads('[' + raw[idx:])
    return []


def load_temporal_snapshots():
    import re
    path = DATA_DIR / "temporal_snapshots.json"
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        data = json.loads("[" + raw[m.end():])
    else:
        data = json.loads(raw)
    return {k: v for k, v in data.items() if isinstance(v, dict) and k != "_wm"}


class Neo4jServiceQuery:
    """S0 静态知识图谱服务基线"""

    def __init__(self, as_of_year: int = 2026):
        self.as_of_year = as_of_year
        self.sv = load_state_vectors()
        self.b1 = load_b1()
        self.ts = load_temporal_snapshots()
        self.driver = None
        creds = load_creds()
        if creds:
            try:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(
                    creds["uri"], auth=(creds["user"], creds["password"])
                )
                self.driver.verify_connectivity()
            except Exception:
                self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def _filter_sv_by_year(self, year: int = None) -> dict:
        y = year or self.as_of_year
        data = self.sv.get(str(y), {})
        return data if isinstance(data, dict) else {}

    def _filter_papers_by_year(self, max_year: int = None) -> list:
        my = max_year or self.as_of_year
        return [p for p in self.b1
                if isinstance(p.get("year"), (int, float))
                and int(p.get("year", 0)) <= my]

    def query_hotspots(self, top_k: int = 20, year: int = None) -> dict:
        sv = self._filter_sv_by_year(year)
        items = sorted(sv.items(), key=lambda x: -x[1][0])[:top_k]
        papers = self._filter_papers_by_year(year)
        return {
            "type": "hotspots",
            "as_of_year": year or self.as_of_year,
            "topics": [
                {
                    "name": name,
                    "heat": vec[0],
                    "growth": vec[1],
                    "centrality": vec[2],
                    "connections": vec[3],
                }
                for name, vec in items
            ],
            "total_papers": len(papers),
        }

    def query_emerging(self, top_k: int = 20, year: int = None) -> dict:
        sv = self._filter_sv_by_year(year)
        items = sorted(sv.items(), key=lambda x: -abs(x[1][1]))[:top_k]
        return {
            "type": "emerging",
            "as_of_year": year or self.as_of_year,
            "topics": [
                {
                    "name": name,
                    "growth": vec[1],
                    "heat": vec[0],
                    "growth_valid": abs(vec[1]) <= vec[0],
                }
                for name, vec in items
            ],
        }

    def query_topic_evidence(self, topic_keyword: str, year: int = None) -> dict:
        papers = self._filter_papers_by_year(year)
        matched = []
        for p in papers:
            title = str(p.get("title", "")).lower()
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            kw_lower = [k.lower().strip() for k in kws]
            if topic_keyword.lower() in title or any(
                topic_keyword.lower() in k for k in kw_lower
            ):
                matched.append({
                    "doi": p.get("doi", ""),
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "venue": p.get("venue", ""),
                    "citations": p.get("citations", 0),
                    "authors": p.get("authors", ""),
                    "language": self._detect_language(p),
                })
        matched.sort(key=lambda x: -(x.get("citations") or 0))
        return {
            "type": "evidence_chain",
            "topic": topic_keyword,
            "as_of_year": year or self.as_of_year,
            "papers": matched[:30],
            "total_matched": len(matched),
        }

    def query_coverage(self, year: int = None) -> dict:
        papers = self._filter_papers_by_year(year)
        lang_count = Counter()
        for p in papers:
            lang = self._detect_language(p)
            lang_count[lang] += 1

        sv = self._filter_sv_by_year(year)
        sparse_topics = []
        for name, vec in sv.items():
            if vec[0] < 5:
                sparse_topics.append({"name": name, "heat": vec[0]})
        sparse_topics.sort(key=lambda x: x["heat"])

        return {
            "type": "coverage",
            "as_of_year": year or self.as_of_year,
            "total_papers": len(papers),
            "language_distribution": dict(lang_count),
            "arabic_ratio": lang_count.get("ar", 0) / max(1, len(papers)),
            "sparse_topics_count": len(sparse_topics),
            "sparse_topics_top20": sparse_topics[:20],
        }

    def query_author_crossdisciplinary(self, year: int = None) -> dict:
        papers = self._filter_papers_by_year(year)
        author_topics = defaultdict(set)
        author_papers = defaultdict(list)
        for p in papers:
            authors_str = p.get("authors", "")
            if not authors_str:
                continue
            import re
            authors = [a.strip() for a in re.split(r'[,;、]', authors_str) if len(a.strip()) > 2]
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            for a in authors[:5]:
                for k in kws:
                    if k.strip():
                        author_topics[a].add(k.strip().lower())
                author_papers[a].append(p.get("title", ""))

        cross_authors = []
        for author, topics in author_topics.items():
            if len(topics) >= 5 and len(author_papers[author]) >= 3:
                cross_authors.append({
                    "name": author,
                    "topic_diversity": len(topics),
                    "paper_count": len(author_papers[author]),
                    "sample_topics": sorted(topics)[:8],
                })
        cross_authors.sort(key=lambda x: -x["topic_diversity"])

        return {
            "type": "author_discovery",
            "as_of_year": year or self.as_of_year,
            "crossdisciplinary_authors": cross_authors[:30],
            "total_authors": len(author_topics),
        }

    def query_graph_paths(self, topic_a: str, topic_b: str,
                          max_hops: int = 3, year: int = None) -> dict:
        sv = self._filter_sv_by_year(year)
        papers = self._filter_papers_by_year(year)

        bridge_papers = []
        for p in papers:
            title = str(p.get("title", "")).lower()
            kws = p.get("keywords") or p.get("normalized_keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",")]
            kw_text = " ".join(k.lower() for k in kws)
            has_a = topic_a.lower() in title or topic_a.lower() in kw_text
            has_b = topic_b.lower() in title or topic_b.lower() in kw_text
            if has_a and has_b:
                bridge_papers.append({
                    "doi": p.get("doi", ""),
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                })

        path_info = {
            "type": "graph_path",
            "from": topic_a,
            "to": topic_b,
            "as_of_year": year or self.as_of_year,
            "bridge_papers": bridge_papers[:20],
            "path_length": 1 if bridge_papers else None,
        }

        if self.driver:
            try:
                with self.driver.session() as s:
                    result = s.run(
                        "MATCH (a:Topic {name: $a})-[r:CO_OCCURS_WITH*1..$hops]-(b:Topic {name: $b}) "
                        "RETURN [rel in r | rel.weight] AS weights, length(r) AS len "
                        "ORDER BY len LIMIT 5",
                        a=topic_a, b=topic_b, hops=max_hops
                    )
                    paths = [dict(record) for record in result]
                    path_info["neo4j_paths"] = paths
            except Exception:
                pass

        return path_info

    def answer_question(self, q: dict) -> dict:
        qid = q["qid"]
        year = self.as_of_year

        if qid == "Q1":
            result = self.query_emerging(top_k=15, year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result

        elif qid == "Q2":
            emerging = self.query_emerging(top_k=10, year=year)
            evidence = self.query_topic_evidence("digital heritage", year=year)
            return {
                "qid": qid,
                "question": q["question"],
                "type": "emerging_prediction",
                "as_of_year": year,
                "emerging_topics": emerging["topics"][:10],
                "evidence_papers": evidence["papers"][:5],
                "note": "S0基线仅提供历史数据，预测能力有限",
            }

        elif qid == "Q3":
            result = self.query_topic_evidence("文化遗产数字化", year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result

        elif qid == "Q4":
            result = self.query_coverage(year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result

        elif qid == "Q5":
            hotspots = self.query_hotspots(top_k=15, year=year)
            return {
                "qid": qid,
                "question": q["question"],
                "type": "forecast",
                "as_of_year": year,
                "baseline_hotspots": hotspots["topics"],
                "note": "S0基线仅外推当前热度排序，无预测模型",
            }

        elif qid == "Q6":
            result = self.query_author_crossdisciplinary(year=year)
            result["question"] = q["question"]
            result["qid"] = qid
            return result

        elif qid == "Q7":
            path = self.query_graph_paths("一带一路", "旅游", year=year)
            return {
                "qid": qid,
                "question": q["question"],
                "type": "counterfactual",
                "as_of_year": year,
                "graph_path": path,
                "note": "S0基线无法模拟反事实，仅提供当前图结构",
            }

        elif qid == "Q8":
            emerging = self.query_emerging(top_k=10, year=year)
            coverage = self.query_coverage(year=year)
            return {
                "qid": qid,
                "question": q["question"],
                "type": "recommendation",
                "as_of_year": year,
                "emerging_topics": emerging["topics"][:5],
                "coverage_warning": {
                    "arabic_ratio": coverage["arabic_ratio"],
                    "sparse_count": coverage["sparse_topics_count"],
                },
                "note": "S0基线推荐基于历史增速，无预测和个性化能力",
            }

        return {"qid": qid, "error": "unknown question"}

    def generate_blind_review_materials(self, output_dir: str = None) -> dict:
        out = Path(output_dir) if output_dir else OUT_DIR / "blind_review"
        out.mkdir(parents=True, exist_ok=True)

        results = {"S0": {}, "S1": {}, "S2": {}, "generated_at": time.strftime("%Y-%m-%d %H:%M")}

        for q in LIBRARIAN_QUESTIONS:
            s0_answer = self.answer_question(q)
            results["S0"][q["qid"]] = s0_answer

            results["S1"][q["qid"]] = {
                "qid": q["qid"],
                "question": q["question"],
                "type": "S1_placeholder",
                "note": "S1 = S0 + XGBoost/普通时序趋势预测（待experiment_model_baseline填充）",
            }
            results["S2"][q["qid"]] = {
                "qid": q["qid"],
                "question": q["question"],
                "type": "S2_placeholder",
                "note": "S2 = S0 + RSSM多步预测 + 不确定性估计（待experiment_model_baseline填充）",
            }

        for level in ["S0", "S1", "S2"]:
            path = out / f"{level}_answers.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(results[level], f, ensure_ascii=False, indent=2)

        questions_path = out / "librarian_questions.json"
        with open(questions_path, "w", encoding="utf-8") as f:
            json.dump(LIBRARIAN_QUESTIONS, f, ensure_ascii=False, indent=2)

        return {
            "output_dir": str(out),
            "questions": len(LIBRARIAN_QUESTIONS),
            "levels": ["S0", "S1", "S2"],
            "files": [str(p) for p in out.glob("*")],
        }

    @staticmethod
    def _detect_language(paper: dict) -> str:
        import re
        title = str(paper.get("title", ""))
        if re.search(r'[\u0600-\u06FF]', title):
            return "ar"
        if re.search(r'[\u4e00-\u9fff]', title):
            return "zh"
        return "en"


def main():
    parser = argparse.ArgumentParser(description="S0 静态知识图谱服务基线")
    parser.add_argument("--as-of", type=int, default=2026, help="截止年份")
    parser.add_argument("--blind-review", action="store_true", help="生成盲评材料")
    parser.add_argument("--question", type=str, help="回答单个问题 (Q1-Q8)")
    args = parser.parse_args()

    sq = Neo4jServiceQuery(as_of_year=args.as_of)

    print("=" * 60)
    print(f"  S0 静态知识图谱服务基线 (as_of_year={args.as_of})")
    print("=" * 60)

    if args.blind_review:
        print("\n[>] 生成盲评材料...")
        result = sq.generate_blind_review_materials()
        print(f"  输出目录: {result['output_dir']}")
        print(f"  问题数: {result['questions']}")
        for f in result["files"]:
            print(f"  - {f}")
        sq.close()
        return

    if args.question:
        q = next((q for q in LIBRARIAN_QUESTIONS if q["qid"] == args.question), None)
        if q:
            answer = sq.answer_question(q)
            print(json.dumps(answer, ensure_ascii=False, indent=2))
        else:
            print(f"问题 {args.question} 不存在，可选: Q1-Q8")
        sq.close()
        return

    print("\n[1] 热点 Top-10:")
    hs = sq.query_hotspots(10)
    for t in hs["topics"]:
        print(f"  {t['name']:<20s} heat={t['heat']}  growth={t['growth']:+d}")

    print("\n[2] 新兴方向 Top-10:")
    em = sq.query_emerging(10)
    for t in em["topics"]:
        print(f"  {t['name']:<20s} growth={t['growth']:+d}  heat={t['heat']}")

    print("\n[3] 数据覆盖:")
    cov = sq.query_coverage()
    print(f"  总论文: {cov['total_papers']}")
    print(f"  语种分布: {cov['language_distribution']}")
    print(f"  阿语占比: {cov['arabic_ratio']:.1%}")
    print(f"  稀疏主题: {cov['sparse_topics_count']} 个")

    print("\n[4] 馆员问题集演示:")
    for q in LIBRARIAN_QUESTIONS[:3]:
        answer = sq.answer_question(q)
        print(f"  [{q['qid']}] {q['question'][:40]}...")
        print(f"    类型: {answer.get('type', 'N/A')}")

    sq.close()
    print(f"\n[OK] S0基线查询完成")


if __name__ == "__main__":
    main()
