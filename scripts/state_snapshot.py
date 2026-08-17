# -*- coding: utf-8 -*-
"""
年度知识状态快照生成器 + 时间切片工具
========================================
用途：
  1. 生成 state_YYYY.json 年度知识状态快照（M0-M2 回测输入）
     - 当年及之前的主题频次（heat）
     - 当年及之前的主题共现（累计权重）
     - 当年新增文献数
  2. 提供实体年份推导规则（显式参数，不默默定）

年份边界约定（已与用户确认）：
  as_of_year = Y 表示"站在 Y 年底"，year <= Y 的 Paper 全部可用。
  Topic/Author/Domain/Venue 无 year 属性，其"可用年份"按关联 Paper 推导。

实体年份推导规则（显式参数 entity_year_mode）：
  'min_paper_year'  : 实体最早关联 Paper 的年份（默认，最保守：当年首次出现才可用）
  'max_paper_year'  : 实体最晚关联 Paper 的年份（激进：只要曾关联过当年 Paper 即可）
  'median_paper_year': 关联 Paper 年份中位数（折中）
"""
import json
import os
import re
from collections import defaultdict, Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据源路径
# ---------------------------------------------------------------------------
B1_PATH = Path(r"E:\大挑\rail_deploy\data\B1_文献主表.json")
ASSIGN_PATH = Path(r"E:\大挑\rail_deploy\data\topic_assignments.json")
OUT_DIR = Path(r"E:\大挑\rail_deploy\data\state_snapshots")
ENTITY_YEAR_MODES = ("min_paper_year", "max_paper_year", "median_paper_year")


def load_skwm_json(path):
    """兼容带 _wm 伪键的 JSON"""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def load_papers():
    papers = load_skwm_json(B1_PATH)
    out = []
    for p in papers:
        if not isinstance(p, dict):
            continue
        y = p.get("year")
        try:
            y = int(y) if y is not None else None
        except (ValueError, TypeError):
            y = None
        if y is None:
            continue
        out.append({
            "doi": str(p.get("doi", "")),
            "title": str(p.get("title", "")),
            "year": y,
            "authors": str(p.get("authors", "")),
            "keywords": p.get("keywords") or p.get("normalized_keywords") or [],
        })
    return out


def load_assignments():
    ta = json.load(open(ASSIGN_PATH, encoding="utf-8"))
    # 返回 pid -> {terms, domains, matched, non_tourism}
    out = {}
    for k, v in ta.items():
        if isinstance(v, dict):
            out[k] = v
    return out


def pid_of(p):
    return str(p.get("doi") or p.get("title"))[:200]


