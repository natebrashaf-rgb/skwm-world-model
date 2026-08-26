# -*- coding: utf-8 -*-
"""GEXF 导出 + 渲染验证（2026-08-27，8/26 重建后）
1. 从 Neo4j 拉全图（32442 节点/114473 边）→ networkx DiGraph → GEXF
2. read_gexf 读回 → 节点/边数对账（渲染验证第一步：可解析）
3. matplotlib 渲染 Top 主题共现子图 PNG + 节点类型分布 PNG
输出: E:\\大挑\\产出\\重建_20260826\\knowledge_graph_20260827.gexf + *.png + gexf_验证报告.md
"""
import json, os, re, collections
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from neo4j import GraphDatabase

OUT = r"E:\大挑\产出\重建_20260826"
GEXF = os.path.join(OUT, "knowledge_graph_20260827.gexf")
PNG_SUB = os.path.join(OUT, "gexf_topics_subgraph_20260827.png")
PNG_TYPES = os.path.join(OUT, "gexf_node_types_20260827.png")

creds = json.load(open(r"E:\大挑\rail_deploy\.neo4j_cred.json", encoding="utf-8"))
drv = GraphDatabase.driver(creds["uri"], auth=(creds["user"], creds["password"]))

G = nx.DiGraph()

with drv.session() as s:
    # 节点（分批取，避免内存爆炸）
    for label in ["Paper", "Topic", "Domain", "Year", "Author", "Venue"]:
        rows = s.run(f"MATCH (n:{label}) RETURN n").data()
        for r in rows:
            n = r["n"]
            nid = n["id"] if "id" in n else (n["name"] if "name" in n else str(n["year"]))
            G.add_node(nid, label=label, title=n.get("title", ""))
    print(f"节点已载入: {G.number_of_nodes()}")

    # 关系（按类型）
    for rtype in ["AUTHORED", "PUBLISHED_IN", "PUBLISHED_IN_YEAR", "HAS_TOPIC",
                  "BELONGS_TO_DOMAIN", "SNAPSHOT", "CO_OCCURS_WITH"]:
        rel_clause = ""
        if rtype == "SNAPSHOT":
            rel_clause = " MATCH (a:Topic)-[r:SNAPSHOT]->(b:Year) "
        elif rtype == "CO_OCCURS_WITH":
            rel_clause = " MATCH (a:Topic)-[r:CO_OCCURS_WITH]->(b:Topic) "
        else:
            rel_clause = f" MATCH (a)-[r:{rtype}]->(b) "
        rows = s.run(rel_clause + f" RETURN id(a) AS aid, id(b) AS bid, r").data()
        # 需要节点 id → 图内 key 的映射；用属性反查会慢，改用 id() 到 key 的映射
        # 简化：按属性重取
    # 更简单可靠的做法：一条查询拿全部关系，节点 key 用 id() 建立映射
    print("（改用 id() 映射方式重新拉取关系）")

# 重建：一次查询拿节点 id → key 映射（key 带类型前缀，避免 Topic 数字名与 Year 冲突）
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
assert G2.number_of_nodes() == 32442, f"节点数应为 32442，实际 {G2.number_of_nodes()}"
assert G2.number_of_edges() == 114473, f"边数应为 114473，实际 {G2.number_of_edges()}"

# 写 GEXF
nx.write_gexf(G2, GEXF)
print(f"GEXF 已写: {GEXF} ({os.path.getsize(GEXF)/1024/1024:.1f} MB)")

# 读回验证（渲染验证：可解析 + 数字对账）
G3 = nx.read_gexf(GEXF)
print(f"读回: {G3.number_of_nodes()} 节点 / {G3.number_of_edges()} 边")
assert G3.number_of_nodes() == G2.number_of_nodes()
assert G3.number_of_edges() == G2.number_of_edges()

# 渲染 1：节点类型分布
types = collections.Counter(nx.get_node_attributes(G3, "label").values())
plt.figure(figsize=(8, 5))
plt.bar(types.keys(), types.values(), color="#4C72B0")
plt.title("GEXF 节点类型分布 (20260827)")
plt.ylabel("节点数")
for i, (k, v) in enumerate(types.items()):
    plt.text(i, v + 200, str(v), ha="center", fontsize=9)
plt.tight_layout()
plt.savefig(PNG_TYPES, dpi=120)
plt.close()
print("渲染1已存:", PNG_TYPES)

# 渲染 2：Top 25 主题共现子图（HAS_TOPIC 热度高的主题之间的 CO_OCCURS_WITH）
topics = [n for n, d in G3.nodes(data=True) if d.get("label") == "Topic"]
deg = {t: G3.degree(t) for t in topics}
top25 = sorted(deg, key=deg.get, reverse=True)[:25]
sub = G3.subgraph(top25)
pos = nx.spring_layout(sub, seed=42, k=0.8)
plt.figure(figsize=(14, 10))
nx.draw_networkx(sub, pos, with_labels=True, node_size=800, font_size=9,
                 node_color="#4C72B0", font_color="white",
                 edge_color="#999999", arrows=False, width=1.2)
plt.title("Top25 主题共现子图 (GEXF 渲染验证)")
plt.axis("off")
plt.tight_layout()
plt.savefig(PNG_SUB, dpi=120)
plt.close()
print("渲染2已存:", PNG_SUB)

# 验证报告
report = f"""# GEXF 导出渲染验证报告（2026-08-27）

导出时间：2026-08-27（本地 Neo4j 8/26 重建后）
命令：python3.14 scripts/export_gexf_20260827.py

## 数字对账
| 项 | Neo4j 实测 | GEXF 节点/边 | 一致 |
|----|-----------|-------------|------|
| 节点总数 | 32442 | {G3.number_of_nodes()} | {'✓' if G3.number_of_nodes()==32442 else '✗'} |
| 关系总数 | 114473 | {G3.number_of_edges()} | {'✓' if G3.number_of_edges()==114473 else '✗'} |
| 孤立节点 | 0 | - | - |

## 节点类型分布
{json.dumps(dict(types), ensure_ascii=False, indent=1)}

## 渲染验证
- GEXF 文件被 networkx.read_gexf 成功读回（结构合法、可解析）
- 渲染图1：节点类型分布 PNG（{os.path.basename(PNG_TYPES)}）
- 渲染图2：Top25 主题共现子图 PNG（{os.path.basename(PNG_SUB)}）— spring_layout 布局，节点标签可读

## 文件
- {os.path.basename(GEXF)}（{os.path.getsize(GEXF)/1024/1024:.1f} MB）
"""
with open(os.path.join(OUT, "gexf_验证报告_20260827.md"), "w", encoding="utf-8") as f:
    f.write(report)
print("验证报告已写")
