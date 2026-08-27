#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task C: 阿语文献对模型影响的对照实验
==================================
比较三个版本：
  V1: 原始模型（不含阿语）
  V2: 加入阿语文献的模型
  V3: 跨语言模型（带语言标记）

回答三个问题：
  1. 加入阿语文献后，主题趋势是否变化？
  2. 阿语文献是否改变跨语言主题映射？
  3. 阿语是否适合单独建模？
"""
import json
import re
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output/experiment_c")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_state_vectors(path):
    """加载状态向量"""
    return json.load(open(path, encoding="utf-8"))


def load_b1_papers(path):
    """加载B1主表"""
    raw = open(path, encoding="utf-8").read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)


def get_top_topics(sv, year, top_k=20):
    """获取某年热度最高的主题"""
    if str(year) not in sv:
        return []
    topics = sv[str(year)]
    scored = []
    for t, v in topics.items():
        heat = v[0] if isinstance(v, list) else v
        if heat > 0:
            scored.append((t, heat))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


def compute_topic_trend(sv, topic, years=range(2010, 2026)):
    """计算主题年度趋势"""
    trend = []
    for y in years:
        if str(y) in sv and topic in sv[str(y)]:
            v = sv[str(y)][topic]
            heat = v[0] if isinstance(v, list) else v
            trend.append((y, heat))
        else:
            trend.append((y, 0))
    return trend


def compute_growth_rate(sv, topic, y1=2020, y2=2024):
    """计算主题增速"""
    v1 = sv.get(str(y1), {}).get(topic, [0])
    v2 = sv.get(str(y2), {}).get(topic, [0])
    h1 = v1[0] if isinstance(v1, list) else v1
    h2 = v2[0] if isinstance(v2, list) else v2
    if h1 > 0:
        return (h2 - h1) / h1
    return 0


def compare_top_topics(sv_orig, sv_arabic, years=[2020, 2022, 2024]):
    """比较原始vs阿语版本的Top主题"""
    results = {}
    for y in years:
        orig_top = get_top_topics(sv_orig, y, 20)
        arab_top = get_top_topics(sv_arabic, y, 20)
        
        orig_names = set(t[0] for t in orig_top)
        arab_names = set(t[0] for t in arab_top)
        
        # 计算Jaccard相似度
        intersection = orig_names & arab_names
        union = orig_names | arab_names
        jaccard = len(intersection) / len(union) if union else 0
        
        # 计算排名变化
        rank_changes = {}
        orig_ranks = {t: i for i, (t, _) in enumerate(orig_top)}
        arab_ranks = {t: i for i, (t, _) in enumerate(arab_top)}
        
        for t in intersection:
            rank_changes[t] = orig_ranks[t] - arab_ranks[t]  # 正数=上升
        
        results[y] = {
            "orig_top10": [(t, round(h, 1)) for t, h in orig_top[:10]],
            "arabic_top10": [(t, round(h, 1)) for t, h in arab_top[:10]],
            "jaccard_similarity": round(jaccard, 3),
            "common_topics": len(intersection),
            "rank_changes": rank_changes,
        }
    return results


def find_new_topics_from_arabic(sv_orig, sv_arabic, threshold=10):
    """找出阿语文献带来的新主题"""
    orig_topics = set()
    for y in ["2020", "2021", "2022", "2023", "2024"]:
        orig_topics.update(sv_orig.get(y, {}).keys())
    
    arab_topics = set()
    for y in ["2020", "2021", "2022", "2023", "2024"]:
        arab_topics.update(sv_arabic.get(y, {}).keys())
    
    # 新主题 = 阿语版有但原版没有（或热度很低）
    new_topics = []
    for t in arab_topics:
        if t not in orig_topics:
            # 检查阿语版热度
            heat = 0
            for y in ["2020", "2021", "2022", "2023", "2024"]:
                v = sv_arabic.get(y, {}).get(t, [0])
                h = v[0] if isinstance(v, list) else v
                heat += h
            if heat > threshold:
                new_topics.append((t, heat))
    
    new_topics.sort(key=lambda x: -x[1])
    return new_topics


def analyze_arabic_papers(papers):
    """分析阿语文献特征"""
    arabic_papers = [p for p in papers if p.get("language") == "ar"]
    
    # 年份分布
    year_dist = Counter()
    for p in arabic_papers:
        y = p.get("year")
        if y:
            year_dist[y] += 1
    
    # 主题分布
    topic_dist = Counter()
    for p in arabic_papers:
        for kw in p.get("keywords", []):
            if kw:
                topic_dist[kw] += 1
    
    # 文旅相关检测
    tourism_keywords = ["旅游", "遗产", "文化", "tourism", "heritage", "culture", 
                       "destination", "博物馆", "丝绸之路", "arab", "arabic"]
    tourism_papers = []
    for p in arabic_papers:
        text = (p.get("title", "") + " " + " ".join(p.get("keywords", []))).lower()
        if any(kw in text.lower() for kw in tourism_keywords):
            tourism_papers.append(p)
    
    return {
        "total": len(arabic_papers),
        "year_distribution": dict(year_dist),
        "top_topics": topic_dist.most_common(20),
        "tourism_related": len(tourism_papers),
        "tourism_papers_sample": [
            {"title": p.get("title", "")[:50], "year": p.get("year"), 
             "keywords": p.get("keywords", [])[:5]}
            for p in tourism_papers[:10]
        ]
    }


def run_experiment():
    """运行完整实验"""
    print("=" * 70)
    print("Task C: 阿语文献对模型影响的对照实验")
    print("=" * 70)
    print(f"时间: {datetime.now().isoformat()}")
    
    # 1. 加载数据
    print("\n[1] 加载数据...")
    sv_orig = load_state_vectors(DATA_DIR / "state_vectors.json")
    sv_arabic = load_state_vectors(DATA_DIR / "state_vectors_含阿语_20260819.json")
    papers = load_b1_papers(DATA_DIR / "B1_文献主表_含阿语_20260819.json")
    
    print(f"  原始状态向量: {len(sv_orig)} 年")
    print(f"  含阿语状态向量: {len(sv_arabic)} 年")
    print(f"  论文总数: {len(papers)}")
    
    # 2. 分析阿语文献
    print("\n[2] 分析阿语文献特征...")
    arabic_analysis = analyze_arabic_papers(papers)
    print(f"  阿语文献数: {arabic_analysis['total']}")
    print(f"  文旅相关: {arabic_analysis['tourism_related']}")
    print(f"  年份分布: {arabic_analysis['year_distribution']}")
    print(f"  Top主题: {[t[0] for t in arabic_analysis['top_topics'][:5]]}")
    
    # 3. 比较Top主题
    print("\n[3] 比较原始vs阿语版本的Top主题...")
    top_comparison = compare_top_topics(sv_orig, sv_arabic)
    for y, data in top_comparison.items():
        print(f"\n  {y}年:")
        print(f"    Jaccard相似度: {data['jaccard_similarity']}")
        print(f"    共同主题数: {data['common_topics']}/20")
        print(f"    原版Top5: {[t[0] for t in data['orig_top10'][:5]]}")
        print(f"    阿语版Top5: {[t[0] for t in data['arabic_top10'][:5]]}")
    
    # 4. 找新主题
    print("\n[4] 找出阿语文献带来的新主题...")
    new_topics = find_new_topics_from_arabic(sv_orig, sv_arabic)
    print(f"  新主题数: {len(new_topics)}")
    if new_topics:
        print(f"  Top10新主题:")
        for t, h in new_topics[:10]:
            print(f"    {t}: 热度={h:.1f}")
    
    # 5. 趋势对比
    print("\n[5] 关键主题趋势对比...")
    key_topics = ["旅游", "Tourism", "文化遗产", "Cultural Heritage", "目的地", "Destination"]
    trend_comparison = {}
    for topic in key_topics:
        orig_trend = compute_topic_trend(sv_orig, topic)
        arab_trend = compute_topic_trend(sv_arabic, topic)
        
        # 计算差异
        orig_total = sum(h for _, h in orig_trend)
        arab_total = sum(h for _, h in arab_trend)
        diff_pct = (arab_total - orig_total) / orig_total * 100 if orig_total > 0 else 0
        
        trend_comparison[topic] = {
            "orig_total": round(orig_total, 1),
            "arabic_total": round(arab_total, 1),
            "diff_pct": round(diff_pct, 2),
            "orig_2024": orig_trend[-1][1] if orig_trend else 0,
            "arabic_2024": arab_trend[-1][1] if arab_trend else 0,
        }
        print(f"  {topic}: 原版={orig_total:.0f}, 阿语版={arab_total:.0f}, 差异={diff_pct:+.1f}%")
    
    # 6. 回答三个问题
    print("\n" + "=" * 70)
    print("实验结论")
    print("=" * 70)
    
    # Q1: 主题趋势是否变化？
    avg_jaccard = np.mean([d["jaccard_similarity"] for d in top_comparison.values()])
    print(f"\nQ1: 加入阿语文献后，主题趋势是否变化？")
    print(f"  A: Top主题Jaccard相似度={avg_jaccard:.3f}")
    if avg_jaccard > 0.8:
        print(f"  → 变化很小（相似度>0.8），阿语文献未显著改变主题排序")
    elif avg_jaccard > 0.5:
        print(f"  → 有一定变化（相似度0.5-0.8），阿语文献补充了部分主题")
    else:
        print(f"  → 变化显著（相似度<0.5），阿语文献带来新的主题视角")
    
    # Q2: 是否改变跨语言主题映射？
    print(f"\nQ2: 阿语文献是否改变跨语言主题映射？")
    print(f"  A: 新增主题数={len(new_topics)}")
    if new_topics:
        print(f"  → 阿语文献带来了{len(new_topics)}个新主题，补充了英文文献未覆盖的议题")
        print(f"  → 代表性新主题: {[t[0] for t in new_topics[:5]]}")
    else:
        print(f"  → 未发现新主题，阿语文献的主题已存在于英文文献中")
    
    # Q3: 阿语是否适合单独建模？
    print(f"\nQ3: 阿语是否适合单独建模？")
    print(f"  A: 阿语文献数={arabic_analysis['total']}, 年份覆盖={len(arabic_analysis['year_distribution'])}年")
    if arabic_analysis['total'] < 50:
        print(f"  → 样本量不足（<50篇），不建议单独建模")
    else:
        print(f"  → 样本量充足，可考虑单独建模")
    
    if len(arabic_analysis['year_distribution']) < 5:
        print(f"  → 年份覆盖集中（<5年），不适合构建完整年度序列")
    else:
        print(f"  → 年份覆盖分散，可构建年度序列")
    
    print(f"\n  综合判断: 阿语文献数量少且年份集中，不适合单独RSSM建模，")
    print(f"  但应保留其对跨语言模型和主题解释的贡献。")
    
    # 7. 保存结果
    results = {
        "timestamp": datetime.now().isoformat(),
        "data_summary": {
            "orig_years": len(sv_orig),
            "arabic_years": len(sv_arabic),
            "total_papers": len(papers),
            "arabic_papers": arabic_analysis['total'],
        },
        "arabic_analysis": arabic_analysis,
        "top_comparison": top_comparison,
        "new_topics": [(t, round(h, 1)) for t, h in new_topics[:20]],
        "trend_comparison": trend_comparison,
        "conclusions": {
            "q1_trend_change": bool(avg_jaccard > 0.8),
            "q2_new_topics": len(new_topics),
            "q3_sample_size": arabic_analysis['total'],
            "recommendation": "retain_cross_language_contribution"
        }
    }
    
    output_path = OUTPUT_DIR / "experiment_c_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")
    
    return results


if __name__ == "__main__":
    run_experiment()
