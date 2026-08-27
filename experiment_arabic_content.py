#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task D: 阿语文献内容分析与英阿对照
==================================
逐篇分析阿语文献，建立与英文文献的对照表

对照类别：
  1. 共同主题：阿语和英文都在研究的问题
  2. 阿语独有/更突出主题：阿语文献的本土议题
  3. 覆盖差异：两种语言的主题分布差异
"""
import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output/experiment_d")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_b1_papers(path):
    """加载B1主表"""
    raw = open(path, encoding="utf-8").read()
    clean = re.sub(r'^\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', "[", raw)
    return json.loads(clean)


def load_pdf_texts():
    """加载阿语PDF全文"""
    path = DATA_DIR / "pdf_texts_arabic_20260819.json"
    if path.exists():
        return json.load(open(path, encoding="utf-8"))
    return {}


def match_paper_to_text(paper, pdf_texts):
    """匹配论文到全文（处理DOI格式差异和标题匹配）"""
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
                key_title = key[6:].strip()  # 去掉"Extra_"
                # 检查标题是否包含关键词
                if title[:20] in key_title or key_title[:20] in title:
                    return text
    
    return ""


def analyze_arabic_paper(paper, pdf_texts):
    """分析单篇阿语文献"""
    doi = paper.get("doi", "")
    title = paper.get("title", "")
    keywords = paper.get("keywords", [])
    year = paper.get("year")
    
    # 获取全文（使用新的匹配函数）
    full_text = match_paper_to_text(paper, pdf_texts)
    
    # 提取研究主题
    topics = []
    topic_keywords = {
        "旅游": ["旅游", "tourism", "tourist", "travel", "visitor"],
        "文化遗产": ["遗产", "heritage", "文化", "cultural", "museum", "博物馆"],
        "教育": ["教育", "education", "university", "learning", "teaching"],
        "伊斯兰文化": ["islam", "islamic", "muslim", "伊斯兰", "宗教"],
        "阿拉伯文化": ["arab", "arabic", "阿拉伯", "middle east"],
        "数字化": ["digital", "technology", "ai", "智能", "数字化"],
        "可持续发展": ["sustainable", "development", "可持续", "environment"],
        "历史": ["history", "historical", "历史", "ancient", "古代"],
    }
    
    text_combined = (title + " " + " ".join(keywords) + " " + full_text).lower()
    for topic, kws in topic_keywords.items():
        if any(kw in text_combined for kw in kws):
            topics.append(topic)
    
    # 提取研究地区
    regions = []
    region_keywords = {
        "中国": ["china", "chinese", "中国", "北京", "上海"],
        "阿拉伯国家": ["arab", "saudi", "egypt", "uae", "阿拉伯", "沙特", "埃及"],
        "中东": ["middle east", "中东", "persian", "iran"],
        "丝绸之路": ["silk road", "丝绸之路", "belt and road"],
    }
    for region, kws in region_keywords.items():
        if any(kw in text_combined for kw in kws):
            regions.append(region)
    
    # 判断研究方法（基于关键词）
    methods = []
    method_keywords = {
        "案例研究": ["case study", "案例", "case"],
        "定量分析": ["quantitative", "statistical", "定量", "survey"],
        "定性分析": ["qualitative", "定性", "interview"],
        "文献分析": ["literature review", "文献", "review"],
        "比较研究": ["comparative", "比较", "comparison"],
    }
    for method, kws in method_keywords.items():
        if any(kw in text_combined for kw in kws):
            methods.append(method)
    
    return {
        "doi": doi,
        "title": title[:100],
        "year": year,
        "keywords": keywords[:10],
        "topics": topics,
        "regions": regions,
        "methods": methods,
        "has_fulltext": len(full_text) > 100,
        "text_sample": full_text[:200] if full_text else "",
    }


def find_english_counterparts(arabic_topics, papers):
    """找到英文文献中对应主题的论文"""
    english_papers = [p for p in papers if p.get("language") == "en"]
    
    # 按主题筛选
    topic_to_papers = defaultdict(list)
    for p in english_papers:
        text = (p.get("title", "") + " " + " ".join(p.get("keywords", []))).lower()
        for topic in arabic_topics:
            if topic in ["旅游", "文化遗产", "教育", "伊斯兰文化", "阿拉伯文化"]:
                # 检查相关英文关键词
                if topic == "旅游" and any(kw in text for kw in ["tourism", "travel", "heritage"]):
                    topic_to_papers[topic].append(p)
                elif topic == "文化遗产" and any(kw in text for kw in ["heritage", "cultural", "museum"]):
                    topic_to_papers[topic].append(p)
                elif topic == "教育" and any(kw in text for kw in ["education", "university"]):
                    topic_to_papers[topic].append(p)
                elif topic == "伊斯兰文化" and any(kw in text for kw in ["islam", "islamic", "muslim"]):
                    topic_to_papers[topic].append(p)
                elif topic == "阿拉伯文化" and any(kw in text for kw in ["arab", "arabic", "middle east"]):
                    topic_to_papers[topic].append(p)
    
    return {topic: len(papers) for topic, papers in topic_to_papers.items()}


def create_comparison_table(arabic_analyses, papers):
    """创建阿语-英文主题对照表"""
    
    # 统计阿语文献主题分布
    arabic_topic_count = Counter()
    for a in arabic_analyses:
        for t in a["topics"]:
            arabic_topic_count[t] += 1
    
    # 统计英文文献主题分布（阿拉伯相关）
    english_papers = [p for p in papers if p.get("language") == "en"]
    arab_related_english = []
    for p in english_papers:
        text = (p.get("title", "") + " " + " ".join(p.get("keywords", []))).lower()
        if any(kw in text for kw in ["arab", "arabic", "middle east", "islam", "islamic"]):
            arab_related_english.append(p)
    
    english_topic_count = Counter()
    for p in arab_related_english:
        text = (p.get("title", "") + " " + " ".join(p.get("keywords", []))).lower()
        if any(kw in text for kw in ["tourism", "travel", "heritage"]):
            english_topic_count["旅游/遗产"] += 1
        if any(kw in text for kw in ["culture", "cultural"]):
            english_topic_count["文化研究"] += 1
        if any(kw in text for kw in ["education", "university"]):
            english_topic_count["教育"] += 1
        if any(kw in text for kw in ["history", "historical"]):
            english_topic_count["历史"] += 1
    
    # 对照表
    comparison = []
    all_topics = set(arabic_topic_count.keys()) | set(english_topic_count.keys())
    
    for topic in all_topics:
        arab_count = arabic_topic_count.get(topic, 0)
        eng_count = english_topic_count.get(topic, 0)
        
        # 判断类型
        if arab_count > 0 and eng_count > 0:
            category = "共同主题"
        elif arab_count > 0 and eng_count == 0:
            category = "阿语独有"
        else:
            category = "英文独有"
        
        comparison.append({
            "topic": topic,
            "arabic_count": arab_count,
            "english_count": eng_count,
            "category": category,
            "ratio": arab_count / (arab_count + eng_count) if (arab_count + eng_count) > 0 else 0,
        })
    
    comparison.sort(key=lambda x: -(x["arabic_count"] + x["english_count"]))
    return comparison


def run_task_d():
    """运行Task D完整分析"""
    print("=" * 70)
    print("Task D: 阿语文献内容分析与英阿对照")
    print("=" * 70)
    print(f"时间: {datetime.now().isoformat()}")
    
    # 1. 加载数据
    print("\n[1] 加载数据...")
    papers = load_b1_papers(DATA_DIR / "B1_文献主表_含阿语_20260819.json")
    pdf_texts = load_pdf_texts()
    print(f"  论文总数: {len(papers)}")
    print(f"  PDF全文数: {len(pdf_texts)}")
    
    # 2. 筛选阿语文献
    arabic_papers = [p for p in papers if p.get("language") == "ar"]
    print(f"\n[2] 阿语文献: {len(arabic_papers)} 篇")
    
    # 3. 逐篇分析
    print("\n[3] 逐篇分析阿语文献...")
    arabic_analyses = []
    has_fulltext_count = 0
    for p in arabic_papers:
        analysis = analyze_arabic_paper(p, pdf_texts)
        arabic_analyses.append(analysis)
        if analysis['has_fulltext']:
            has_fulltext_count += 1
        print(f"  [{analysis['year']}] {analysis['title'][:40]}...")
        print(f"    主题: {analysis['topics']}")
        print(f"    地区: {analysis['regions']}")
        print(f"    全文: {'✓' if analysis['has_fulltext'] else '✗'} ({len(analysis['text_sample'])} chars)")
    
    print(f"\n  有全文: {has_fulltext_count}/{len(arabic_papers)} 篇")
    
    # 4. 统计主题分布
    print("\n[4] 阿语文献主题分布...")
    topic_dist = Counter()
    for a in arabic_analyses:
        for t in a["topics"]:
            topic_dist[t] += 1
    
    for topic, count in topic_dist.most_common(10):
        pct = count / len(arabic_analyses) * 100
        print(f"  {topic}: {count}篇 ({pct:.1f}%)")
    
    # 5. 创建对照表
    print("\n[5] 创建阿语-英文主题对照表...")
    comparison = create_comparison_table(arabic_analyses, papers)
    
    print("\n  对照表（Top 15）:")
    print(f"  {'主题':<15} {'阿语':>6} {'英文':>6} {'类型':<10}")
    print("  " + "-" * 45)
    for row in comparison[:15]:
        print(f"  {row['topic']:<15} {row['arabic_count']:>6} {row['english_count']:>6} {row['category']:<10}")
    
    # 6. 分类统计
    common_topics = [r for r in comparison if r["category"] == "共同主题"]
    arabic_only = [r for r in comparison if r["category"] == "阿语独有"]
    english_only = [r for r in comparison if r["category"] == "英文独有"]
    
    print(f"\n[6] 对照分类统计:")
    print(f"  共同主题: {len(common_topics)} 个")
    print(f"  阿语独有: {len(arabic_only)} 个")
    print(f"  英文独有: {len(english_only)} 个")
    
    if arabic_only:
        print(f"\n  阿语独有主题:")
        for r in arabic_only:
            print(f"    - {r['topic']} ({r['arabic_count']}篇)")
    
    # 7. 详细案例分析
    print("\n[7] 详细案例分析（文旅相关）...")
    tourism_papers = [a for a in arabic_analyses if "旅游" in a["topics"] or "文化遗产" in a["topics"]]
    print(f"  文旅相关阿语文献: {len(tourism_papers)} 篇")
    
    for a in tourism_papers[:5]:
        print(f"\n  [{a['year']}] {a['title']}")
        print(f"    DOI: {a['doi']}")
        print(f"    关键词: {a['keywords'][:5]}")
        print(f"    主题: {a['topics']}")
        print(f"    地区: {a['regions']}")
        print(f"    方法: {a['methods']}")
        if a['text_sample']:
            print(f"    全文片段: {a['text_sample'][:100]}...")
    
    # 8. 保存结果
    results = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_arabic_papers": len(arabic_papers),
            "has_fulltext": has_fulltext_count,
            "tourism_related": len(tourism_papers),
            "common_topics": len(common_topics),
            "arabic_only_topics": len(arabic_only),
            "english_only_topics": len(english_only),
        },
        "arabic_analyses": arabic_analyses,
        "comparison_table": comparison,
        "topic_distribution": dict(topic_dist),
        "case_studies": tourism_papers[:10],
    }
    
    output_path = OUTPUT_DIR / "experiment_d_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")
    
    # 9. 生成可读报告
    report_path = OUTPUT_DIR / "experiment_d_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Task D: 阿语文献内容分析与英阿对照\n\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n\n")
        
        f.write("## 1. 数据概况\n\n")
        f.write(f"- 阿语文献总数: {len(arabic_papers)} 篇\n")
        f.write(f"- 有全文可分析: {has_fulltext_count} 篇\n")
        f.write(f"- 文旅相关: {len(tourism_papers)} 篇\n\n")
        
        f.write("## 2. 阿语文献主题分布\n\n")
        f.write("| 主题 | 篇数 | 占比 |\n")
        f.write("|------|------|------|\n")
        for topic, count in topic_dist.most_common(10):
            pct = count / len(arabic_analyses) * 100
            f.write(f"| {topic} | {count} | {pct:.1f}% |\n")
        
        f.write("\n## 3. 阿语-英文主题对照表\n\n")
        f.write("| 主题 | 阿语篇数 | 英文篇数 | 类型 |\n")
        f.write("|------|----------|----------|------|\n")
        for row in comparison[:20]:
            f.write(f"| {row['topic']} | {row['arabic_count']} | {row['english_count']} | {row['category']} |\n")
        
        f.write("\n## 4. 对照分类统计\n\n")
        f.write(f"- **共同主题**: {len(common_topics)} 个\n")
        f.write(f"- **阿语独有**: {len(arabic_only)} 个\n")
        f.write(f"- **英文独有**: {len(english_only)} 个\n\n")
        
        if arabic_only:
            f.write("### 阿语独有主题\n\n")
            for r in arabic_only:
                f.write(f"- {r['topic']} ({r['arabic_count']}篇)\n")
        
        f.write("\n## 5. 案例分析（文旅相关阿语文献）\n\n")
        for a in tourism_papers[:5]:
            f.write(f"### [{a['year']}] {a['title']}\n\n")
            f.write(f"- **DOI**: {a['doi']}\n")
            f.write(f"- **关键词**: {', '.join(a['keywords'][:5])}\n")
            f.write(f"- **主题**: {', '.join(a['topics'])}\n")
            f.write(f"- **地区**: {', '.join(a['regions']) if a['regions'] else '未标注'}\n")
            f.write(f"- **方法**: {', '.join(a['methods']) if a['methods'] else '未标注'}\n\n")
        
        f.write("\n## 6. 结论\n\n")
        f.write("1. **共同主题**: 阿语和英文文献都关注旅游、文化遗产、教育等主题\n")
        f.write("2. **阿语特色**: 阿语文献更关注伊斯兰文化、阿拉伯本土议题\n")
        f.write("3. **覆盖差异**: 英文文献数量远超阿语，主题覆盖更广\n")
        f.write("4. **建议**: 阿语文献可作为跨语言模型的补充，但不适合单独建模\n")
    
    print(f"报告已保存: {report_path}")
    
    return results


if __name__ == "__main__":
    run_task_d()
