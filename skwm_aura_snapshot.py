# -*- coding: utf-8 -*-
"""
云端补传 SNAPSHOT（主题-年度热度）关系
=====================================
组员实测发现的问题：上传脚本 skwm_aura_upload.py 构建了 year_topic 数据
但漏了写入 SNAPSHOT 关系，导致云端缺 7463 条（105191-97728=7463）。
本脚本补传：
  (Topic)-[SNAPSHOT]->(Year)  with heat = 该主题该年论文数

与本地 rebuild_neo4j.py 的 SNAPSHOT 逻辑完全一致。
"""
import json
import re
import time
from collections import Counter

from neo4j import GraphDatabase

DATA_DIR = r"E:\大挑\rail_deploy\data"
CRED_FILE = r"E:\大挑\rail_deploy\.neo4j_aura_conn.json"


def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def to_year(y):
    try:
        return int(y)
    except (ValueError, TypeError):
        return 0


def run_with_retry(s, query, **kwargs):
    for attempt in range(10):
        try:
            s.run(query, **kwargs).consume()
            return
        except Exception as e:
            if attempt == 9:
                raise
            wait = 20 * (attempt + 1)
            print(f"    ⚠ 重试{attempt+1}: {type(e).__name__} {str(e)[:60]} → {wait}s")
            time.sleep(wait)


def main():
    creds = json.load(open(CRED_FILE, encoding="utf-8"))
    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]),
                                  connection_timeout=30, max_connection_lifetime=300)

    # 1. 从源头核算 SNAPSHOT（与 rebuild_neo4j.py 相同逻辑）
    print("[1/3] 从源头核算 SNAPSHOT...")
    papers = load_skwm_json(DATA_DIR + r"\B1_文献主表.json")
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    assigns = json.load(open(DATA_DIR + r"\topic_assignments.json", encoding="utf-8"))
    paper_topics = {}
    for pid, v in assigns.items():
        if v.get("matched"):
            paper_topics[pid] = set(v.get("terms", []))
    year_topic = Counter()
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        year = to_year(p.get("year"))
        for t in paper_topics.get(pid, set()):
            year_topic[(year, t)] += 1
    snap_rows = [{"t": t, "y": y, "heat": c} for (y, t), c in year_topic.items()]
    print(f"    核算出 SNAPSHOT {len(snap_rows)} 条")

    # 2. 写入云端（批量 UNWIND）
    print("[2/3] 写入云端...")
    with driver.session() as s:
        # 先确认云端现状
        v = run_with_retry(s, "MATCH ()-[r:SNAPSHOT]->() RETURN count(r) AS c")
        # 上面用的是 consume，改查一下
        now = s.run("MATCH ()-[r:SNAPSHOT]->() RETURN count(r) AS c").single()["c"] \
            if "SNAPSHOT" in [r[0] for r in s.run(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").values()] \
            else 0
        print(f"    云端现有 SNAPSHOT: {now}")
        done = now
        for bi in range(0, len(snap_rows), 300):
            chunk = snap_rows[bi:bi + 300]
            run_with_retry(s, """
            UNWIND $rows AS r
            MATCH (t:Topic {name: r.t})
            MATCH (y:Year {year: r.y})
            MERGE (t)-[rel:SNAPSHOT]->(y)
            SET rel.heat = r.heat
            """, rows=chunk)
            done += len(chunk)
            if bi % 3000 == 0:
                print(f"    进度: {done}/{len(snap_rows)}")
        print(f"    ✓ SNAPSHOT 完成: {done}")

    # 3. 最终核对
    print("[3/3] 核对...")
    with driver.session() as s:
        total = 0
        for rel in ["HAS_TOPIC", "AUTHORED", "CO_OCCURS_WITH", "BELONGS_TO_DOMAIN",
                    "PUBLISHED_IN", "PUBLISHED_IN_YEAR", "SNAPSHOT"]:
            v = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()["c"]
            total += v
            print(f"  {rel}: {v}")
        print(f"  合计: {total} (期望 105191)")

    driver.close()
    print("\n[完成]")


if __name__ == "__main__":
    main()
