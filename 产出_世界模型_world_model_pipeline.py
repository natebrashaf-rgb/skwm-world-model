#!/usr/bin/env python3
# ​​​​​​⁠​​​﻿
"""🌍 世界模型施工 — 代码1~5（基于B1/B2文件）"""
import json, itertools, random, os
from collections import defaultdict
import numpy as np

OUTPUT = r"E:\大挑\产出\世界模型"
os.makedirs(OUTPUT, exist_ok=True)

# ====== 加载B1 ======
print("📂 加载 B1_文献主表.json ...")
with open(r"E:\大挑\产出\B1_文献主表.json", 'r', encoding='utf-8') as f:
    B1 = json.load(f)
print(f"   {len(B1)} 篇文献")

# ====== 按年分组 ======
print("\n📂 按年分组 ...")
by_year = defaultdict(list)
for p in B1:
    y = p.get('year')
    kw = p.get('keywords') or []
    if y and kw:
        try:
            by_year[int(y)].append([k.lower().strip() for k in kw if k])
        except:
            pass

years = sorted(by_year.keys())
print(f"   年份范围: {years[0]}~{years[-1]} ({len(years)}年)")

# ====== 代码1: 按年切片 ======
print("\n📂 代码1: 按年切片重建时序共现图 ...")
import networkx as nx

def snapshot(upto, window=5):
    """≤upto的近window年累积图 = S_t"""
    G = nx.Graph()
    for y in range(upto - window + 1, upto + 1):
        for kws in by_year.get(y, []):
            for u, v in itertools.combinations(set(kws), 2):
                if G.has_edge(u, v):
                    G[u][v]['w'] += 1
                else:
                    G.add_edge(u, v, w=1)
    return G

snapshots = {}
for y in years:
    if y >= years[0] + 4:  # Need at least 5 years for window
        snapshots[y] = snapshot(y, window=5)
        print(f"   S_{y}: {snapshots[y].number_of_nodes()} 节点, {snapshots[y].number_of_edges()} 边")

# Save snapshots
snap_data = {}
for y, G in snapshots.items():
    edges = [{'u': u, 'v': v, 'w': d['w']} for u, v, d in G.edges(data=True)]
    snap_data[str(y)] = {'nodes': list(G.nodes()), 'edges': edges, 'n_nodes': G.number_of_nodes(), 'n_edges': G.number_of_edges()}

with open(os.path.join(OUTPUT, "时序快照.json"), 'w', encoding='utf-8') as f:
    json.dump(snap_data, f, ensure_ascii=False, indent=2)
print(f"   ✅ 已保存: 时序快照.json")

# ====== 代码2: 状态向量 ======
print("\n📂 代码2: 状态向量 ...")

snap_years = sorted(snapshots.keys())
S = {}

for i, y in enumerate(snap_years):
    G = snapshots[y]
    deg = dict(G.degree(weight='w'))
    cen = nx.degree_centrality(G)
    prev_deg = dict(snapshots[snap_years[i-1]].degree(weight='w')) if i > 0 else {}
    
    for n in G.nodes():
        d = deg.get(n, 0)
        growth = d - prev_deg.get(n, 0)
        c = cen.get(n, 0)
        conn = G.degree(n)
        S[(str(y), n)] = [d, growth, round(c, 6), conn]

# Save state vectors
state_data = {}
for (y, n), vec in S.items():
    if y not in state_data:
        state_data[y] = {}
    state_data[y][n] = vec

with open(os.path.join(OUTPUT, "状态向量.json"), 'w', encoding='utf-8') as f:
    json.dump(state_data, f, ensure_ascii=False)

print(f"   状态向量: {len(S)} 条 (年×节点)")
print(f"   每向量: [热度, 增速, 中心度, 连接数]")

# Top nodes by 2024 growth
if snap_years:
    last_y = str(snap_years[-1])
    if last_y in state_data:
        top_growth = sorted(state_data[last_y].items(), key=lambda x: -x[1][1])[:15]
        print(f"\n   {last_y} 增速Top 15:")
        for name, vec in top_growth:
            print(f"     {name}: 热度={vec[0]}, 增速={vec[1]}")

# ====== 代码3: XGBoost链接预测 ======
print("\n📂 代码3: XGBoost链接预测 (动力学f) ...")

from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score

