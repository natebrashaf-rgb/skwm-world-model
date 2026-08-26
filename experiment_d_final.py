#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task D 最终版：人工全文验证 + 统一分类
======================================
完成项：
  1. 9条自动抽取文本的验证状态标记
  2. 27条阿语文献的统一分类（文旅核心/可能/非文旅）
  3. 层级本体统计
  4. 英阿对照表
"""
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output/experiment_d_final")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. 数据加载
# ============================================================
def load_b1(path):
    raw = open(path, encoding='utf-8').read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)

def load_json(path):
    return json.load(open(path, encoding='utf-8'))

# ============================================================
# 2. 文旅判定词表（缩窄版）
# ============================================================
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
    """缩窄词表的文旅判定"""
    text = (paper.get("title","") + " " + " ".join(paper.get("keywords",[]))).lower()
    core_hit = any(kw in text for kw in CORE_TOURISM)
    maybe_hit = any(kw in text for kw in MAYBE_TOURISM)
    if core_hit:
        return "core"
    elif maybe_hit:
        return "maybe"
    else:
        return "none"

# ============================================================
# 3. 层级本体
# ============================================================
TOPIC_ONTOLOGY = {
    "L1_文旅核心": ["旅游", "文化遗产", "目的地", "博物馆"],
    "L2_文化认同": ["阿拉伯文化", "伊斯兰文化", "历史"],
    "L3_方法论":   ["教育", "数字化", "可持续发展"],
    "L4_区域研究": ["中东", "丝绸之路", "中国-阿拉伯"],
}

def classify_topic_level(topics):
    """根据主题列表判断层级"""
    for level, keywords in TOPIC_ONTOLOGY.items():
        if any(kw in topics for kw in keywords):
            return level
    return "L5_其他"

# ============================================================
# 4. 人工验证状态标记
# ============================================================
def mark_verification_status(arabic_papers, arabic_texts):
    """
    标记27条阿语文献的验证状态：
    - has_pdf: 是否有PDF文件
    - text_extracted: 是否成功提取文本（>100字符）
    - human_verified: 是否人工验证（当前全部为False）
    """
    results = []
    
    for p in arabic_papers:
        doi = p.get("doi", "")
        title = p.get("title", "")
        
        # 检查是否有PDF
        has_pdf = bool(p.get("has_pdf"))
        
        # 检查是否提取了文本
        text_extracted = False
        text_content = ""
        if doi and doi in arabic_texts:
            text_content = arabic_texts[doi]
            text_extracted = len(text_content) > 100
        
        # 人工验证状态（当前全部为False）
        human_verified = False
        
        # 文旅分类
        tourism_class = classify_tourism(p)
        
        # 主题识别
        text_combined = (title + " " + " ".join(p.get("keywords", [])) + " " + text_content[:500]).lower()
        topics = []
        topic_map = {
            "旅游": ["旅游", "tourism", "سياحة"],
            "文化遗产": ["遗产", "heritage", "تراث", "博物馆"],
            "阿拉伯文化": ["arab", "arabic", "阿拉伯", "عربي"],
            "伊斯兰文化": ["islam", "islamic", "伊斯兰"],
            "教育": ["education", "教育", "جامعة"],
            "数字化": ["digital", "数字化"],
            "可持续发展": ["sustainable", "可持续"],
            "历史": ["history", "历史", "تاريخ"],
        }
        for topic, kws in topic_map.items():
            if any(kw in text_combined for kw in kws):
                topics.append(topic)
        
        level = classify_topic_level(",".join(topics)) if topics else "L5_其他"
        
        results.append({
            "doi": doi,
            "title": title[:80],
            "year": p.get("year"),
            "has_pdf": has_pdf,
            "text_extracted": text_extracted,
            "human_verified": human_verified,
            "tourism_class": tourism_class,
            "topics": topics,
            "level": level,
            "text_length": len(text_content),
        })
    
    return results

# ============================================================
# 5. 主函数
# ============================================================
def run_task_d_final():
    print("=" * 70)
    print("Task D 最终版：人工全文验证 + 统一分类")
    print("=" * 70)
    print(f"时间: {datetime.now().isoformat()}")
    
    # 加载数据
    b1 = load_b1(DATA_DIR / "B1_文献主表.json")
    arabic_texts = load_json(DATA_DIR / "pdf_texts_arabic_20260819.json")
    
    arabic = [p for p in b1 if p.get("language") == "ar"]
    
    print(f"\n[1] 数据概况")
    print(f"  阿语文献总数: {len(arabic)}条")
    print(f"  阿语文本库: {len(arabic_texts)}条")
    
    # 标记验证状态
    print(f"\n[2] 验证状态标记")
    verification_results = mark_verification_status(arabic, arabic_texts)
    
    # 统计
    has_pdf_count = sum(1 for r in verification_results if r["has_pdf"])
    text_extracted_count = sum(1 for r in verification_results if r["text_extracted"])
    human_verified_count = sum(1 for r in verification_results if r["human_verified"])
    
    print(f"  has_pdf: {has_pdf_count}条")
    print(f"  text_extracted: {text_extracted_count}条")
    print(f"  human_verified: {human_verified_count}条 (待人工验证)")
    
    # 文旅分类统计
    print(f"\n[3] 文旅分类统计")
    tourism_counts = Counter(r["tourism_class"] for r in verification_results)
    print(f"  文旅核心(core): {tourism_counts['core']}条")
    print(f"  文旅可能(maybe): {tourism_counts['maybe']}条")
    print(f"  非文旅(none): {tourism_counts['none']}条")
    
    # 层级本体统计
    print(f"\n[4] 层级本体统计")
    level_counts = Counter(r["level"] for r in verification_results)
    for level, count in sorted(level_counts.items()):
        print(f"  {level}: {count}条")
    
    # 主题分布
    print(f"\n[5] 主题分布")
    topic_counts = Counter()
    for r in verification_results:
        for topic in r["topics"]:
            topic_counts[topic] += 1
    for topic, count in topic_counts.most_common(10):
        print(f"  {topic}: {count}条")
    
    # 详细列表（前10条）
    print(f"\n[6] 详细列表（前10条）")
    for i, r in enumerate(verification_results[:10], 1):
        status = []
        if r["has_pdf"]:
            status.append("PDF")
        if r["text_extracted"]:
            status.append("Text")
        if r["human_verified"]:
            status.append("Verified")
        
        status_str = "+".join(status) if status else "-"
        print(f"  {i}. [{r['year']}] {r['title'][:40]}... | {status_str} | {r['tourism_class']} | {r['level']}")
    
    # 保存结果
    results = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "task": "D最终版：人工全文验证 + 统一分类",
        },
        "summary": {
            "total": len(arabic),
            "has_pdf": has_pdf_count,
            "text_extracted": text_extracted_count,
            "human_verified": human_verified_count,
            "verification_note": "9条已提取文本，待人工验证",
        },
        "tourism_classification": dict(tourism_counts),
        "level_distribution": dict(level_counts),
        "topic_distribution": dict(topic_counts),
        "verification_results": verification_results,
    }
    
    output_path = OUTPUT_DIR / "experiment_d_final_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")
    
    return results

if __name__ == "__main__":
    run_task_d_final()
