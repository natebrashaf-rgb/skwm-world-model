#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task C/D 最终版 - 基于已验证阿语文献
"""
import json
import re
import hashlib
from pathlib import Path
from collections import Counter

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")

def load_b1(path):
    raw = open(path, encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def load_json(path):
    return json.load(open(path, encoding='utf-8'))

def sha256_of(path):
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()

# ============================================================
# Task C: 严格对照实验
# ============================================================
def run_task_c():
    print("="*70)
    print("Task C: 严格'排除阿语 vs 包含阿语'对照实验")
    print("="*70)
    
    # 加载已验证的state_vectors
    sv_c0 = load_json(OUTPUT_DIR / "state_vectors_C0_verified.json")
    sv_c1 = load_json(OUTPUT_DIR / "state_vectors_C1_verified.json")
    
    # 加载已验证的B1
    b1 = load_b1(DATA_DIR / "B1_文献主表_已验证.json")
    arabic = [p for p in b1 if p.get("language") == "ar"]
    
    print(f"\n数据版本: 已验证")
    print(f"  B1总数: {len(b1)}条")
    print(f"  阿语文献: {len(arabic)}条")
    print(f"  C0(排除阿语): {len(b1) - len(arabic)}条")
    print(f"  C1(包含阿语): {len(b1)}条")
    
    # Q1: 主题趋势变化（Jaccard相似度）
    print("\n[Q1] 主题趋势变化")
    jaccards = []
    for year in ["2020", "2021", "2022", "2023", "2024"]:
        if year in sv_c0 and year in sv_c1:
            topics_c0 = set(sv_c0[year].keys())
            topics_c1 = set(sv_c1[year].keys())
            intersection = topics_c0 & topics_c1
            union = topics_c0 | topics_c1
            jaccard = len(intersection) / len(union) if union else 0
            jaccards.append(jaccard)
            print(f"  {year}: Jaccard={jaccard:.4f} (C0:{len(topics_c0)}主题, C1:{len(topics_c1)}主题)")
    
    avg_jaccard = sum(jaccards) / len(jaccards) if jaccards else 0
    q1_trend_change = avg_jaccard < 0.95
    print(f"\n  平均Jaccard: {avg_jaccard:.4f}")
    print(f"  q1_trend_change: {q1_trend_change} ({'有变化' if q1_trend_change else '无变化'})")
    
    # Q2: 新增主题
    print("\n[Q2] 新增主题")
    all_topics_c0 = set()
    all_topics_c1 = set()
    for year in ["2020", "2021", "2022", "2023", "2024"]:
        if year in sv_c0:
            all_topics_c0.update(sv_c0[year].keys())
        if year in sv_c1:
            all_topics_c1.update(sv_c1[year].keys())
    
    new_topics = all_topics_c1 - all_topics_c0
    print(f"  C0主题数: {len(all_topics_c0)}")
    print(f"  C1主题数: {len(all_topics_c1)}")
    print(f"  新增主题: {len(new_topics)}个")
    
    if new_topics:
        # 统计新增主题的热度
        new_topics_with_heat = []
        for year in ["2020", "2021", "2022", "2023", "2024"]:
            if year in sv_c1:
                for topic in new_topics:
                    if topic in sv_c1[year]:
                        heat = sv_c1[year][topic][0]
                        new_topics_with_heat.append((topic, year, heat))
        
        new_topics_with_heat.sort(key=lambda x: -x[2])
        print(f"  新增主题样例（按热度排序）:")
        for topic, year, heat in new_topics_with_heat[:10]:
            print(f"    {year}年 {topic}: 热度={heat:.1f}")
    
    # Q3: 阿语是否适合单独建模
    print("\n[Q3] 阿语是否适合单独建模")
    year_dist = Counter(p.get("year") for p in arabic if p.get("year"))
    print(f"  样本量: {len(arabic)}篇")
    print(f"  年份分布: {dict(year_dist)}")
    print(f"  年份覆盖: {len(year_dist)}年")
    print(f"  结论: {'不适合' if len(arabic) < 50 else '可能适合'} (样本量{'<50' if len(arabic) < 50 else '>=50'})")
    
    # 保存结果
    results = {
        "data_version": "已验证",
        "b1_count": len(b1),
        "arabic_count": len(arabic),
        "q1_jaccard": avg_jaccard,
        "q1_trend_change": q1_trend_change,
        "q2_new_topics": len(new_topics),
        "q3_sample_size": len(arabic),
        "q3_year_coverage": len(year_dist),
    }
    
    return results

# ============================================================
# Task D: 内容分析
# ============================================================
def run_task_d():
    print("\n" + "="*70)
    print("Task D: 阿语文献内容分析")
    print("="*70)
    
    # 加载已验证的B1
    b1 = load_b1(DATA_DIR / "B1_文献主表_已验证.json")
    arabic = [p for p in b1 if p.get("language") == "ar"]
    
    print(f"\n阿语文献总数: {len(arabic)}条（已验证）")
    
    # 全文状态
    has_pdf = sum(1 for p in arabic if p.get("has_pdf"))
    text_extracted = sum(1 for p in arabic if p.get("text_extracted"))
    human_read = 0  # 未人工验证
    
    print(f"\n全文状态:")
    print(f"  has_pdf: {has_pdf}条")
    print(f"  text_extracted: {text_extracted}条")
    print(f"  human_read: {human_read}条")
    
    # 文旅分类（缩窄词表）
    CORE_TOURISM = [
        "旅游", "tourism", "سياحة",
        "遗产", "heritage", "تراث",
        "文化遗产", "cultural heritage",
        "博物馆", "museum",
        "目的地", "destination",
        "沙漠旅游", "desert tourism",
    ]
    
    MAYBE_TOURISM = [
        "文化", "culture",
        "阿拉伯", "arab",
        "手稿", "مخطوط",
        "丝绸之路", "silk road",
    ]
    
    def classify_tourism(paper):
        text = (paper.get("title","") + " " + " ".join(paper.get("keywords",[]))).lower()
        core_hit = any(kw in text for kw in CORE_TOURISM)
        maybe_hit = any(kw in text for kw in MAYBE_TOURISM)
        if core_hit:
            return "core"
        elif maybe_hit:
            return "maybe"
        else:
            return "none"
    
    tourism_cats = [classify_tourism(p) for p in arabic]
    core_n = tourism_cats.count("core")
    maybe_n = tourism_cats.count("maybe")
    none_n = tourism_cats.count("none")
    
    print(f"\n文旅分类:")
    print(f"  核心: {core_n}条")
    print(f"  可能: {maybe_n}条")
    print(f"  非文旅: {none_n}条")
    
    # 层级本体
    level_dist = {"L1_文旅核心": core_n, "L2_文化认同": len(arabic) - core_n - none_n, "L5_其他": none_n}
    
    print(f"\n层级本体:")
    for level, count in level_dist.items():
        print(f"  {level}: {count}条")
    
    # 保存结果
    results = {
        "total": len(arabic),
        "has_pdf": has_pdf,
        "text_extracted": text_extracted,
        "human_read": human_read,
        "tourism_core": core_n,
        "tourism_maybe": maybe_n,
        "tourism_none": none_n,
        "level_distribution": level_dist,
    }
    
    return results

# ============================================================
# 主函数
# ============================================================
def main():
    print("\n" + "="*70)
    print("Task C/D 最终版 - 基于已验证阿语文献")
    print("="*70)
    
    c_results = run_task_c()
    d_results = run_task_d()
    
    # 保存完整结果
    final_results = {
        "meta": {
            "timestamp": "2026-08-27",
            "data_version": "已验证",
            "description": "基于DOI验证的阿语文献（15篇已验证，12篇排除）",
        },
        "task_c": c_results,
        "task_d": d_results,
    }
    
    output_path = OUTPUT_DIR / "task_cd_final_verified_results.json"
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "="*70)
    print("完成！")
    print("="*70)
    print(f"结果已保存: {output_path}")
    
    return final_results

if __name__ == "__main__":
    main()
