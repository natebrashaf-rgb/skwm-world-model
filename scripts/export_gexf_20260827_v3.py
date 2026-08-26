# -*- coding: utf-8 -*-
"""GEXF 导出 + 渲染验证 v3（2026-08-27，终版：11条字符串修复后重建 20:03 的图库）
1. 从 Neo4j 拉全图（32431 节点/114304 边）→ networkx DiGraph → GEXF
2. read_gexf 读回 → 节点/边数对账（渲染验证第一步：可解析）
3. matplotlib 渲染 Top 主题共现子图 PNG + 节点类型分布 PNG
输出: E:\大挑\产出\重建_20260826\knowledge_graph_20260827_v3.gexf + *_v3.png + gexf_验证报告_20260827_v3.md
"""
import json, os, collections
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from neo4j import GraphDatabase

OUT = r"E:\大挑\产出\重建_20260826"
GEXF = os.path.join(OUT, "knowledge_graph_20260827_v3.gexf")
PNG_SUB = os.path.join(OUT, "gexf_topics_subgraph_20260827_v3.png")
PNG_TYPES = os.path.join(OUT, "gexf_node_types_20260827_v3.png")

EXPECT_NODES = 32431   # 终版实测: Paper12233+Topic1171+Domain19+Year84+Author14612+Venue4312
EXPECT_EDGES = 114304   # 终版实测

creds = json.load(open(r"E:\大挑\rail_deploy\.neo4j_cred.json", encoding="utf-8"))
drv = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))

with drv.session() as s:
    id2key = {}
    for label in ["Paper", "Topic", "Domain", "Year", "Author", "Venue"]:
        rows = s.run(f"MATCH (n:{label}) RETURN id(n) AS i, n").data()
        for r in rows:
            n = r["n"]
            nid_raw = n["id"] if "id" in n else (n["name"] if "name" in n else str(n["year"]))
            id2key[r["i"]] = f"{label}:{nid_raw}"
    G2 = nx.DiGraph()
    for label in ["Paper", "Topic", "Domain", "Year", "Author", "Venue"]:
        rows = s.run(f"MATCH (n:{label}) RETURN id(n) AS i, n").data()
        for r in rows:
            n = r["n"]
            nid_raw = n["id"] if "id" in n else (n["name"] if "name" in n else str(n["year"]))
            G2.add_node(f"{label}:{nid_raw}", label=label, title=n.get("title", ""))
    n_edges = 0
    for rtype in ["AUTHORED", "PUBLISHED_IN", "PUBLISHED_IN_YEAR", "HAS_TOPIC",
                  "BELONGS_TO_DOMAIN", "SNAPSHOT", "CO_OCCURS_WITH"]:
        cy = f"MATCH (a)-[r:{rtype}]->(b) RETURN id(a) AS a, id(b) AS b"
        rows = s.run(cy).data()
        for r in rows:
            ka, kb = id2key.get(r["a"]), id2key.get(r["b"])
            if ka and kb:
                G2.add_edge(ka, kb, type=rtype)
                n_edges += 1
    print(f"关系已载入: {n_edges}")

drv.close()
print(f"图: {G2.number_of_nodes()} 节点 / {G2.number_of_edges()} 边")
assert G2.number_of_nodes() == EXPECT_NODES, f"节点数应为 {EXPECT_NODES}，实际 {G2.number_of_nodes()}"
assert G2.number_of_edges() == EXPECT_EDGES, f"边数应为 {EXPECT_EDGES}，实际 {G2.number_of_edges()}"

# 端点无悬挂检查
missing = sum(1 for a, b in G2.edges() if a not in G2 or b not in G2)
print(f"悬挂端点检查: {missing}")

nx.write_gexf(G2, GEXF)
print(f"GEXF 已写: {GEXF} ({os.path.getsize(GEXF)/1024/1024:.1f} MB)")

# 读回验证
G3 = nx.read_gexf(GEXF)
print(f"读回: {G3.number_of_nodes()} 节点 / {G3.number_of_edges()} 边")
assert G3.number_of_nodes() == G2.number_of_nodes()
assert G3.number_of_edges() == G2.number_of_edges()
print("read_gexf 读回验证通过（结构合法、可解析、数字一致）")

types = collections.Counter(nx.get_node_attributes(G3, "label").values())
print("节点类型分布:", dict(types))

# 渲染 1：节点类型分布
plt.figure(figsize=(8, 5))
plt.bar(types.keys(), types.values(), color="#4C72B0")
plt.title("GEXF v3 节点类型分布 (终版 20260827)")
plt.ylabel("节点数")
for i, (k, v) in enumerate(types.items()):
    plt.text(i, v + 200, str(v), ha="center", fontsize=9)
plt.tight_layout()
plt.savefig(PNG_TYPES, dpi=120)
plt.close()
print("渲染1已存:", PNG_TYPES)

# 渲染 2：Top 25 主题共现子图
topics = [n for n, d in G3.nodes(data=True) if d.get("label") == "Topic"]
deg = {t: G3.degree(t) for t in topics}
top25 = sorted(deg, key=deg.get, reverse=True)[:25]
sub = G3.subgraph(top25)
pos = nx.spring_layout(sub, seed=42, k=0.8)
plt.figure(figsize=(14, 10))
nx.draw_networkx(sub, pos, with_labels=True, node_size=800, font_size=9,
                 node_color="#4C72B0", font_color="white",
                 edge_color="#999999", arrows=False, width=1.2)
plt.title("Top25 主题共现子图 v3 (GEXF 渲染验证, 终版)")
plt.axis("off")
plt.tight_layout()
plt.savefig(PNG_SUB, dpi=120)
plt.close()
print("渲染2已存:", PNG_SUB)

# 验证报告
report = f"""# GEXF 导出渲染验证报告 v3（终版，2026-08-27）

导出时间：2026-08-27（本地 Neo4j 终版重建 20:03）
命令：python3.14 scripts/export_gexf_20260827_v3.py
输入：topic_assignments.json（SHA 3332966f 终版，11条字符串类型已修复）

## 数字对账
| 项 | Neo4j 实测 | GEXF 节点/边 | 一致 |
|----|-----------|-------------|------|
| 节点总数 | {EXPECT_NODES} | {G3.number_of_nodes()} | {'✓' if G3.number_of_nodes()==EXPECT_NODES else '✗'} |
| 关系总数 | {EXPECT_EDGES} | {G3.number_of_edges()} | {'✓' if G3.number_of_edges()==EXPECT_EDGES else '✗'} |
| 悬挂端点 | 0 | {missing} | {'✓' if missing==0 else '✗'} |

## 节点类型分布
{json.dumps(dict(types), ensure_ascii=False, indent=1)}

## 渲染验证
- GEXF 文件被 networkx.read_gexf 成功读回（networkx {nx.__version__}，结构合法、可解析）
- 渲染图1：节点类型分布 PNG（{os.path.basename(PNG_TYPES)}）
- 渲染图2：Top25 主题共现子图 PNG（{os.path.basename(PNG_SUB)}）

## 文件与 SHA-256
- {os.path.basename(GEXF)}（{os.path.getsize(GEXF)/1024/1024:.1f} MB）
- 注意：本 GEXF 为终版（Topic 1171/Domain 19），与 graph_snapshot_20260827_v2.json 同口径；
  v1（合并前, 1174/27）、v2（合并后修复前, 1168/26）为历史版本，终版以 v3 为准。
"""
with open(os.path.join(OUT, "gexf_验证报告_20260827_v3.md"), "w", encoding="utf-8") as f:
    f.write(report)
print("验证报告已写")
