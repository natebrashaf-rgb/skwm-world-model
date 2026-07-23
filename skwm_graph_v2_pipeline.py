#!/usr/bin/env python3
"""
SKWM 知识图谱重构管线 v2.0
===========================
1. 实体消歧与归一（去重）
2. 社区检测（Louvain）
3. 核心子图提取
4. 最短路径索引
5. GraphRAG 社区摘要
"""
import json, re, os, sys, hashlib, math
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output" / "graph_redesign"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE))

# ── 加载器 ──
def load_fix(path):
    raw = open(path, encoding='utf-8').read()
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    return json.loads('[' + raw[idx:])


# ══════════════════════════════════════════════════════
# 1. 实体消歧与归一
# ══════════════════════════════════════════════════════

def disambiguate(b1_data, core_terms, state_vector_entities):
    """实体消歧：合并同名作者、规范机构名、合并中英同义主题"""
    print("\n" + "="*50)
    print("  实体消歧与归一")
    print("="*50)
    
    # 1a. 作者消歧
    authors_raw = Counter()
    for doc in b1_data:
        for a in re.split(r'[,;、]', str(doc.get('authors', ''))):
            a = a.strip()
            if len(a) > 4:
                authors_raw[a] += 1
    
    # 归一化作者名（去掉中间名缩写、统一大小写）
    author_map = {}  # normalized -> canonical
    for name, freq in authors_raw.most_common():
        norm = re.sub(r'\b[A-Z]\.?\s*', '', name).strip().lower()
        norm = re.sub(r'\s+', ' ', norm)
        if norm not in author_map:
            author_map[norm] = {'canonical': name, 'variants': [name], 'freq': freq, 'papers': 0}
        else:
            author_map[norm]['variants'].append(name)
            author_map[norm]['freq'] += freq
    
    # 统计去重效果
    before_authors = len(authors_raw)
    after_authors = len(author_map)
    dup_rate_authors = (1 - after_authors / before_authors) * 100 if before_authors else 0
    print(f"  作者: {before_authors} → {after_authors} ({dup_rate_authors:.1f}% 去重)")
    
    # 1b. 机构消歧
    orgs_raw = set()
    for doc in b1_data:
        for org_field in ['journal', 'source', 'publisher', 'affiliation']:
            org = str(doc.get(org_field, '')).strip()
            if org and len(org) > 5:
                orgs_raw.add(org)
    
    # 归一化机构名
    org_map = {}
    for org in sorted(orgs_raw):
        norm = re.sub(r'[（(].*?[）)]', '', org).strip()
        norm = re.sub(r'(University|Institute|College).*', r'\1', norm, flags=re.I).strip()
        norm = norm.lower()[:30]
        key = hashlib.md5(norm.encode()).hexdigest()[:8]
        if key not in org_map:
            org_map[key] = {'canonical': org, 'variants': [org], 'count': 0}
        else:
            org_map[key]['variants'].append(org)
    
    before_orgs = len(orgs_raw)
    after_orgs = len(org_map)
    dup_rate_orgs = (1 - after_orgs / before_orgs) * 100 if before_orgs else 0
    print(f"  机构: {before_orgs} → {after_orgs} ({dup_rate_orgs:.1f}% 去重)")
    
    # 1c. 主题消歧（合并中英同义主题）
    en_terms = set()
    zh_terms = set()
    ar_terms = set()
    term_map = {}  # en lower -> canonical
    
    for t in core_terms:
        en = t.get('en', '').strip()
        zh = t.get('cn', '').strip()
        ar = t.get('ar', '').strip()
        if en:
            en_lower = en.lower()
            if en_lower not in term_map:
                term_map[en_lower] = {'en': en, 'zh': zh, 'ar': ar, 'variants': []}
            else:
                term_map[en_lower]['variants'].append(en)
    
    # 状态向量中的实体去重
    sv_lower = set(e.lower() for e in state_vector_entities)
    overlap = len(sv_lower & set(term_map.keys()))
    
    print(f"  主题(核心术语): {len(core_terms)}")
    print(f"  主题(状态向量): {len(state_vector_entities)}")
    print(f"  主题去重后: {len(term_map)}")
    print(f"  核心术语覆盖率: {overlap}/{len(sv_lower)} ({overlap/len(sv_lower)*100:.1f}%)" if sv_lower else "  状态向量为空")
    
    # 1d. 总体验收
    total_before = before_authors + before_orgs + len(core_terms)
    total_after = after_authors + after_orgs + len(term_map)
    total_dup_rate = (1 - total_after / total_before) * 100 if total_before else 0
    print(f"\n  📊 总体验收: {total_before} → {total_after} ({total_dup_rate:.1f}% 去重)")
    print(f"  重复实体率: {dup_rate_authors:.1f}% (作者) + {dup_rate_orgs:.1f}% (机构)")
    print(f"  验收标准: 重复实体率 < 3%")
    status = '✅ 通过' if dup_rate_authors < 3 and dup_rate_orgs < 3 else '⚠️ 部分通过'
    print(f"  结果: {status}")
    
    return {
        'authors': {'before': before_authors, 'after': after_authors, 'rate': dup_rate_authors},
        'orgs': {'before': before_orgs, 'after': after_orgs, 'rate': dup_rate_orgs},
        'terms': {'before': len(core_terms), 'after': len(term_map)},
        'author_map': author_map,
        'org_map': org_map,
        'term_map': term_map,
    }


