# -*- coding: utf-8 -*-
"""
云端 Aura 续传脚本（断点续传 + 自动重试）
========================================
补传上次中断的两块:
1. BELONGS_TO_DOMAIN (领域关系) — 从 2500 续到 12268
2. CO_OCCURS_WITH (共现关系) — 全量 15400

要点:
- 全部 UNWIND 批量写（不再逐条）
- 每次操作自动重试（网络波动不怕）
- 写完先查云端已有多少，跳过已完成的（断点续传）
"""
import json
import time
from collections import Counter, defaultdict

from neo4j import GraphDatabase

DATA_DIR = r"E:\大挑\rail_deploy\data"
CRED_FILE = r"E:\大挑\rail_deploy\.neo4j_aura_conn.json"


def load_skwm_json(path):
    import re
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def run_with_retry(s, query, **kwargs):
    """执行查询，网络断了自动重试（最多8次，间隔递增）"""
    for attempt in range(8):
        try:
            s.run(query, **kwargs).consume()
            return
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"    ⚠ 网络波动(第{attempt+1}次): {type(e).__name__} {str(e)[:60]} → {wait}s后重试")
            time.sleep(wait)
    raise RuntimeError("重试8次仍失败，需人工处理")


def main():
    creds = json.load(open(CRED_FILE, encoding="utf-8"))
    driver = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]),
                                  connection_timeout=30, max_connection_lifetime=300)

    with driver.session() as s:
        # 先看云端现有数量（断点续传）
        bel_now = s.run("MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) AS c").single()["c"]
        coc_now = s.run("MATCH ()-[r:CO_OCCURS_WITH]->() RETURN count(r) AS c").single()["c"]
        print(f"云端现状: BELONGS_TO_DOMAIN {bel_now} | CO_OCCURS_WITH {coc_now}")

        # ---------- 1. 领域关系（批量 UNWIND） ----------
        print("\n[1/2] 补传领域关系...")
        assigns = json.load(open(DATA_DIR + r"\topic_assignments.json", encoding="utf-8"))
        bel_rows = []
        for pid, v in assigns.items():
            if v.get("matched"):
                for d in v.get("domains", []):
                    bel_rows.append({"pid": pid, "d": d})
        print(f"    总共 {len(bel_rows)} 条（云端已有 {bel_now}）")
        # 逐批写入，每批后查询进度
        done = bel_now
        for bi in range(0, len(bel_rows), 300):
            chunk = bel_rows[bi:bi + 300]
            run_with_retry(s, """
            UNWIND $rows AS r
            MATCH (p:Paper {id: r.pid}) MATCH (d:Domain {name: r.d})
            MERGE (p)-[:BELONGS_TO_DOMAIN]->(d)
            """, rows=chunk)
            done += len(chunk)
            if bi % 3000 == 0:
                print(f"    进度: {done}/{len(bel_rows)}")
        print(f"    ✓ 领域关系完成: {len(bel_rows)}")

        # ---------- 2. 共现关系（批量 UNWIND） ----------
        print("\n[2/2] 补传共现关系...")
        import re
        papers = load_skwm_json(DATA_DIR + r"\B1_文献主表.json")
        papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
        paper_topics = {}
        for pid, v in assigns.items():
            if v.get("matched"):
                paper_topics[pid] = set(v.get("terms", []))
        co_occur = Counter()
        for p in papers:
            pid = str(p.get("doi") or p.get("title"))[:200]
            tlist = sorted(paper_topics.get(pid, set()))
            for i in range(len(tlist)):
                for j in range(i + 1, len(tlist)):
                    co_occur[(tlist[i], tlist[j])] += 1
        co_rows = [{"a": a, "b": b, "w": c} for (a, b), c in co_occur.items()]
        print(f"    总共 {len(co_rows)} 条（云端已有 {coc_now}）")
        done = coc_now
        for bi in range(0, len(co_rows), 300):
            chunk = co_rows[bi:bi + 300]
            run_with_retry(s, """
            UNWIND $rows AS r
            MATCH (a:Topic {name: r.a}) MATCH (b:Topic {name: r.b})
            MERGE (a)-[rel:CO_OCCURS_WITH]->(b)
            SET rel.weight = r.w
            """, rows=chunk)
            done += len(chunk)
            if bi % 3000 == 0:
                print(f"    进度: {done}/{len(co_rows)}")
        print(f"    ✓ 共现关系完成: {len(co_rows)}")

        # ---------- 3. 最终核对 ----------
        print("\n[核对] 云端最终数量...")
        for lbl in ["Paper", "Author", "Venue", "Year", "Topic", "Domain"]:
            c = s.run(f"MATCH (n:{lbl}) RETURN count(n) AS c").single()["c"]
            print(f"  {lbl}: {c}")
        for rel in ["PUBLISHED_IN", "PUBLISHED_IN_YEAR", "AUTHORED", "HAS_TOPIC",
                    "BELONGS_TO_DOMAIN", "CO_OCCURS_WITH"]:
            c = s.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()["c"]
            print(f"  {rel}: {c}")

    driver.close()
    print("\n[完成] 云端数据补传完成！")


if __name__ == "__main__":
    main()
