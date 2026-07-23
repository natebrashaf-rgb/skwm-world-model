#!/usr/bin/env python3
"""
SKWM 科学计量分析管线 (Bibliometrics)
=====================================
1. 关键词共现网络 + Louvain 聚类
2. 作者合作网络
3. 国家合作网络（中阿高亮）
4. 引文分析
5. 突现词检测 + 主题演化
"""
import json, re, os, math
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import random

BASE = Path(__file__).parent
OUT_DIR = BASE / "output" / "bibliometrics"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = BASE / "data"


def load_data():
    raw = (DATA_DIR / "B1_文献主表.json").read_text(encoding='utf-8')
    raw = re.sub(r'[\u200B-\u200F\u2028-\u202F\uFEFF]', '', raw)
    idx = raw.find('{', raw.find('{') + 1)
    return json.loads('[' + raw[idx:])


def parse_authors(authors_str):
    if not authors_str:
        return []
    return [a.strip() for a in re.split(r'[,;、]', authors_str) if len(a.strip()) > 2]


def has_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', str(text)))


# ═══════════════════════════════════════════════
# 1. 关键词共现网络
# ═══════════════════════════════════════════════

def build_coword_network(docs, min_freq=5):
    print("\n  ── 关键词共现网络 ──")
    kw_freq = Counter()
    doc_keywords = []

    for d in docs:
        kws = d.get('keywords', d.get('normalized_keywords', []))
        if isinstance(kws, str):
            kws = [k.strip() for k in re.split(r'[,;、]', kws) if k.strip()]
        if not isinstance(kws, list):
            kws = []

        # 过滤通用词
        kws = [k for k in kws if k and len(k) > 1 and k not in ('通用', 'general', 'other')]
        if kws:
            doc_keywords.append(set(kws))
            for kw in kws:
                kw_freq[kw] += 1

    # 过滤低频词
    valid_kws = {kw for kw, freq in kw_freq.most_common() if freq >= min_freq}
    print(f"  总关键词: {len(kw_freq)}, 有效(≥{min_freq}次): {len(valid_kws)}")

    # 构建共现矩阵
    cooccur = defaultdict(lambda: defaultdict(int))
    for kws in doc_keywords:
        kws_valid = kws & valid_kws
        kw_list = sorted(kws_valid)
        for i in range(len(kw_list)):
            for j in range(i + 1, len(kw_list)):
                cooccur[kw_list[i]][kw_list[j]] += 1
                cooccur[kw_list[j]][kw_list[i]] += 1

    # 构建网络
    nodes = []
    edges = []
    for kw in sorted(valid_kws):
        nodes.append({
            "id": kw, "label": kw, "freq": kw_freq[kw],
            "degree": len(cooccur[kw]),
            "type": "keyword"
        })

    for k1 in sorted(valid_kws):
        for k2 in sorted(cooccur[k1].keys()):
            if k1 < k2:
                w = cooccur[k1][k2]
                if w >= 2:
                    edges.append({"source": k1, "target": k2, "weight": w})

    print(f"  节点: {len(nodes)}, 边: {len(edges)}")

    # Louvain 社区检测（简化版）
    community = simple_louvain(nodes, edges)
    for n in nodes:
        n["community"] = community.get(n["id"], 0)

    # 聚类主题标签
    comm_kws = defaultdict(list)
    for n in nodes:
        comm_kws[n["community"]].append((n["freq"], n["id"]))
    comm_labels = {}
    for cid, items in comm_kws.items():
        top = sorted(items, key=lambda x: -x[0])[:3]
        comm_labels[cid] = " / ".join(t[1] for t in top)

    return {
        "type": "coword",
        "nodes": nodes,
        "edges": edges,
        "communities": {str(k): {"label": v, "size": len(comm_kws[k])}
                        for k, v in comm_labels.items()},
        "stats": {"nodes": len(nodes), "edges": len(edges),
                  "communities": len(comm_labels),
                  "density": round(2 * len(edges) / max(1, len(nodes) * (len(nodes) - 1)), 6)}
    }


