#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于已验证阿语文献重新生成state_vectors和完成C/D任务
"""
import json
import re
import hashlib
import itertools
from pathlib import Path
from collections import defaultdict
import networkx as nx

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

def load_b1(path):
    """加载B1文献主表"""
    raw = open(path, encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def build_state_vectors(b1):
    """生成state_vectors"""
    by_year = defaultdict(list)
    for p in b1:
        y = p.get("year")
        kw = p.get("keywords") or []
        if y and kw:
            try:
                by_year[int(y)].append([k.lower().strip() for k in kw if k])
            except Exception:
                pass
    
    years = sorted(by_year.keys())
    
    def snapshot(upto, window=5):
        G = nx.Graph()
        for y in range(upto - window + 1, upto + 1):
            for kws in by_year.get(y, []):
                for u, v in itertools.combinations(set(kws), 2):
                    if G.has_edge(u, v):
                        G[u][v]["w"] += 1
                    else:
                        G.add_edge(u, v, w=1)
        return G
    
    snapshots = {y: snapshot(y) for y in years if y >= years[0] + 4}
    snap_years = sorted(snapshots.keys())
    
    S = {}
    for i, y in enumerate(snap_years):
        G = snapshots[y]
        deg = dict(G.degree(weight="w"))
        cen = nx.degree_centrality(G)
        prev_deg = dict(snapshots[snap_years[i - 1]].degree(weight="w")) if i > 0 else {}
        for n in G.nodes():
            d = deg.get(n, 0)
            S[(str(y), n)] = [d, d - prev_deg.get(n, 0), round(cen.get(n, 0), 6), G.degree(n)]
    
    state = {}
    for (y, n), vec in S.items():
        state.setdefault(y, {})[n] = vec
    
    return {k: dict(sorted(v.items())) for k, v in sorted(state.items(), key=lambda x: int(x[0]))}

def sha256_of(d):
    raw = json.dumps(d, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def main():
    print("="*70)
    print("基于已验证阿语文献重新生成state_vectors")
    print("="*70)
    
    # 1. 加载验证结果
    verification = json.load(open(OUTPUT_DIR / "arabic_papers_verification.json", encoding='utf-8'))
    
    # 2. 提取已验证的DOI
    verified_dois = set()
    for r in verification["details"]["verified"]:
        verified_dois.add(r["doi"])
    
    print(f"\n已验证DOI: {len(verified_dois)}个")
    
    # 3. 加载B1
    b1_full = load_b1(DATA_DIR / "B1_文献主表.json")
    print(f"原始B1: {len(b1_full)}条")
    
    # 4. 筛选阿语文献
    arabic = [p for p in b1_full if p.get("language") == "ar"]
    verified_arabic = [p for p in arabic if p.get("doi") in verified_dois]
    unverified_arabic = [p for p in arabic if p.get("doi") not in verified_dois]
    
    print(f"阿语文献: {len(arabic)}条")
    print(f"  已验证: {len(verified_arabic)}条")
    print(f"  未验证: {len(unverified_arabic)}条")
    
    # 5. 创建筛选后的B1
    b1_filtered = [p for p in b1_full if p not in unverified_arabic]
    print(f"\n筛选后B1: {len(b1_filtered)}条")
    
    # 6. 生成C0（排除阿语）和C1（包含已验证阿语）
    b1_c0 = [p for p in b1_filtered if (p.get("language") or "") != "ar"]
    b1_c1 = b1_filtered
    
    print(f"C0(排除阿语): {len(b1_c0)}条")
    print(f"C1(包含已验证阿语): {len(b1_c1)}条")
    
    # 7. 生成state_vectors
    print("\n生成state_vectors...")
    sv_c0 = build_state_vectors(b1_c0)
    sv_c1 = build_state_vectors(b1_c1)
    
    # 8. 保存
    output_c0 = OUTPUT_DIR / "state_vectors_C0_verified.json"
    output_c1 = OUTPUT_DIR / "state_vectors_C1_verified.json"
    
    with open(output_c0, "w", encoding='utf-8') as f:
        json.dump(sv_c0, f, ensure_ascii=False)
    
    with open(output_c1, "w", encoding='utf-8') as f:
        json.dump(sv_c1, f, ensure_ascii=False)
    
    sha_c0 = sha256_of(sv_c0)
    sha_c1 = sha256_of(sv_c1)
    
    print(f"C0: {output_c0} (SHA: {sha_c0[:16]})")
    print(f"C1: {output_c1} (SHA: {sha_c1[:16]})")
    
    # 9. 统计
    def stats(sv):
        years = sorted(int(k) for k in sv)
        total = sum(len(v) for v in sv.values())
        heat_sum = sum(vec[0] for v in sv.values() for vec in v.values())
        return years[0], years[-1], len(years), total, heat_sum
    
    s0, s1 = stats(sv_c0), stats(sv_c1)
    
    print(f"\nC0统计: {s0[0]}-{s0[1]}年, {s0[2]}年, {s0[3]}主题, 热度{s0[4]:.0f}")
    print(f"C1统计: {s1[0]}-{s1[1]}年, {s1[2]}年, {s1[3]}主题, 热度{s1[4]:.0f}")
    
    # 10. 保存筛选后的B1
    b1_filtered_path = DATA_DIR / "B1_文献主表_已验证.json"
    with open(b1_filtered_path, "w", encoding='utf-8') as f:
        json.dump(b1_filtered, f, ensure_ascii=False, indent=2)
    
    print(f"\n筛选后B1已保存: {b1_filtered_path}")
    
    # 11. 生成报告
    report = {
        "meta": {
            "timestamp": "2026-08-27",
            "description": "基于已验证阿语文献的state_vectors",
        },
        "data_summary": {
            "original_b1": len(b1_full),
            "arabic_total": len(arabic),
            "arabic_verified": len(verified_arabic),
            "arabic_unverified": len(unverified_arabic),
            "filtered_b1": len(b1_filtered),
        },
        "c0_baseline": {
            "count": len(b1_c0),
            "sha256": sha_c0,
            "years": f"{s0[0]}-{s0[1]}",
            "topics": s0[3],
        },
        "c1_with_verified_arabic": {
            "count": len(b1_c1),
            "sha256": sha_c1,
            "years": f"{s1[0]}-{s1[1]}",
            "topics": s1[3],
        },
        "files": {
            "b1_filtered": str(b1_filtered_path),
            "sv_c0": str(output_c0),
            "sv_c1": str(output_c1),
        }
    }
    
    report_path = OUTPUT_DIR / "verified_arabic_state_vectors_report.json"
    with open(report_path, "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存: {report_path}")
    
    return report

if __name__ == "__main__":
    main()