# Use early years as train, later years as test
if len(snap_years) >= 6:
    train_cut = snap_years[-3]  # Use up to 3rd-from-last as training
    test_year = snap_years[-1]
    
    G_train = snapshot(train_cut, window=5)
    G_test = snapshots[test_year]
    
    print(f"   训练集: ≤{train_cut} | 测试集: {test_year}")
    print(f"   训练图: {G_train.number_of_nodes()} 节点, {G_train.number_of_edges()} 边")
    
    # Build positive samples (new edges in test that exist in train's nodes)
    nodes = list(G_train.nodes())
    pos = [(u, v) for u, v in G_test.edges()
           if u in G_train and v in G_train and not G_train.has_edge(u, v)]
    
    # Negative samples
    neg = []
    while len(neg) < min(5 * len(pos), 20000):
        u, v = random.sample(nodes, 2)
        if not G_test.has_edge(u, v) and (u, v) not in neg and (v, u) not in neg:
            neg.append((u, v))
    
    print(f"   正样本: {len(pos)}, 负样本: {len(neg)}")
    
    # Feature engineering
    def feat(G, u, v):
        cn = list(nx.common_neighbors(G, u, v))
        aa = sum(1.0 / np.log(G.degree(w) + 1) for w in cn if G.degree(w) > 1)
        jc = list(nx.jaccard_coefficient(G, [(u, v)]))
        jc_val = next((p for _, _, p in jc), 0.0)
        return [len(cn), aa, G.degree(u, weight='w'), G.degree(v, weight='w'),
                G.degree(u), G.degree(v), jc_val]
    
    samples = [(u, v, 1) for u, v in pos] + [(u, v, 0) for u, v in neg]
    X = np.array([feat(G_train, u, v) for u, v, _ in samples])
    y = np.array([s for *_, s in samples])
    
    # Train
    f = XGBClassifier(n_estimators=200, max_depth=5, eval_metric='logloss')
    f.fit(X, y)
    
    auc = roc_auc_score(y, f.predict_proba(X)[:, 1])
    print(f"\n   ✅ 动力学f训练完成!")
    print(f"   AUC: {auc:.4f}")
    
    # Feature importance
    print(f"   特征重要性: {f.feature_importances_}")
    
    # Save model
    import pickle
    with open(os.path.join(OUTPUT, "动力学f_xgboost.pkl"), 'wb') as f_model:
        pickle.dump(f, f_model)
    print(f"   ✅ 模型已保存")
else:
    print("   年份不够，至少需要6年")

# ====== 代码4: 突现主题检测 ======
print("\n📂 代码4: 突现主题检测 ...")

freq = defaultdict(lambda: defaultdict(int))
for yr, docs in by_year.items():
    for kws in docs:
        for k in set(kws):
            freq[k][yr] += 1

def burst(k, y):
    hist = [freq[k].get(t, 0) for t in range(y - 5, y)]
    mu = np.mean(hist)
    sd = np.std(hist) + 1e-9
    return (freq[k].get(y, 0) - mu) / sd

if years:
    latest = max(years)
    emerging = sorted(freq.keys(), key=lambda k: burst(k, latest), reverse=True)[:30]
    print(f"   {latest} 突现前沿Top 20:")
    for k in emerging[:20]:
        b = burst(k, latest)
        current = freq[k].get(latest, 0)
        print(f"     {k}: burst={b:.1f}, 频次={current}")

# ====== 代码5: 反事实分析 ======
print("\n📂 代码5: 反事实分析 ...")

if len(snap_years) >= 3:
    G_hist = snapshot(snap_years[-2], window=5)
    
    # Find the most promising future link
    nodes_list = list(G_hist.nodes())
    candidates = []
    for i in range(min(50, len(nodes_list))):
        for j in range(i+1, min(50, len(nodes_list))):
            u, v = nodes_list[i], nodes_list[j]
            if not G_hist.has_edge(u, v):
                cn = list(nx.common_neighbors(G_hist, u, v))
                candidates.append((len(cn), u, v))
    
    candidates.sort(key=lambda x: -x[0])
    
    print(f"   反事实案例 — 移除政策/术语桥:")
    bridges_to_test = ["一带一路", "silk road", "belt", "china", "文化遗产", "tourism"]
    
    for bridge in bridges_to_test:
        if not G_hist.has_node(bridge):
            print(f"    ⚠️ '{bridge}' 不在图中，跳过")
            continue
        
        # Baseline prediction
        if candidates:
            _, u, v = candidates[0]
            base_feat = feat(G_hist, u, v)
            base_prob = f.predict_proba([base_feat])[0, 1] if 'f' in dir() else 0
            
            # Counterfactual: remove bridge
            G_cf = G_hist.copy()
            G_cf.remove_node(bridge)
            
            cf_feat = feat(G_cf, u, v)
            cf_prob = f.predict_proba([cf_feat])[0, 1] if 'f' in dir() else 0
            
            delta = base_prob - cf_prob
            print(f"   🔗 桥='{bridge}': 基线P={base_prob:.3f}, 移除后P={cf_prob:.3f}, Δ={delta:.3f}")
    
    print(f"\n   结论: Δ越大, 该桥越可能是前沿出现的'因'")

# ====== 保存结果 ======
results = {
    'n_papers': len(B1),
    'year_range': [years[0], years[-1]] if years else [],
    'n_snapshots': len(snapshots),
    'n_state_vectors': len(S),
    'top_emerging': emerging[:20] if 'emerging' in dir() else [],
    'counterfactual_results': [],
}

with open(os.path.join(OUTPUT, "世界模型结果.json"), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"  🌍 世界模型施工完成!")
print(f"  📁 输出: {OUTPUT}")
print(f"  ✅ 时序快照: {len(snapshots)} 年")
print(f"  ✅ 状态向量: {len(S)} 条")
if 'f' in dir():
    print(f"  ✅ 动力学f: AUC={auc:.4f}")
print(f"  ✅ 突现前沿: {len(emerging)} 个")
print(f"{'='*60}")