# ---------------------------------------------------------------------------
# 实体年份推导
# ---------------------------------------------------------------------------
def compute_entity_years(papers, assignments, mode="min_paper_year"):
    """
    计算 Topic / Domain / Author 的"可用年份"。
    mode 见文件顶部 ENTITY_YEAR_MODES。
    返回 dict: {entity_type: {entity_name: year}}
    """
    if mode not in ENTITY_YEAR_MODES:
        raise ValueError(f"entity_year_mode 必须是 {ENTITY_YEAR_MODES} 之一, 收到: {mode}")

    topic_years = defaultdict(list)
    domain_years = defaultdict(list)
    author_years = defaultdict(list)

    for p in papers:
        pid = pid_of(p)
        y = p["year"]
        assign = assignments.get(pid) or assignments.get(p.get("title", ""))
        if not assign:
            continue
        if assign.get("matched"):
            for t in (assign.get("terms") or []):
                topic_years[t].append(y)
            for d in (assign.get("domains") or []):
                domain_years[d].append(y)
        elif assign.get("non_tourism"):
            domain_years["非文旅"].append(y)
        # 作者（从文献作者字段）
        authors = [a.strip() for a in re.split(r"[,;、]", p["authors"]) if len(a.strip()) > 2]
        for a in authors[:5]:
            author_years[a].append(y)

    def pick(vals):
        if not vals:
            return None
        if mode == "min_paper_year":
            return min(vals)
        if mode == "max_paper_year":
            return max(vals)
        if mode == "median_paper_year":
            s = sorted(vals)
            return s[len(s) // 2]

    return {
        "Topic": {name: pick(v) for name, v in topic_years.items() if pick(v) is not None},
        "Domain": {name: pick(v) for name, v in domain_years.items() if pick(v) is not None},
        "Author": {name: pick(v) for name, v in author_years.items() if pick(v) is not None},
    }


# ---------------------------------------------------------------------------
# 年度知识状态快照
# ---------------------------------------------------------------------------
def build_year_snapshot(as_of_year, papers, assignments, entity_years=None,
                        entity_year_mode="min_paper_year"):
    """
    生成 as_of_year 年的知识状态快照（只含 year <= as_of_year 的知识）。
    返回 dict:
      {
        "as_of_year": Y,
        "entity_year_mode": "min_paper_year",
        "papers_used": 当年及之前可用文献数,
        "papers_new_in_year": Y 年新增文献数,
        "topic_freq": {topic: 篇数},
        "domain_freq": {domain: 篇数},
        "topic_cooccur": {"t1||t2": 共现权重},
        "top_topics": 按频次排序前50,
        "topic_birth_year": {topic: 首次出现年份},
        "author_count": 当年可见作者数,
      }
    """
    # 1) 过滤文献
    usable = [p for p in papers if p["year"] <= as_of_year]
    new_in_year = [p for p in papers if p["year"] == as_of_year]

    # 2) 主题频次 / 领域频次
    topic_freq = Counter()
    domain_freq = Counter()
    topic_birth = {}
    topic_years_all = defaultdict(list)
    paper_topic = {}  # pid -> set(topics)

    for p in usable:
        pid = pid_of(p)
        assign = assignments.get(pid) or assignments.get(p.get("title", ""))
        if not assign:
            continue
        if assign.get("matched"):
            ts = set(assign.get("terms") or [])
            ds = set(assign.get("domains") or [])
            for t in ts:
                topic_freq[t] += 1
                topic_years_all[t].append(p["year"])
            for d in ds:
                domain_freq[d] += 1
            paper_topic[pid] = ts
        elif assign.get("non_tourism"):
            domain_freq["非文旅"] += 1

    # 主题诞生年（最早出现）
    for t, ys in topic_years_all.items():
        topic_birth[t] = min(ys)

    # 3) 主题共现（当年及之前的 Paper 重新聚合）
    cooccur = Counter()
    for pid, ts in paper_topic.items():
        tl = sorted(ts)
        for i in range(len(tl)):
            for j in range(i + 1, len(tl)):
                cooccur[f"{tl[i]}||{tl[j]}"] += 1

    # 4) 实体年份
    if entity_years is None:
        entity_years = compute_entity_years(usable, assignments, mode=entity_year_mode)

    # 当年可见主题 = birth_year <= as_of_year
    visible_topics = {t for t, by in topic_birth.items() if by <= as_of_year}

    return {
        "as_of_year": as_of_year,
        "entity_year_mode": entity_year_mode,
        "papers_used": len(usable),
        "papers_new_in_year": len(new_in_year),
        "topic_freq": dict(topic_freq),
        "domain_freq": dict(domain_freq),
        "topic_cooccur": dict(cooccur),
        "top_topics": topic_freq.most_common(50),
        "topic_birth_year": topic_birth,
        "visible_topic_count": len(visible_topics),
        "author_count": len(entity_years.get("Author", {})),
    }


def generate_snapshots(years, out_dir=None, entity_year_mode="min_paper_year"):
    """
    批量生成 state_YYYY.json。
    years: 年份列表，如 range(2018, 2025) 或 [2018, 2020, 2022, 2024]
    """
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/3] 加载文献...", flush=True)
    papers = load_papers()
    print(f"      文献 {len(papers)} 篇（有年份）", flush=True)

    print("[2/3] 加载主题分配...", flush=True)
    assignments = load_assignments()
    print(f"      分配 {len(assignments)} 条", flush=True)

    print(f"[3/3] 生成快照 ({entity_year_mode})...", flush=True)
    for y in sorted(years):
        snap = build_year_snapshot(y, papers, assignments, entity_year_mode=entity_year_mode)
        out_path = out_dir / f"state_{y}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
        print(f"      state_{y}.json: 文献{snap['papers_used']} 新增{snap['papers_new_in_year']} "
              f"主题{snap['visible_topic_count']} 共现{len(snap['topic_cooccur'])}", flush=True)

    print(f"\n[完成] 快照已生成: {out_dir}")
    return out_dir


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="年度知识状态快照生成器")
    parser.add_argument("--years", type=str, default="2018-2024",
                        help="年份范围: 2018-2024 或 2018,2020,2022")
    parser.add_argument("--out-dir", type=str, default=None)
    parser.add_argument("--entity-year-mode", type=str, default="min_paper_year",
                        choices=ENTITY_YEAR_MODES)
    args = parser.parse_args()

    if "-" in args.years and "," not in args.years:
        a, b = args.years.split("-")
        years = list(range(int(a), int(b) + 1))
    else:
        years = [int(x) for x in args.years.split(",")]

    generate_snapshots(years, args.out_dir, args.entity_year_mode)
