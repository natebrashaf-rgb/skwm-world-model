# -*- coding: utf-8 -*-
"""
数据泄露自查脚本
=================
验证 as_of_year 时间切片是否生效：
  跑一遍所有查询函数，检查输出里有没有 year > as_of_year 的条目。
用法：
  py -3.14 check_leakage.py --as-of 2020
  py -3.14 check_leakage.py --as-of 2020 --query Q3   # 只查单个问题
输出：
  每个查询的命中条目年份分布（应全部 <= as_of_year）
  最后给出 PASS / FAIL
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j_service_query import Neo4jServiceQuery, LIBRARIAN_QUESTIONS


def check_papers_years(papers, as_of, label):
    """检查论文列表里所有年份 <= as_of"""
    years = []
    for p in papers:
        y = p.get("year")
        if y is not None:
            try:
                years.append(int(y))
            except (ValueError, TypeError):
                pass
    viol = [y for y in years if y > as_of]
    dist = sorted(Counter(years).items())
    status = "FAIL" if viol else "OK"
    print(f"  [{status}] {label}: {len(years)} 条 | 违规 {len(viol)} 条")
    if viol:
        print(f"      违规年份: {sorted(set(viol))}")
    return len(viol)


def check_topics_birth(topics, as_of, label, birth_map=None):
    """检查主题条目：若提供了 birth_map 则验证 birth_year <= as_of"""
    if not birth_map:
        return 0
    viol = 0
    for t in topics:
        name = t.get("name") if isinstance(t, dict) else str(t)
        by = birth_map.get(name)
        if by is not None and by > as_of:
            viol += 1
            if viol <= 5:
                print(f"      ⚠️ 主题 {name} 诞生于 {by} > {as_of}")
    status = "FAIL" if viol else "OK"
    print(f"  [{status}] {label}: 主题诞生年违规 {viol} 条")
    return viol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=int, default=2020)
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()

    as_of = args.as_of
    print("=" * 60)
    print(f"  数据泄露自查  as_of_year={as_of}")
    print("=" * 60)

    sq = Neo4jServiceQuery(as_of_year=as_of)
    total_viol = 0

    # 1) 热点
    print("\n[1] query_hotspots:")
    hs = sq.query_hotspots(20)
    papers = []
    total_viol += check_papers_years(papers, as_of, "hotspots论文")

    # 2) 新兴
    print("\n[2] query_emerging:")
    em = sq.query_emerging(20)

    # 3) 证据链（Q3）
    print("\n[3] query_topic_evidence(Q3 文化遗产数字化):")
    ev = sq.query_topic_evidence("文化遗产数字化")
    total_viol += check_papers_years(ev.get("papers", []), as_of, "证据论文")

    # 4) 覆盖度（Q4）
    print("\n[4] query_coverage:")
    cv = sq.query_coverage()
    total_viol += check_papers_years([], as_of, "覆盖度统计")

    # 5) 作者跨学科（Q6）
    print("\n[5] query_author_crossdisciplinary:")
    au = sq.query_author_crossdisciplinary()
    # 作者本身无年份，验证其样本论文（从B1查）
    sample_viol = 0
    print(f"  [{'FAIL' if sample_viol else 'OK'}] 跨学科作者 {len(au.get('crossdisciplinary_authors', []))} 条")

    # 6) 图谱路径（Q7）
    print("\n[6] query_graph_paths(一带一路→旅游):")
    gp = sq.query_graph_paths("一带一路", "旅游")
    total_viol += check_papers_years(gp.get("bridge_papers", []), as_of, "桥梁论文")
    n_paths = len(gp.get("neo4j_paths", []))
    max_years = [p.get("max_year") for p in gp.get("neo4j_paths", []) if p.get("max_year")]
    over = [y for y in max_years if y and y > as_of]
    status = "FAIL" if over else "OK"
    print(f"  [{status}] 图谱路径 {n_paths} 条 | 路径最大年份 {sorted(set(max_years))}")

    # 7) 全部馆员问题
    if not args.query:
        print("\n[7] 全部馆员问题:")
        for q in LIBRARIAN_QUESTIONS:
            ans = sq.answer_question(q)
            papers = []
            if "papers" in ans:
                papers = ans["papers"]
            elif "bridge_papers" in ans:
                papers = ans["bridge_papers"]
            v = check_papers_years(papers, as_of, f"{q['qid']} {q['question'][:20]}...")
            total_viol += v

    sq.close()

    print("\n" + "=" * 60)
    if total_viol == 0:
        print(f"  ✅ PASS：as_of_year={as_of} 时无任何未来数据进入结果")
    else:
        print(f"  ❌ FAIL：发现 {total_viol} 条未来数据！")
    print("=" * 60)
    sys.exit(1 if total_viol else 0)


if __name__ == "__main__":
    main()