# ══════════════════════════════════════════════════════
# 2. 社区检测 + 核心子图
# ══════════════════════════════════════════════════════

def louvain_community_detection(nodes, edges):
    """
    简化版 Louvain 社区检测（无 NetworkX 环境时用贪心邻居聚合）
    """
    # 每个节点初始自成一社区
    community = {n['id']: i for i, n in enumerate(nodes)}
    
    # 构建邻接表
    adj = defaultdict(set)
    edge_weights = {}
    for e in edges:
        s, t = e['source'], e['target']
        adj[s].add(t)
        adj[t].add(s)
        key = tuple(sorted([s, t]))
        edge_weights[key] = edge_weights.get(key, 0) + e.get('weight', 1)
    
    # 贪心迭代：合并共享边最多的邻居
    changed = True
    while changed:
        changed = False
        for n in list(community.keys()):
            my_comm = community[n]
            # 统计邻居的社区分布
            neighbor_comms = Counter()
            for nb in adj.get(n, set()):
                if nb in community:
                    neighbor_comms[community[nb]] += edge_weights.get(tuple(sorted([n, nb])), 1)
            if neighbor_comms:
                # 加入最多邻居的社区
                best_comm = neighbor_comms.most_common(1)[0][0]
                if best_comm != my_comm:
                    community[n] = best_comm
                    changed = True
    
    # 重新编号社区
    comm_ids = {}
    for k in community:
        v = community[k]
        if v not in comm_ids:
            comm_ids[v] = len(comm_ids)
    community = {k: comm_ids[v] for k, v in community.items()}
    
    # 统计
    comm_sizes = Counter(community.values())
    print(f"  Louvain 社区: {len(comm_sizes)} 个")
    for cid, size in sorted(comm_sizes.items(), key=lambda x: -x[1])[:10]:
        print(f"    社区 {cid}: {size} 节点")
    
    return community


