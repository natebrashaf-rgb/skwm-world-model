#!/usr/bin/env python3
"""
SKWM ETL: B1 JSON → ChromaDB + NetworkX Graph
=============================================
一次性脚本，把 11601 篇文献和 state_vectors 建成图数据库。
跑完以后 skwm_qa_api.py 的图检索功能就能用。
"""
import json, re, hashlib, os, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"

# ── 加载 B1 文献 ──
print("📖 加载 B1_文献主表.json...")
b1_path = DATA_DIR / "B1_文献主表.json"
raw = b1_path.read_text(encoding='utf-8')
raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
idx = raw.find('{', raw.find('{') + 1)
papers = json.loads('[' + raw[idx:])
print(f"  ✅ {len(papers)} 篇文献")

# ── 加载 state_vectors ──
print("📊 加载 state_vectors.json...")
sv_path = DATA_DIR / "state_vectors.json"
sv = json.loads(sv_path.read_text(encoding='utf-8'))
print(f"  ✅ {len(sv)} 个年份")

# ── 构建 NetworkX 图 ──
print("🕸️ 构建知识图谱...")
try:
    import networkx as nx
except ImportError:
    print("  安装 networkx...")
    os.system(f"{sys.executable} -m pip install networkx")
    import networkx as nx

G = nx.DiGraph()

# 1. 添加论文节点
for p in papers:
    pid = hashlib.md5((p.get('doi','') or p.get('title','')).encode()).hexdigest()[:12]
    G.add_node(pid, type='paper', title=p.get('title',''), year=int(p.get('year',0) or 0),
               doi=p.get('doi',''), authors=p.get('authors',''))

# 2. 添加主题节点 + HAS_TOPIC 边
for p in papers:
    pid = hashlib.md5((p.get('doi','') or p.get('title','')).encode()).hexdigest()[:12]
    for kw in (p.get('keywords') or []):
        if kw and kw.strip():
            G.add_node(kw.strip(), type='topic')
            G.add_edge(pid, kw.strip(), relation='has_topic')

# 3. 添加作者节点 + AUTHORED_BY 边
for p in papers:
    pid = hashlib.md5((p.get('doi','') or p.get('title','')).encode()).hexdigest()[:12]
    authors_str = p.get('authors','')
    if authors_str:
        for i, author in enumerate(authors_str.split(',')):
            author = author.strip().title()
            if author and len(author) > 1:
                G.add_node(author, type='author')
                G.add_edge(pid, author, relation='authored_by', rank=i+1)

# 4. 添加时序快照（state_vectors）
for year_str, entities in sv.items():
    if year_str == '_wm': continue
    year = int(year_str)
    year_node = f'Y{year}'
    G.add_node(year_node, type='year', year=year)
    for name, vec in entities.items():
        G.add_node(name, type='topic')
        G.add_edge(name, year_node, relation='has_snapshot',
                   heat=vec[0], growth=vec[1], centrality=vec[2], connections=vec[3])

print(f"\n  ✅ 图构建完成：{G.number_of_nodes()} 节点, {G.number_of_edges()} 边")
print(f"     论文: {sum(1 for n in G.nodes if G.nodes[n].get('type')=='paper')}")
print(f"     主题: {sum(1 for n in G.nodes if G.nodes[n].get('type')=='topic')}")
print(f"     作者: {sum(1 for n in G.nodes if G.nodes[n].get('type')=='author')}")

# 5. 导出
print("\n💾 导出到 data/knowledge_graph.gexf...")
nx.write_gexf(G, str(DATA_DIR / "knowledge_graph.gexf"))
print("  ✅ 已保存")

# 6. 导出精简版节点列表（供 QA 检索用）
print("💾 导出精简版节点索引...")
node_index = {}
for n, attr in G.nodes(data=True):
    if attr.get('type') == 'topic':
        node_index[n] = {'type': 'topic'}
        # 找最近的 year 热度
        for _, neighbor, data in G.edges(n, data=True):
            if data.get('relation') == 'has_snapshot':
                node_index[n]['heat'] = max(node_index[n].get('heat', 0), data.get('heat', 0))
                node_index[n]['year'] = data.get('year', node_index[n].get('year', 0))

json.dump(node_index, open(DATA_DIR / "graph_node_index.json", 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
print(f"  ✅ {len(node_index)} 个主题节点已索引")

print("\n🎉 全部完成！现在可以设置 RETRIEVAL_BACKEND=graph 启用图检索。")
