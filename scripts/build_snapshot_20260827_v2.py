# -*- coding: utf-8 -*-
"""图库聚合层快照 20260827 v2（终版：11条字符串修复后重建，2026-08-26 20:03）
用途：给 GitHub/Manus 读图。仅聚合层，不含全文PDF、不含作者个人字段。
口径：与 rebuild_neo4j.py 完全一致（同一篇内主题词去重；year 仅 0<year<=2026 计入）。
计数：直接取自 Neo4j 实测（终版重建：Paper 12233/Topic 1171/HAS_TOPIC 29491/关系 114304/孤立0）。
"""
import json, os, csv
from collections import Counter

DATA = r"E:\大挑\rail_deploy\data"
OUT = r"E:\大挑\产出\重建_20260826"
CRED = r"E:\大挑\rail_deploy\.neo4j_cred.json"

def to_int(x):
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return 0

# 1. 加载
b1 = json.load(open(os.path.join(DATA, "B1_文献主表.json"), encoding="utf-8"))
ta = json.load(open(os.path.join(DATA, "topic_assignments.json"), encoding="utf-8"))
print(f"加载: B1 {len(b1)} | topic_assignments {len(ta)}")

# 2. 复刻 rebuild 聚合
paper_topics = {}
paper_domains = {}
non_tourism = set()
for pid, v in ta.items():
    if v.get("matched"):
        paper_topics[pid] = set(v.get("terms", []))
        paper_domains[pid] = set(v.get("domains", []))
    elif v.get("non_tourism"):
        non_tourism.add(pid)

year_topic = Counter()
for p in b1:
    pid = str(p.get("doi") or p.get("title"))[:200]
    year = to_int(p.get("year"))
    year_valid = 0 < year <= 2026
    for t in paper_topics.get(pid, set()):
        if year_valid:
            year_topic[(year, t)] += 1

n_has_topic = sum(len(t) for t in paper_topics.values())
n_year_valid = sum(year_topic.values())
print(f"HAS_TOPIC 复刻: {n_has_topic} | year_topic 有效和: {n_year_valid}")

# 3. Neo4j 实测计数（8/26 重建后）
from neo4j import GraphDatabase
creds = json.load(open(CRED, encoding="utf-8"))
drv = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))
with drv.session() as s:
    node_counts = {r["l"]: r["c"] for r in s.run(
        "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c").data()}
    edge_counts = {r["t"]: r["c"] for r in s.run(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c").data()}
    node_total = s.run("MATCH (n) RETURN count(n)").single()[0]
    edge_total = s.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
    isolated = s.run("MATCH (n) WHERE NOT (n)--() RETURN count(n)").single()[0]
drv.close()
print("Neo4j 实测:", node_counts, edge_counts, f"孤立={isolated}")

# 4. 节点清单
paper_nodes = []
seen_pid = set()
for p in b1:
    pid = str(p.get("doi") or p.get("title"))[:200]
    if pid in seen_pid:
        continue
    seen_pid.add(pid)
    paper_nodes.append({"id": pid, "title": p.get("title", "")})

topic_names = sorted(set().union(*[paper_topics[pid] for pid in paper_topics]))
years = sorted({to_int(p.get("year")) for p in b1 if 0 < to_int(p.get("year")) <= 2026})
domains = sorted(set().union(*[paper_domains[pid] for pid in paper_domains]) | {"非文旅"})
print(f"节点: Paper {len(paper_nodes)} | Topic {len(topic_names)} | Year {len(years)} | Domain {len(domains)}")

heat = [{"topic": t, "year": y, "count": c} for (y, t), c in year_topic.items()]
heat.sort(key=lambda r: (-r["count"], r["year"], r["topic"]))
print(f"topic×year 热度: {len(heat)} 行 | 计数 {sum(r['count'] for r in heat)}")

# 5. 写 JSON（文件名带日期 20260827）
snap = {
    "meta": {
        "file": "graph_snapshot_20260827_v2.json",
        "generated_at": "2026-08-27",
        "generated_by": "build_snapshot_20260827_v2.py（复刻 rebuild_neo4j.py 聚合口径；计数取 Neo4j 实测）",
        "source": "本地 Neo4j 图库（2026-08-26 20:03 终版重建：topic_assignments SHA 3332966f，B1主表12233含56篇补录+27条language=ar）",
        "purpose": "给 GitHub/Manus 读图用；仅聚合层",
        "change_note": "相对上版 v1(20260827, 1168版)：11条字符串类型修复后重建（Topic 1168→1171、HAS_TOPIC 29639→29491、BEL_DOM 17250→17173、共现 17441→17229、SNAPSHOT 7467→7363、关系 114845→114304、Domain 26→19单字消失）",
        "rules": [
            "不含全文 PDF/正文文本",
            "不含作者个人字段（Author 节点仅计数，不导明细）",
            "year<=0 或 >2026 的 Paper 保留节点但无 Year 关系/PUBLISHED_IN_YEAR（rebuild 口径）",
            "同一篇内重复主题词已去重（set），与 HAS_TOPIC 关系数一致",
        ],
        "counts_verify": {
            "HAS_TOPIC_复刻": n_has_topic,
            "HAS_TOPIC_实测": edge_counts.get("HAS_TOPIC", 0),
            "year_topic_有效和": n_year_valid,
            "year_topic_无效年份边": n_has_topic - n_year_valid,
            "Topic_复刻": len(topic_names),
            "Topic_实测": node_counts.get("Topic", 0),
            "Domain_复刻": len(domains),
            "Domain_实测": node_counts.get("Domain", 0),
            "Year_复刻": len(years),
            "Year_实测": node_counts.get("Year", 0),
            "Paper_实测": node_counts.get("Paper", 0),
        },
    },
    "node_counts": node_counts,
    "node_total": node_total,
    "edge_counts": edge_counts,
    "edge_total": edge_total,
    "isolated_nodes": isolated,
    "nodes": {
        "Paper": paper_nodes,
        "Topic": [{"name": t} for t in topic_names],
        "Year": [{"year": y} for y in years],
        "Domain": [{"name": d} for d in domains],
        "Author": {"count": node_counts.get("Author", 0), "note": "个人字段不导出"},
        "Venue": {"count": node_counts.get("Venue", 0), "note": "期刊名，聚合层仅计数"},
    },
    "topic_year_heat": heat,
}

p_json = os.path.join(OUT, "graph_snapshot_20260827_v2.json")
with open(p_json, "w", encoding="utf-8") as f:
    json.dump(snap, f, ensure_ascii=False, indent=1)
print("写入:", p_json, os.path.getsize(p_json), "bytes")

p_csv = os.path.join(OUT, "topic_year_heat_20260827_v2.csv")
with open(p_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["topic", "year", "count"])
    w.writeheader()
    w.writerows(heat)
print("写入:", p_csv, len(heat), "行")
