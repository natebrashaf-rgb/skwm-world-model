# -*- coding: utf-8 -*-
"""
给 Neo4j 中的 Topic/Domain/Author 节点写入 birth_year 属性
============================================================
birth_year = 该实体最早关联 Paper 的年份（min_paper_year 规则，与快照一致）。
用法：py -3.14 set_birth_years.py
说明：写入是幂等的，可重复跑。
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j import GraphDatabase
from state_snapshot import load_papers, load_assignments, compute_entity_years, pid_of

CRED = json.load(open(r"E:\大挑\rail_deploy\.neo4j_cred.json", encoding="utf-8"))


def main():
    print("[1/3] 加载文献与分配...", flush=True)
    papers = load_papers()
    assignments = load_assignments()
    print(f"      文献 {len(papers)} | 分配 {len(assignments)}", flush=True)

    print("[2/3] 计算实体 birth_year (min_paper_year)...", flush=True)
    entity_years = compute_entity_years(papers, assignments, mode="min_paper_year")
    for t, m in entity_years.items():
        print(f"      {t}: {len(m)} 个实体")

    print("[3/3] 写入 Neo4j...", flush=True)
    driver = GraphDatabase.driver(CRED["uri"], auth=(CRED["user"], CRED["password"]))
    driver.verify_connectivity()
    with driver.session() as s:
        for label, mapping in entity_years.items():
            rows = [{"name": n, "y": y} for n, y in mapping.items() if y is not None]
            total = 0
            for bi in range(0, len(rows), 500):
                chunk = rows[bi:bi + 500]
                # label 是白名单（Topic/Domain/Author），无注入风险
                r = s.run(
                    f"""UNWIND $rows AS r
                    MATCH (n:{label} {{name: r.name}})
                    SET n.birth_year = r.y
                    RETURN count(n) AS c""",
                    rows=chunk
                )
                total += r.single()["c"]
            print(f"      {label}: 写入 {total} 个 birth_year", flush=True)
    driver.close()
    print("\n[完成] birth_year 已写入 Neo4j")


if __name__ == "__main__":
    main()