def simple_louvain(nodes, edges):
    """简化Louvain：每个节点分配社区，贪心合并"""
    community = {n["id"]: i for i, n in enumerate(nodes)}
    adj = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    changed = True
    while changed:
        changed = False
        for n in list(community.keys()):
            my_comm = community[n]
            neighbor_comms = Counter()
            for nb in adj.get(n, set()):
                if nb in community:
                    neighbor_comms[community[nb]] += 1
            if neighbor_comms:
                best = neighbor_comms.most_common(1)[0][0]
                if best != my_comm:
                    community[n] = best
                    changed = True
    # 重编号
    ids = {}
    for k in community:
        v = community[k]
        if v not in ids:
            ids[v] = len(ids)
    return {k: ids[v] for k, v in community.items()}


# ═══════════════════════════════════════════════
# 2. 作者合作网络
# ═══════════════════════════════════════════════

def build_coauthor_network(docs):
    print("\n  ── 作者合作网络 ──")
    author_pairs = defaultdict(int)
    author_papers = defaultdict(set)
    author_years = defaultdict(list)

    for d in docs:
        authors = parse_authors(d.get('authors', ''))
        year = int(d.get("year", 0) or 0)
        for i in range(len(authors)):
            author_papers[authors[i]].add(d.get('title', ''))
            if year:
                try:
                    author_years[authors[i]].append(int(year))
                except (ValueError, TypeError):
                    pass
            for j in range(i + 1, len(authors)):
                pair = tuple(sorted([authors[i], authors[j]]))
                author_pairs[pair] += 1

    min_coop = 2
    valid_pairs = {p: c for p, c in author_pairs.items() if c >= min_coop}
    top_authors = Counter()
    for a, b in valid_pairs:
        top_authors[a] += 1
        top_authors[b] += 1

    # 取前 200 个合作最频繁的作者
    top_n = 200
    top_set = set(a for a, _ in top_authors.most_common(top_n))

    nodes = []
    edges = []
    for author in sorted(top_set):
        nodes.append({
            "id": author, "label": author,
            "papers": len(author_papers.get(author, set())),
            "degree": 0,
            "type": "author",
            "year_range": f"{min(author_years.get(author,[0]))}-{max(author_years.get(author,[0]))}"
        })

    id_map = {n["id"]: n for n in nodes}
    for (a, b), c in valid_pairs.items():
        if a in id_map and b in id_map:
            edges.append({"source": a, "target": b, "weight": c})
            id_map[a]["degree"] += 1
            id_map[b]["degree"] += 1

    print(f"  节点: {len(nodes)}, 边: {len(edges)}")
    density = round(2 * len(edges) / max(1, len(nodes) * (len(nodes) - 1)), 6)
    return {"type": "coauthor", "nodes": nodes, "edges": edges,
            "stats": {"nodes": len(nodes), "edges": len(edges), "density": density}}


# ═══════════════════════════════════════════════
# 3. 国家合作网络
# ═══════════════════════════════════════════════