def extract_core_subgraph(nodes, edges, community, max_nodes=50):
    """提取核心子图（PageRank 代理 + 社区代表）"""
    if len(nodes) <= max_nodes:
        return nodes, edges
    
    # 用度数近似 PageRank
    degree = Counter()
    for e in edges:
        degree[e['source']] += 1
        degree[e['target']] += 1
    
    # 取热度 + 度数最高的节点
    scored = []
    for n in nodes:
        heat = n.get('heat', n.get('degree', 0))
        deg = degree.get(n['id'], 0)
        score = heat * 0.7 + deg * 0.3
        scored.append((score, n))
    scored.sort(key=lambda x: -x[0])
    
    # 确保每个社区至少有代表（如果社区有节点）
    selected_ids = set()
    comm_members = defaultdict(list)
    for n in nodes:
        comm_members[community.get(n['id'], 0)].append(n)
    
    # 每社区至少 2 个代表
    for cid, members in sorted(comm_members.items(), key=lambda x: -len(x[1])):
        members.sort(key=lambda x: -(degree.get(x['id'], 0)))
        for m in members[:min(2, max(1, max_nodes // len(comm_members)))]:
            selected_ids.add(m['id'])
    
    # 补足到 max_nodes
    for _, n in scored:
        if len(selected_ids) >= max_nodes:
            break
        selected_ids.add(n['id'])
    
    core_nodes = [n for n in nodes if n['id'] in selected_ids]
    core_edges = [e for e in edges if e['source'] in selected_ids and e['target'] in selected_ids]
    
    print(f"  核心子图: {len(nodes)} → {len(core_nodes)} 节点, {len(edges)} → {len(core_edges)} 边")
    return core_nodes, core_edges


# ══════════════════════════════════════════════════════
# 3. 最短路径索引（BFS）
# ══════════════════════════════════════════════════════

def build_shortest_path_index(edges):
    """构建 BFS 最短路径索引"""
    adj = defaultdict(set)
    for e in edges:
        adj[e['source']].add(e['target'])
        adj[e['target']].add(e['source'])
    
    def shortest_path(start, end, max_depth=6):
        """BFS 找最短路径"""
        if start == end:
            return [start]
        queue = [(start, [start])]
        visited = {start}
        while queue:
            node, path = queue.pop(0)
            if len(path) > max_depth:
                continue
            for nb in adj.get(node, set()):
                if nb == end:
                    return path + [nb]
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, path + [nb]))
        return None
    
    return shortest_path


# ══════════════════════════════════════════════════════
# 4. GraphRAG 社区摘要生成
# ══════════════════════════════════════════════════════

def generate_community_summaries(nodes, community):
    """为每个社区生成摘要"""
    comm_members = defaultdict(list)
    for n in nodes:
        comm_members[community.get(n['id'], 0)].append(n)
    
    summaries = {}
    for cid, members in comm_members.items():
        types = Counter(m['type'] for m in members if 'type' in m)
        top_types = types.most_common(5)
        names = [m.get('label_en', m.get('label', m['id'])) for m in members[:5]]
        summaries[cid] = {
            'id': cid,
            'size': len(members),
            'top_types': dict(top_types),
            'representatives': names[:5],
            'summary': f"社区{cid}: {', '.join(n[:20] for n in names[:3])} 等 {len(members)} 个实体"
        }
    return summaries


# ══════════════════════════════════════════════════════
# 5. 主流程
# ══════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  SKWM 知识图谱重构管线 v2.0")
    print("  本体 -> 消歧 -> 社区 -> 核心子图 -> GraphRAG")
    print("=" * 60)
    
    # 加载数据
    print("\n📦 加载数据...")
    b1 = load_fix(DATA_DIR / "B1_文献主表.json")
    terms = load_fix(DATA_DIR / "datiao" / "知识图谱_核心术语.json")
    sv = json.loads(open(DATA_DIR / "state_vectors.json", encoding='utf-8').read())
    sv_entities = list(set(e for yd in sv.values() if isinstance(yd, dict) for e in yd.keys()))
    
    print(f"  B1文献: {len(b1)}, 核心术语: {len(terms)}, 状态向量实体: {len(sv_entities)}")
    
    # 1. 实体消歧
    dedup = disambiguate(b1, terms, sv_entities)
    
    # 2. 构建规范化的图数据
    # 从核心术语生成节点和边
    nodes = []
    edges = []
    for i, t in enumerate(terms[:500]):  # 取前500个高频术语
        en = t.get('en', '')
        if not en:
            continue
        node = {
            'id': f't{i}',
            'type': 'Topic',
            'label_zh': t.get('cn', ''),
            'label_en': en,
            'label_ar': t.get('ar', ''),
            'domain': t.get('domain', '文旅'),
            'heat': t.get('freq', 50),
            'degree': 0
        }
        nodes.append(node)
    
    # 生成共现边：同领域术语之间建边
    domain_groups = defaultdict(list)
    for n in nodes:
        domain_groups[n['domain']].append(n)
    for domain, group in domain_groups.items():
        for i in range(len(group)):
            for j in range(i+1, len(group)):
                edges.append({
                    'source': group[i]['id'],
                    'target': group[j]['id'],
                    'relation': 'co_occurs',
                    'label': '共现',
                    'weight': 1
                })
        # 更新度数
        for n in group:
            n['degree'] = len(group) - 1
    
    print(f"\n  🕸️ 规范图: {len(nodes)} 节点, {len(edges)} 边")
    
    # 3. Louvain 社区检测
    community = {}
    if nodes:
        community = louvain_community_detection(nodes, edges)
        # 写入节点社区
        for n in nodes:
            n['community_id'] = community.get(n['id'], 0)
    
    # 4. 提取核心子图
    core_nodes, core_edges = extract_core_subgraph(nodes, edges, community, max_nodes=50)
    
    # 5. 社区摘要
    summaries = generate_community_summaries(core_nodes, community)
    
    # 6. 最短路径函数
    shortest_path_fn = build_shortest_path_index(core_edges)
    
    # ── 输出 ──
    # 去重报告
    report = f"""# SKWM 知识图谱去重报告

## 数据源
- B1文献主表: {len(b1)} 条
- 核心术语: {len(terms)} 条
- 状态向量实体: {len(sv_entities)} 个

## 消歧结果

| 类型 | 去重前 | 去重后 | 去重率 |
|------|:------:|:------:|:------:|
| 作者 | {dedup['authors']['before']} | {dedup['authors']['after']} | {dedup['authors']['rate']:.1f}% |
| 机构 | {dedup['orgs']['before']} | {dedup['orgs']['after']} | {dedup['orgs']['rate']:.1f}% |
| 主题 | {dedup['terms']['before']} | {dedup['terms']['after']} | - |

## 验收
- 重复实体率 < 3%: {'✅' if dedup['authors']['rate'] < 3 and dedup['orgs']['rate'] < 3 else '⚠️'}
- 规范图: {len(nodes)} 节点, {len(edges)} 边
- 核心子图: {len(core_nodes)} 节点, {len(core_edges)} 边
- Louvain 社区: {len(community and set(community.values()) or set())} 个
"""
    with open(OUT_DIR / "dedup_report.md", 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n  📄 去重报告: {OUT_DIR / 'dedup_report.md'}")
    
    # 规范图数据
    graph_data = {
        'nodes': core_nodes,
        'edges': core_edges,
        'communities': {str(k): v for k, v in summaries.items()},
        'stats': {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'core_nodes': len(core_nodes),
            'core_edges': len(core_edges),
            'communities': len(summaries)
        }
    }
    with open(OUT_DIR / "graph_v2.json", 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    print(f"  📄 规范图数据: {OUT_DIR / 'graph_v2.json'}")
    
    print(f"\n  {'='*50}")
    print(f"  🎉 重构完成")
    print(f"  {'='*50}")


if __name__ == '__main__':
    main()
