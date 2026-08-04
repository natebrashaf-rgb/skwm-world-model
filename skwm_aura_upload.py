# -*- coding: utf-8 -*-
"""
本地 Neo4j → 云端 Aura 传输脚本
================================
从源头文件（主表/主题分配）重建数据，直接写入云端 Aura 实例。
复用 rebuild_neo4j.py 的数据处理逻辑，连接目标改为云端。

要点（技能经验）:
- UNWIND 500 条一批，不用逐条写（快几十倍）
- 节点和关系分开 MERGE（避免唯一约束冲突）
- 先建唯一约束，再写数据
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

from neo4j import GraphDatabase

DATA_DIR = r"E:\大挑\rail_deploy\data"
MAIN_TABLE = os.path.join(DATA_DIR, "B1_文献主表.json")
ASSIGNMENTS = os.path.join(DATA_DIR, "topic_assignments.json")
PDF_TEXTS = os.path.join(DATA_DIR, "pdf_texts.json")
CRED_FILE = r"E:\大挑\rail_deploy\.neo4j_aura_conn.json"


def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def split_authors(authors: str):
    if not authors:
        return []
    parts = re.split(r"[,;，；、]|\s+and\s+|\s+&\s+", authors)
    return [p.strip() for p in parts if p.strip()]


def to_year(y):
    try:
        return int(y)
    except (ValueError, TypeError):
        return 0


def main():
    creds = json.load(open(CRED_FILE, encoding="utf-8"))
    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))
    driver.verify_connectivity()
    print("[OK] 已连接云端:", creds["uri"].replace("neo4j+s://", ""))

    # 1. 加载源头
    print("[1/6] 加载数据...")
    papers = load_skwm_json(MAIN_TABLE)
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    assigns = json.load(open(ASSIGNMENTS, encoding="utf-8"))
    print(f"    论文 {len(papers)} | 匹配结果 {len(assigns)}")

    # 2. 论文→主题/领域
    paper_topics = {}
    paper_domains = {}
    for pid, v in assigns.items():
        if v.get("matched"):
            paper_topics[pid] = set(v.get("terms", []))
            paper_domains[pid] = set(v.get("domains", []))

    # 3. 构建批量数据
    print("[2/6] 构建批量数据...")
    paper_rows = []
    topic_papers = defaultdict(set)
    domain_papers = defaultdict(set)
    co_occur = Counter()
    year_topic = Counter()
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        year = to_year(p.get("year"))
        venue = (p.get("venue") or "").strip() or "未知"
        paper_rows.append({
            "pid": pid, "title": p.get("title", ""), "year": year,
            "citations": p.get("citations", 0), "venue": venue,
            "authors": split_authors(p.get("authors", "")),
        })
        topics = paper_topics.get(pid, set())
        domains = paper_domains.get(pid, set())
        for t in topics:
            topic_papers[t].add(pid)
            year_topic[(year, t)] += 1
        for d in domains:
            domain_papers[d].add(pid)
        tlist = sorted(topics)
        for i in range(len(tlist)):
            for j in range(i + 1, len(tlist)):
                co_occur[(tlist[i], tlist[j])] += 1

    # 4. 写入云端
    with driver.session() as s:
        print("[3/6] 建唯一约束...")
        for stmt in [
            "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT venue_name IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS UNIQUE",
            "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT year_val IF NOT EXISTS FOR (y:Year) REQUIRE y.year IS UNIQUE",
        ]:
            try:
                s.run(stmt)
            except Exception as e:
                print(f"    约束跳过: {str(e)[:80]}")

        print("[4/6] 写入论文/作者/期刊/年份...")
        for bi in range(0, len(paper_rows), 500):
            chunk = paper_rows[bi:bi + 500]
            s.run("""
            UNWIND $rows AS r
            MERGE (p:Paper {id: r.pid})
            SET p.title = r.title, p.year = r.year, p.citations = r.citations
            MERGE (v:Venue {name: r.venue})
            MERGE (p)-[:PUBLISHED_IN]->(v)
            MERGE (y:Year {year: r.year})
            MERGE (p)-[:PUBLISHED_IN_YEAR]->(y)
            FOREACH (a IN r.authors |
                MERGE (au:Author {name: a})
                MERGE (au)-[:AUTHORED]->(p)
            )
            """, rows=chunk)
        print(f"    论文 {len(paper_rows)} 已写入")

        print("[5/6] 写入主题/领域/共现...")
        topic_rows = [{"t": t} for t in sorted(topic_papers)]
        for bi in range(0, len(topic_rows), 500):
            s.run("UNWIND $rows AS r MERGE (t:Topic {name: r.t})", rows=topic_rows[bi:bi + 500])
        dom_rows = [{"d": d} for d in sorted(domain_papers)]
        for bi in range(0, len(dom_rows), 500):
            s.run("UNWIND $rows AS r MERGE (d:Domain {name: r.d})", rows=dom_rows[bi:bi + 500])

        link_rows = [{"pid": pid, "t": t} for pid, topics in paper_topics.items() for t in topics]
        for bi in range(0, len(link_rows), 500):
            s.run("""
            UNWIND $rows AS r
            MATCH (p:Paper {id: r.pid})
            MATCH (t:Topic {name: r.t})
            MERGE (p)-[:HAS_TOPIC]->(t)
            """, rows=link_rows[bi:bi + 500])
        for pid, domains in paper_domains.items():
            for d in domains:
                s.run("MATCH (p:Paper {id: $pid}) MATCH (d:Domain {name: $d}) MERGE (p)-[:BELONGS_TO_DOMAIN]->(d)",
                      pid=pid, d=d)
        print(f"    HAS_TOPIC {len(link_rows)} | BELONGS_TO_DOMAIN {sum(len(v) for v in paper_domains.values())}")

        print("[6/6] 写入共现边...")
        co_rows = [{"a": a, "b": b, "w": c} for (a, b), c in co_occur.items()]
        for bi in range(0, len(co_rows), 500):
            s.run("""
            UNWIND $rows AS r
            MATCH (a:Topic {name: r.a}) MATCH (b:Topic {name: r.b})
            MERGE (a)-[rel:CO_OCCURS_WITH]->(b)
            SET rel.weight = r.w
            """, rows=co_rows[bi:bi + 500])
        print(f"    共现边 {len(co_rows)}")

    driver.close()
    print("\n[完成] 云端数据写入成功！")
    print(f"主题数 {len(topic_papers)} | 领域数 {len(domain_papers)} | 共现边 {len(co_rows)}")


if __name__ == "__main__":
    main()
