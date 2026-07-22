#!/usr/bin/env python3
# ​​​​​​⁠​​​﻿
"""🧠 中阿文旅知识图谱 2.1 — 实体+关系 10000+"""
import os, json, re, math, itertools
from collections import Counter, defaultdict
import networkx as nx

KG = r"E:\大挑\知识图谱"

print("="*60)
print("  🧠 中阿文旅知识图谱 2.1 (实体10000+ 关系15000+)")
print("="*60)

# ====== Load data ======
all_papers = []
if os.path.exists(r"E:\大挑\产出\B1_文献主表.json"):
    with open(r"E:\大挑\产出\B1_文献主表.json", 'r', encoding='utf-8') as f:
        all_papers.extend(json.load(f))

arxiv_meta = r"E:\大挑\📚_文献资料库\07_中阿文旅与文化遗产\_阿语大采集元数据.json"
if os.path.exists(arxiv_meta):
    with open(arxiv_meta, 'r', encoding='utf-8') as f:
        for p in json.load(f):
            all_papers.append({
                'title': p['title'], 'year': int(p.get('year',0) or 0),
                'authors': p.get('authors',''), 'keywords': [], 'doi': '', 'source': 'arXiv'
            })

# Dedup
seen = set()
unique = []
for p in all_papers:
    t = p.get('title','').strip().lower()[:60]
    if t and t not in seen:
        seen.add(t)
        unique.append(p)
all_papers = unique
print(f"  📚 {len(all_papers)} 篇文献")

# ====== Load terms ======
with open(f"{KG}/术语对齐表_v3.json", 'r', encoding='utf-8') as f:
    terms = json.load(f)
print(f"  📖 {len(terms)} 条术语")

# ====== Build entity graph ======
G = nx.Graph()
eid = 0
paper_map = {}  # title -> entity_id
author_terms = Counter()
paper_titles_lower = {}

# Country/region list for matching
COUNTRIES = ['china','saudi arabia','uae','united arab emirates','qatar','oman','bahrain',
             'kuwait','egypt','jordan','morocco','tunisia','algeria','sudan','iraq',
             'syria','lebanon','palestine','yemen','libya','mauritania','turkey',
             'iran','spain','france','italy','germany','uk','united kingdom','usa',
             'united states','japan','korea','india','russia','australia','brazil',
             '中国','沙特','阿联酋','卡塔尔','阿曼','埃及','约旦','摩洛哥','突尼斯',
             '阿尔及利亚','伊拉克','叙利亚','黎巴嫩','土耳其','伊朗','美国','英国',
             '法国','德国','意大利','西班牙','日本','韩国','印度']

# ====== Step 1: Create Paper entities + Author entities ======
print("\n📂 创建Paper实体 + Author实体 + Country实体...")

for i, p in enumerate(all_papers[:10000]):
    eid += 1
    title = p.get('title', '')[:80]
    paper_map[i] = eid
    paper_titles_lower[eid] = p.get('title', '').lower()
    
    G.add_node(eid, type='Paper', label=title,
               year=str(p.get('year','')),
               authors=p.get('authors','')[:80],
               source=p.get('source','B1'))
    
    # Extract Author entities from author string
    authors_str = p.get('authors', '')
    if authors_str:
        for author in authors_str.split(',')[:3]:  # First 3 authors
            author = author.strip()
            if author and len(author) > 3:
                author_terms[author] += 1

# Create Author entities (top 3000 authors)
author_eid = {}
for author, freq in author_terms.most_common(3000):
    if freq < 2: break
    eid += 1
    author_eid[author] = eid
    G.add_node(eid, type='Author', label=author[:50], freq=freq)

# Create Country entities
country_eid = {}
for country in COUNTRIES:
    eid += 1
    country_eid[country] = eid
    G.add_node(eid, type='Country', label=country)

print(f"  🟢 实体总数: {eid} (目标10000+)")

# ====== Step 2: Build Topic entities from terms ======
topic_eid = {}
for i, t in enumerate(terms[:3000]):
    if len(t['en']) > 2:
        eid += 1
        topic_eid[t['en']] = eid
        G.add_node(eid, type='Topic', label=t['en'], domain=t.get('domain',''))

print(f"  🟢 含Topic后: {eid}")

# ====== Step 3: Build RELATIONSHIPS ======
print("\n📂 构建关系 (目标15000+)...")
rel_count = 0