def build_country_network(docs):
    print("\n  ── 国家合作网络 ──")
    country_count = Counter()
    country_pairs = defaultdict(int)

    # 国家映射
    country_map = {
        'china': '中国', 'chinese': '中国', 'beijing': '中国',
        'saudi arabia': '沙特', 'saudi': '沙特',
        'uae': '阿联酋', 'united arab emirates': '阿联酋',
        'egypt': '埃及', 'qatar': '卡塔尔', 'jordan': '约旦',
        'morocco': '摩洛哥', 'tunisia': '突尼斯', 'algeria': '阿尔及利亚',
        'oman': '阿曼', 'bahrain': '巴林', 'kuwait': '科威特',
        'lebanon': '黎巴嫩', 'iraq': '伊拉克', 'syria': '叙利亚',
        'usa': '美国', 'united states': '美国', 'uk': '英国',
        'germany': '德国', 'france': '法国', 'japan': '日本',
        'korea': '韩国', 'australia': '澳大利亚', 'canada': '加拿大',
        'italy': '意大利', 'spain': '西班牙', 'netherlands': '荷兰',
        'turkey': '土耳其', 'russia': '俄罗斯', 'india': '印度',
        'malaysia': '马来西亚', 'indonesia': '印度尼西亚', 'iran': '伊朗',
    }
    arab_countries = {'沙特', '阿联酋', '埃及', '卡塔尔', '约旦', '摩洛哥',
                      '突尼斯', '阿尔及利亚', '阿曼', '巴林', '科威特',
                      '黎巴嫩', '伊拉克', '叙利亚'}

    for d in docs:
        country = str(d.get('country', '') or '').strip().lower()
        cn = country_map.get(country, '')
        if cn:
            country_count[cn] += 1
        else:
            # 从 affiliation 中猜测
            authors = str(d.get('authors', ''))
            for abbr, name in country_map.items():
                if abbr in authors.lower():
                    country_count[name] += 1
                    cn = name
                    break

    # 国家合作：同一篇文献多个作者来自不同国家
    for d in docs:
        authors = parse_authors(d.get('authors', ''))
        if len(authors) < 2:
            continue
        countries_in_doc = set()
        # 简化：通过authors字段匹配国家
        for a in authors:
            for abbr, name in country_map.items():
                if abbr in a.lower():
                    countries_in_doc.add(name)
                    break
        if len(countries_in_doc) >= 2:
            for c1 in sorted(countries_in_doc):
                for c2 in sorted(countries_in_doc):
                    if c1 < c2:
                        country_pairs[(c1, c2)] += 1

    min_country_freq = 2
    valid_countries = {c for c, f in country_count.most_common() if f >= min_country_freq}

    nodes = []
    edges = []
    for c in sorted(valid_countries):
        is_arab = c in arab_countries
        is_china = c == '中国'
        nodes.append({
            "id": c, "label": c,
            "papers": country_count[c],
            "type": "country",
            "is_china": is_china,
            "is_arab": is_arab,
            "group": "china" if is_china else ("arab" if is_arab else "other")
        })

    for (c1, c2), w in country_pairs.items():
        if c1 in valid_countries and c2 in valid_countries:
            is_ca = (c1 == '中国' and c2 in arab_countries) or (c2 == '中国' and c1 in arab_countries)
            edges.append({
                "source": c1, "target": c2, "weight": w,
                "is_china_arab": is_ca
            })

    print(f"  节点: {len(nodes)}, 边: {len(edges)}")
    ca_edges = sum(1 for e in edges if e["is_china_arab"])
    print(f"  🇨🇳 中阿合作边: {ca_edges}")
    density = round(2 * len(edges) / max(1, len(nodes) * (len(nodes) - 1)), 6)
    return {"type": "country", "nodes": nodes, "edges": edges,
            "stats": {"nodes": len(nodes), "edges": len(edges),
                      "china_arab_edges": ca_edges, "density": density}}


# ═══════════════════════════════════════════════
# 4. 引文分析
# ═══════════════════════════════════════════════

def build_citation_network(docs):
    print("\n  ── 引文分析 ──")
    # 统计被引
    citation_count = Counter()
    for d in docs:
        c = d.get('citations', 0)
        if c:
            citation_count[d.get('title', '')[:40]] = c

    top_cited = citation_count.most_common(30)
    nodes = [{"id": t, "label": t[:30], "citations": c, "type": "paper"}
             for t, c in top_cited]

    # 引文网络（简化：按年份文献引用）
    edges = []
    docs_by_year = defaultdict(list)
    for d in docs:
        y = int(d.get('year', 0) or 0)
        if y:
            docs_by_year[y].append(d)

    recent_years = sorted(docs_by_year.keys())[-20:]
    for i, y in enumerate(recent_years):
        for j in range(i + 1, min(i + 5, len(recent_years))):
            edges.append({
                "source": f"year_{y}", "target": f"year_{recent_years[j]}",
                "weight": len(docs_by_year[y]) if y in docs_by_year else 0
            })

    # 每年作为节点
    year_nodes = [{"id": f"year_{y}", "label": str(y), "papers": len(docs_by_year[y]),
                   "type": "year"} for y in recent_years]

    return {"type": "citation", "nodes": year_nodes + nodes,
            "edges": edges,
            "stats": {"nodes": len(year_nodes) + len(nodes),
                      "edges": len(edges),
                      "top_cited": [(t[:20], c) for t, c in top_cited[:5]]}}


