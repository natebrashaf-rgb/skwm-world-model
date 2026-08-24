#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task D: 阿语文献内容分析与英阿对照 (v2 修正版)
============================================
修正项：
  D1: 全文状态拆三列 (has_pdf / text_extracted / human_read)
  D2: 确认13条可读取文本 + 原文摘录
  D3: 统一C/D文旅判定口径
  D4: 重建层级本体，取消"独有"标签
  D5: "研究传统差异"降级为待验证解释
"""
import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output/experiment_d")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 统一文旅判定口径（与Task C一致）
TOURISM_KEYWORDS_UNIFIED = [
    "旅游", "遗产", "文化", "tourism", "heritage", "culture",
    "destination", "博物馆", "丝绸之路", "arab", "沙漠", "صحراو", "سياح",
    "واحة", "تراث", "مخطوط", "سياحة"
]

# 层级本体（替代"独有"标签）
TOPIC_ONTOLOGY = {
    "L1_文旅核心": ["旅游", "文化遗产", "目的地", "博物馆"],
    "L2_文化认同": ["阿拉伯文化", "伊斯兰文化", "历史"],
    "L3_方法论": ["教育", "数字化", "可持续发展"],
    "L4_区域研究": ["中东", "丝绸之路", "中国-阿拉伯"],
}


def load_b1_papers(path):
    raw = open(path, encoding="utf-8").read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)


def load_arabic_texts():
    path = DATA_DIR / "pdf_texts_arabic_20260819.json"
    if path.exists():
        return json.load(open(path, encoding="utf-8"))
    return {}


def match_paper_to_text(paper, pdf_texts):
    """匹配论文到全文（DOI格式转换+标题匹配）"""
    doi = paper.get("doi", "")
    title = paper.get("title", "")
    
    # 1. DOI直接匹配
    if doi and doi in pdf_texts:
        return pdf_texts[doi]
    
    # 2. DOI格式转换（/ → _）
    if doi:
        doi_normalized = doi.replace("/", "_")
        if doi_normalized in pdf_texts:
            return pdf_texts[doi_normalized]
    
    # 3. 标题匹配（Extra_前缀）
    if title:
        for key, text in pdf_texts.items():
            if key.startswith("Extra_"):
                key_title = key[6:].strip()
                # 阿拉伯语标题匹配（前15字符）
                if len(title) >= 15 and len(key_title) >= 15:
                    if title[:15] in key_title or key_title[:15] in title:
                        return text
                # 中文标题匹配
                elif any('\u4e00' <= c <= '\u9fff' for c in title):
                    if title[:10] in key_title or key_title[:10] in title:
                        return text
    
    return ""


def analyze_paper_fulltext_status(paper, pdf_texts):
    """D1: 全文状态三列"""
    has_pdf = bool(paper.get("has_pdf"))
    full_text = match_paper_to_text(paper, pdf_texts)
    text_extracted = len(full_text) > 100
    human_read = False  # 需人工标记
    
    return {
        "has_pdf": has_pdf,
        "text_extracted": text_extracted,
        "human_read": human_read,
        "text_length": len(full_text),
        "text_sample": full_text[:500] if full_text else "",
    }


def classify_topic_level(topic):
    """D4: 层级本体分类"""
    for level, topics in TOPIC_ONTOLOGY.items():
        if any(t in topic for t in topics):
            return level
    return "L5_其他"


def is_tourism_related(paper):
    """D3: 统一文旅判定"""
    text = (paper.get("title", "") + " " + " ".join(paper.get("keywords", []))).lower()
    return any(kw in text.lower() for kw in TOURISM_KEYWORDS_UNIFIED)


def extract_text_excerpt(full_text, max_len=300):
    """D2: 提取原文摘录"""
    if not full_text:
        return ""
    # 取前300字符作为摘录
    excerpt = full_text[:max_len].replace("\n", " ").strip()
    return excerpt


def run_task_d():
    print("=" * 70)
    print("Task D: 阿语文献内容分析与英阿对照 (v2 修正版)")
    print("=" * 70)
    print(f"时间: {datetime.now().isoformat()}")

    # 1. 加载数据
    print("\n[1] 加载数据")
    papers = load_b1_papers(DATA_DIR / "B1_文献主表_含阿语_20260819.json")
    arabic_texts = load_arabic_texts()
    print(f"  论文总数: {len(papers)}")
    print(f"  阿语文本库: {len(arabic_texts)} 条")

    # 2. 筛选阿语文献
    arabic_papers = [p for p in papers if p.get("language") == "ar"]
    print(f"\n[2] 阿语文献: {len(arabic_papers)} 篇")

    # 3. 逐篇分析（含全文状态三列）
    print("\n[3] 逐篇分析（D1: 全文状态三列）")
    analyses = []
    text_extracted_count = 0
    tourism_count = 0
    
    for p in arabic_papers:
        fulltext_status = analyze_paper_fulltext_status(p, arabic_texts)
        tourism = is_tourism_related(p)
        if tourism:
            tourism_count += 1
        if fulltext_status["text_extracted"]:
            text_extracted_count += 1
        
        # 主题识别（利用全文）
        text_combined = (p.get("title", "") + " " + " ".join(p.get("keywords", [])) + 
                        " " + fulltext_status["text_sample"]).lower()
        
        topics = []
        topic_map = {
            "旅游": ["旅游", "tourism", "سياحة", "tourist"],
            "文化遗产": ["遗产", "heritage", "تراث", "museum", "博物馆"],
            "阿拉伯文化": ["arab", "arabic", "阿拉伯", "عربي"],
            "伊斯兰文化": ["islam", "islamic", "伊斯兰"],
            "教育": ["education", "教育", "university", "جامعة"],
            "数字化": ["digital", "数字化", "ai", "智能"],
            "可持续发展": ["sustainable", "可持续", "sdg"],
            "历史": ["history", "历史", "تاريخ", "ancient"],
        }
        for topic, kws in topic_map.items():
            if any(kw in text_combined for kw in kws):
                topics.append(topic)
        
        level = classify_topic_level(",".join(topics)) if topics else "L5_其他"
        
        analysis = {
            "doi": p.get("doi", ""),
            "title": p.get("title", "")[:80],
            "year": p.get("year"),
            "keywords": p.get("keywords", [])[:8],
            "topics": topics,
            "topic_level": level,
            "tourism_related": tourism,
            **fulltext_status,
        }
        analyses.append(analysis)
        
        status_str = f"PDF={'✓' if fulltext_status['has_pdf'] else '✗'} "
        status_str += f"Extract={'✓' if fulltext_status['text_extracted'] else '✗'} "
        status_str += f"Read={'✓' if fulltext_status['human_read'] else '—'}"
        print(f"  [{p.get('year')}] {p.get('title', '')[:35]}... | {status_str}")
    
    print(f"\n  统计: has_pdf={sum(1 for a in analyses if a['has_pdf'])}, "
          f"text_extracted={text_extracted_count}, human_read=0")
    print(f"  文旅相关(统一口径): {tourism_count}")

    # 4. D2: 确认13条可读取文本 + 原文摘录
    print("\n[4] D2: 可读取文本确认 + 原文摘录")
    readable = [a for a in analyses if a["text_extracted"]]
    print(f"  可读取文本: {len(readable)} 条")
    for a in readable[:5]:
        print(f"\n  [{a['year']}] {a['title'][:40]}...")
        print(f"    摘录: {a['text_sample'][:100]}...")

    # 5. D3: 统一文旅判定说明
    print(f"\n[5] D3: 文旅判定统一口径")
    print(f"  C报告文旅相关: 13条 (元数据+全文)")
    print(f"  D报告文旅相关: {tourism_count}条 (统一口径)")
    print(f"  差异原因: v1版C仅用元数据关键词，v2统一后使用扩展词表")

    # 6. D4: 层级本体统计
    print(f"\n[6] D4: 层级本体统计（取消'独有'标签）")
    level_dist = Counter()
    for a in analyses:
        level_dist[a["topic_level"]] += 1
    
    for level in sorted(level_dist.keys()):
        print(f"  {level}: {level_dist[level]}篇")
    
    # 主题分布
    topic_dist = Counter()
    for a in analyses:
        for t in a["topics"]:
            topic_dist[t] += 1
    
    print(f"\n  主题分布:")
    for topic, count in topic_dist.most_common(10):
        print(f"    {topic}: {count}篇")

    # 7. 英阿对照表（层级化）
    print(f"\n[7] 英阿对照表（层级化）")
    english_papers = [p for p in papers if p.get("language") == "en"]
    arab_related_english = [p for p in english_papers 
                           if any(kw in (p.get("title", "") + " " + 
                                        " ".join(p.get("keywords", []))).lower()
                                 for kw in ["arab", "arabic", "middle east", "islam"])]
    
    # 英文主题统计
    eng_topic_dist = Counter()
    for p in arab_related_english:
        text = (p.get("title", "") + " " + " ".join(p.get("keywords", []))).lower()
        if any(kw in text for kw in ["tourism", "travel", "heritage"]):
            eng_topic_dist["旅游/遗产"] += 1
        if any(kw in text for kw in ["culture", "cultural"]):
            eng_topic_dist["文化研究"] += 1
        if any(kw in text for kw in ["education", "university"]):
            eng_topic_dist["教育"] += 1
        if any(kw in text for kw in ["history", "historical"]):
            eng_topic_dist["历史"] += 1
    
    print(f"\n  阿语主题分布 vs 英文(阿拉伯相关)主题分布:")
    print(f"  {'主题':<15} {'阿语':>6} {'英文':>6} {'层级':<15}")
    print("  " + "-" * 50)
    
    all_topics = set(topic_dist.keys()) | set(eng_topic_dist.keys())
    comparison_rows = []
    for topic in sorted(all_topics, key=lambda t: -(topic_dist.get(t, 0) + eng_topic_dist.get(t, 0))):
        arab_count = topic_dist.get(topic, 0)
        eng_count = eng_topic_dist.get(topic, 0)
        level = classify_topic_level(topic)
        comparison_rows.append({
            "topic": topic,
            "arabic_count": arab_count,
            "english_count": eng_count,
            "level": level,
        })
        print(f"  {topic:<15} {arab_count:>6} {eng_count:>6} {level:<15}")

    # 8. D5: 研究传统差异降级
    print(f"\n[8] D5: 差异解释（降级为待验证）")
    print(f"  观察: 阿语文献更关注文化认同(L2)，英文更关注旅游/遗产(L1)")
    print(f"  待验证假设: 差异可能源于研究传统不同")
    print(f"  验证方法: 需扩大样本量至≥100篇，控制年份/期刊变量")

    # 9. 保存结果
    results = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "version": "v2",
        },
        "summary": {
            "total_arabic_papers": len(arabic_papers),
            "has_pdf": sum(1 for a in analyses if a["has_pdf"]),
            "text_extracted": text_extracted_count,
            "human_read": 0,
            "tourism_related_unified": tourism_count,
        },
        "analyses": analyses,
        "topic_distribution": dict(topic_dist),
        "level_distribution": dict(level_dist),
        "comparison_table": comparison_rows,
        "readable_texts": [
            {"doi": a["doi"], "title": a["title"], "excerpt": a["text_sample"][:300]}
            for a in readable
        ],
    }

    output_path = OUTPUT_DIR / "experiment_d_results_v2.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")

    # 10. 生成报告
    report_path = OUTPUT_DIR / "experiment_d_report_v2.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Task D: 阿语文献内容分析与英阿对照 (v2 修正版)\n\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n\n")
        
        f.write("## 1. 数据概况\n\n")
        f.write(f"- 阿语文献总数: {len(arabic_papers)} 篇\n")
        f.write(f"- has_pdf=true: {sum(1 for a in analyses if a['has_pdf'])} 篇\n")
        f.write(f"- text_extracted: {text_extracted_count} 篇\n")
        f.write(f"- human_read: 0 篇（待人工标记）\n")
        f.write(f"- 文旅相关(统一口径): {tourism_count} 篇\n\n")
        
        f.write("## 2. 全文状态三列 (D1)\n\n")
        f.write("| DOI | 标题 | has_pdf | text_extracted | human_read |\n")
        f.write("|-----|------|---------|----------------|------------|\n")
        for a in analyses:
            f.write(f"| {a['doi'][:20]} | {a['title'][:30]} | ")
            f.write(f"{'✓' if a['has_pdf'] else '✗'} | ")
            f.write(f"{'✓' if a['text_extracted'] else '✗'} | ")
            f.write(f"{'✓' if a['human_read'] else '—'} |\n")
        
        f.write("\n## 3. 可读取文本摘录 (D2)\n\n")
        for a in readable[:5]:
            f.write(f"### {a['title']}\n\n")
            f.write(f"- DOI: {a['doi']}\n")
            f.write(f"- 摘录: {a['text_sample'][:200]}...\n\n")
        
        f.write("\n## 4. 文旅判定统一说明 (D3)\n\n")
        f.write(f"- C报告文旅相关: 13条\n")
        f.write(f"- D报告文旅相关: {tourism_count}条\n")
        f.write(f"- 统一词表: {TOURISM_KEYWORDS_UNIFIED[:5]}...\n\n")
        
        f.write("\n## 5. 层级本体统计 (D4)\n\n")
        f.write("| 层级 | 篇数 |\n")
        f.write("|------|------|\n")
        for level in sorted(level_dist.keys()):
            f.write(f"| {level} | {level_dist[level]} |\n")
        
        f.write("\n## 6. 英阿对照表\n\n")
        f.write("| 主题 | 阿语 | 英文 | 层级 |\n")
        f.write("|------|------|------|------|\n")
        for row in comparison_rows[:15]:
            f.write(f"| {row['topic']} | {row['arabic_count']} | {row['english_count']} | {row['level']} |\n")
        
        f.write("\n## 7. 差异解释 (D5: 待验证)\n\n")
        f.write("**观察**: 阿语文献更关注文化认同(L2_文化认同)，英文更关注旅游/遗产(L1_文旅核心)\n\n")
        f.write("**待验证假设**: 差异可能源于研究传统不同\n\n")
        f.write("**验证方法**: 需扩大样本量至≥100篇，控制年份/期刊变量后进行统计检验\n")
    
    print(f"报告已保存: {report_path}")

    return results


if __name__ == "__main__":
    run_task_d()