# 3a. Paper → Author (authored_by)
for i, p in enumerate(all_papers[:10000]):
    if i not in paper_map: continue
    pid = paper_map[i]
    authors_str = p.get('authors', '')
    if authors_str:
        for author in authors_str.split(',')[:3]:
            author = author.strip()
            if author in author_eid:
                if not G.has_edge(pid, author_eid[author]):
                    G.add_edge(pid, author_eid[author], type='authored_by')
                    rel_count += 1

print(f"  🔗 作者关系: {rel_count}")

# 3b. Paper → Country (about, from title)
for pid, title_lower in paper_titles_lower.items():
    for country, ceid in country_eid.items():
        if country in title_lower:
            if not G.has_edge(pid, ceid):
                G.add_edge(pid, ceid, type='about_country')
                rel_count += 1

print(f"  🔗 国家关系: {rel_count}")

# 3c. Paper → Topic (studies)
for pid, title_lower in paper_titles_lower.items():
    matched = False
    for en, teid in topic_eid.items():
        if len(en) > 3 and en.lower() in title_lower:
            if not G.has_edge(pid, teid):
                G.add_edge(pid, teid, type='studies', weight=1)
                rel_count += 1
                matched = True
                if rel_count >= 25000: break
        if rel_count >= 25000: break
    if rel_count >= 25000: break

print(f"  🔗 主题关系: {rel_count}")

# 3d. Author → Author (co_authored) - co-authorship
for i, p in enumerate(all_papers[:8000]):
    authors_str = p.get('authors', '')
    if not authors_str: continue
    authors = [a.strip() for a in authors_str.split(',') if a.strip() in author_eid]
    for a1, a2 in itertools.combinations(authors[:4], 2):  # Within same paper
        e1, e2 = author_eid[a1], author_eid[a2]
        if G.has_edge(e1, e2):
            G[e1][e2]['weight'] = G[e1][e2].get('weight', 1) + 1
        else:
            G.add_edge(e1, e2, type='co_authored', weight=1)
            rel_count += 1

print(f"  🔗 合作关系: {rel_count}")

# 3e. Topic → Topic co-occurrence (from paper titles)
topic_cooc = defaultdict(int)
for i, p in enumerate(all_papers[:5000]):
    title_lower = p.get('title', '').lower()
    topics_in_paper = [en for en in topic_eid if len(en) > 3 and en.lower() in title_lower]
    for en1, en2 in itertools.combinations(topics_in_paper[:5], 2):
        pair = tuple(sorted([en1, en2]))
        topic_cooc[pair] += 1

for (en1, en2), freq in sorted(topic_cooc.items(), key=lambda x:-x[1])[:3000]:
    if en1 in topic_eid and en2 in topic_eid:
        e1, e2 = topic_eid[en1], topic_eid[en2]
        if not G.has_edge(e1, e2):
            G.add_edge(e1, e2, type='co_occurrence', weight=freq)
            rel_count += 1

print(f"  🔗 共现关系: {rel_count}")

# ====== Save ======
print("\n📂 保存结果...")

# Clean None values
for n, data in G.nodes(data=True):
    for k, v in list(data.items()):
        if v is None: data[k] = ''
for u, v, data in G.edges(data=True):
    for k, v in list(data.items()):
        if v is None: data[k] = ''

nx.write_gexf(G, os.path.join(KG, "知识图谱2.1.gexf"))
nx.write_graphml(G, os.path.join(KG, "知识图谱2.1.graphml"))

# Entity type counts
type_counts = Counter()
for n, data in G.nodes(data=True):
    type_counts[data.get('type', 'Unknown')] += 1

# Relationship type counts
rel_type_counts = Counter()
for u, v, data in G.edges(data=True):
    rel_type_counts[data.get('type', 'Unknown')] += 1

print(f"\n{'='*60}")
print(f"  ✅ 中阿文旅知识图谱 2.1 构建完成!")
print(f"  🟢 实体节点: {G.number_of_nodes()}")
print(f"  🔗 关系边: {G.number_of_edges()}")
print()
print(f"  实体类型分布:")
for t, c in sorted(type_counts.items(), key=lambda x:-x[1]):
    print(f"    {t}: {c}")
print()
print(f"  关系类型分布:")
for t, c in sorted(rel_type_counts.items(), key=lambda x:-x[1]):
    print(f"    {t}: {c}")
print(f"{'='*60}")