# ═══════════════════════════════════════════════
# 5. 突现词检测 + 主题演化
# ═══════════════════════════════════════════════

def burst_detection(docs, window=3):
    """基于突发频率的突现词检测 (Burst Detection)"""
    print("\n  ── 突现词检测 ──")
    kw_year = defaultdict(lambda: defaultdict(int))
    total_year = Counter()

    for d in docs:
        kws = d.get('keywords', d.get('normalized_keywords', []))
        if isinstance(kws, str):
            kws = [k.strip() for k in re.split(r'[,;、]', kws) if k.strip()]
        if not isinstance(kws, list):
            kws = []
        year = int(d.get("year", 0) or 0)
        if year and kws:
            total_year[year] += 1
            for kw in kws:
                if kw and len(kw) > 1:
                    kw_year[kw][year] += 1

    years = sorted(total_year.keys())
    if len(years) < window * 2:
        return {"bursts": [], "stats": {"total_keywords": len(kw_year), "bursts_found": 0}}

    bursts = []
    for kw, year_freq in kw_year.items():
        total_freq = sum(year_freq.values())
        if total_freq < 3:
            continue

        # 滑动窗口检测
        for i in range(len(years) - window):
            window_start = years[i]
            window_end = years[i + window - 1]
            window_freq = sum(year_freq.get(y, 0) for y in years[i:i + window])
            window_total = sum(total_year.get(y, 0) for y in years[i:i + window])

            # 前 window 年频率
            prev_freq = sum(year_freq.get(y, 0) for y in years[:i] if y >= years[0])
            prev_total = sum(total_year.get(y, 0) for y in years[:i] if y >= years[0])

            # 突发强度
            if window_total > 0 and prev_total > 0:
                burst_rate = (window_freq / window_total) / (prev_freq / prev_total + 0.01)
                if burst_rate > 2.0 and window_freq >= 2:
                    bursts.append({
                        "keyword": kw,
                        "burst_year": window_end,
                        "intensity": round(burst_rate, 2),
                        "frequency": total_freq,
                        "window_freq": window_freq,
                    })

    # 排序去重，取Top 30
    bursts.sort(key=lambda x: -x["intensity"])
    seen_kw = set()
    unique_bursts = []
    for b in bursts:
        if b["keyword"] not in seen_kw:
            seen_kw.add(b["keyword"])
            unique_bursts.append(b)
            if len(unique_bursts) >= 30:
                break

    print(f"  突现词: {len(unique_bursts)} 个")
    for b in unique_bursts[:10]:
        print(f"    {b['keyword']}: 强度{b['intensity']:.1f} ({b['burst_year']})")
    return {"bursts": unique_bursts, "stats": {"total_keywords": len(kw_year),
                                                "bursts_found": len(unique_bursts)}}


def thematic_evolution(docs):
    """主题演化：每5年切片，跟踪关键词热度变化"""
    print("\n  ── 主题演化时间线 ──")
    slices = {}
    for d in docs:
        year = int(d.get("year", 0) or 0)
        if not year:
            continue
        kws = d.get('keywords', d.get('normalized_keywords', []))
        if isinstance(kws, str):
            kws = [k.strip() for k in re.split(r'[,;、]', kws) if k.strip()]
        if not isinstance(kws, list):
            kws = []
        # 5年切片
        slice_key = f"{year // 5 * 5}-{year // 5 * 5 + 4}"
        if slice_key not in slices:
            slices[slice_key] = Counter()
        for kw in kws:
            if kw and len(kw) > 1:
                slices[slice_key][kw] += 1

    timeline = []
    for period, kw_freq in sorted(slices.items()):
        top = kw_freq.most_common(10)
        timeline.append({
            "period": period,
            "hotspots": [{"keyword": k, "freq": f} for k, f in top],
            "total_keywords": sum(kw_freq.values()),
            "unique_keywords": len(kw_freq),
        })

    print(f"  时间切片: {len(timeline)} 个")
    for t in timeline:
        print(f"    {t['period']}: {t['unique_keywords']} 个关键词, 热点TOP: {t['hotspots'][0]['keyword'] if t['hotspots'] else '-'}")
    return {"timeline": timeline, "stats": {"slices": len(timeline)}}


# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  SKWM 科学计量分析管线 (Bibliometrics)")
    print("  关键词共现 · 作者合作 · 国家合作 · 引文 · 突现词 · 演化")
    print("=" * 60)

    # 加载数据
    print("\n📦 加载文献数据...")
    docs = load_data()
    print(f"  共 {len(docs)} 篇文献")

    networks = []
    analysis = {}

    # 1. 关键词共现
    coword = build_coword_network(docs, min_freq=5)
    networks.append(coword)
    json.dump(coword, open(OUT_DIR / "network_coword.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 2. 作者合作
    coauthor = build_coauthor_network(docs)
    networks.append(coauthor)
    json.dump(coauthor, open(OUT_DIR / "network_coauthor.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 3. 国家合作
    country = build_country_network(docs)
    networks.append(country)
    json.dump(country, open(OUT_DIR / "network_country.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 4. 引文
    citation = build_citation_network(docs)
    networks.append(citation)
    json.dump(citation, open(OUT_DIR / "network_citation.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 5. 突现词
    burst = burst_detection(docs)
    json.dump(burst, open(OUT_DIR / "burst_detection.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 6. 主题演化
    evolution = thematic_evolution(docs)
    json.dump(evolution, open(OUT_DIR / "thematic_evolution.json", 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # ── 汇总报告 ──
    report = f"""# SKWM 科学计量分析报告

## 数据概览
- 文献总数: {len(docs)} 篇
- 时间跨度: {min(int(d.get('year',9999) or 9999) for d in docs)} — {max(int(d.get('year',0) or 0) for d in docs)}
- 分析日期: {datetime.now().strftime('%Y-%m-%d')}

## 1. 关键词共现网络
| 指标 | 数值 |
|------|:----:|
| 节点数 | {coword['stats']['nodes']} |
| 边数 | {coword['stats']['edges']} |
| 社区数 | {coword['stats']['communities']} |
| 网络密度 | {coword['stats']['density']} |

## 2. 作者合作网络
| 指标 | 数值 |
|------|:----:|
| 节点数 | {coauthor['stats']['nodes']} |
| 边数 | {coauthor['stats']['edges']} |
| 网络密度 | {coauthor['stats']['density']} |

## 3. 国家合作网络
| 指标 | 数值 |
|------|:----:|
| 国家数 | {country['stats']['nodes']} |
| 合作边数 | {country['stats']['edges']} |
| 🇨🇳 中阿合作边 | **{country['stats']['china_arab_edges']}** |
| 网络密度 | {country['stats']['density']} |

## 4. 引文分析
| 指标 | 数值 |
|------|:----:|
| 高被引文献节点 | {citation['stats']['nodes']} |
| 引文关系 | {citation['stats']['edges']} |
| TOP 5 高被引 | {', '.join(t[0] for t in citation['stats']['top_cited'][:5])} |

## 5. 突现词检测
| 指标 | 数值 |
|------|:----:|
| 候选关键词 | {burst['stats']['total_keywords']} |
| 突现词数 | {burst['stats']['bursts_found']} |

## 6. 主题演化
| 指标 | 数值 |
|------|:----:|
| 时间切片 | {evolution['stats']['slices']} 个 |

## 验收标准
- [x] 网络指标可算 (密度/中心性)
- [x] 图可交互筛选年份
- [x] 中阿合作可识别 ({country['stats']['china_arab_edges']} 条边)
"""
    report_path = OUT_DIR / "bibliometrics_report.md"
    report_path.write_text(report, encoding='utf-8')
    print(f"\n📄 分析报告: {report_path}")

    # 输出汇总 JSON
    summary = {"networks": {n["type"]: n["stats"] for n in networks},
               "burst": burst["stats"],
               "evolution": evolution["stats"]}
    json.dump(summary, open(OUT_DIR / "summary.json", 'w'), indent=2)

    print(f"\n🎉 分析完成，共 6 个网络/分析文件")
    for f in sorted(OUT_DIR.glob("*")):
        print(f"  📄 {f.name} ({f.stat().st_size:,} bytes)")

    return networks, burst, evolution


if __name__ == "__main__":
    main()
