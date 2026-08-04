# -*- coding: utf-8 -*-
"""
SKWM 受控词表匹配脚本 v2.0
原理：用 core_terms.json 的 9014 个领域词（排除"通用"类），去每篇论文的
    标题+关键词里做词边界匹配，命中才算主题。
    匹配不上的论文，诚实标记 matched=false，绝不兜底成"通用"。
输出：topic_assignments.json（每篇论文的命中词+领域）+ 统计报告（stdout）
"""
import json
import re
import sys
from collections import Counter

CORE_TERMS = r"E:\大挑\03_knowledge_graph\core_terms.json"
MAIN_TABLE = r"E:\大挑\rail_deploy\data\B1_文献主表.json"
OUT_FILE = r"E:\大挑\rail_deploy\data\topic_assignments.json"


def load_skwm_json(path):
    """兼容带 _wm 伪键的 JSON"""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


# 黑名单：词表里被错分领域的通用词（如 Guidelines→旅游 是错的）
# 这些词单独出现时是"套话/通用词"，不代表中阿文旅主题
BLACKLIST = {
    "guidelines", "guide", "standard", "standards",
    "algorithm", "algorithms", "criterion", "criteria",
    "review", "survey", "assessment", "evaluation",
    "framework", "approach", "approaches",
    "perspective", "perspectives", "challenge", "challenges",
    "opportunity", "opportunities", "implication", "implications",
    "evidence", "analysis", "analyses", "role", "roles",
    "impact", "impacts", "effect", "effects", "factor", "factors",
    "determinant", "determinants", "management", "practice", "practices",
    "status", "progress", "experience", "experiences", "case", "cases",
    "commentary", "editorial", "letter", "note", "notes",
    "preface", "introduction", "conclusion", "summary", "overview",
    "outlook", "future", "direction", "directions", "need", "needs",
    "gap", "gaps", "trend", "trends", "pattern", "patterns",
    "dimension", "dimensions", "aspect", "aspects", "feature", "features",
    "issue", "issues", "problem", "problems", "question", "questions",
    "answer", "answers", "context", "contexts", "setting", "settings",
    "field", "fields", "development", "developments",
    # 领域外噪声词（医学/生化/物理/天文等，词表里被乱分领域）
    "nanoparticles", "nanoparticle", "heart", "failure", "cognition",
    "statistics", "statistical", "modelling", "modeling", "simulation",
    "simulations", "molecular", "dynamics", "protein", "proteins",
    "gene", "genes", "genome", "genomic", "genetic", "genetics",
    "cancer", "tumor", "tumour", "clinical", "drug", "drugs",
    "cell", "cells", "cellular", "biological", "bioinformatics",
    "chemistry", "physics", "astronomy", "astrophysics", "mathematics",
    "mathematical", "ethics", "ethical", "psychology", "psychological",
    "diagnosis", "diagnostic", "treatment", "therapy", "disease",
    "diseases", "patient", "patients", "syndrome", "vaccine",
    "magnetic", "resonance", "spectroscopy", "chromatography",
    "microbiome", "genomewide", "exosome", "exosomes",
}


def build_term_index(terms):
    """词表 → 匹配索引。排除 domain=通用 的词（避免'通用'标签复活）。"""
    single = {}   # 单token英文词: 小写词 -> (原词, 领域)
    multi = {}    # 多token英文短语: 'a b' -> (原词, 领域)，最多3个token
    cn_map = {}   # 中文词 -> (原词, 领域)
    for t in terms:
        dom = (t.get("domain") or "").strip()
        if dom == "通用":
            continue
        en = (t.get("en") or "").strip()
        cn = (t.get("cn") or "").strip()
        low = en.lower()
        if len(low) >= 3 and low not in BLACKLIST:
            if " " in low:
                toks = low.split()
                # 短语规则：≤3个token，且任何token都不在黑名单
                if len(toks) <= 3 and not any(tok in BLACKLIST for tok in toks):
                    multi[low] = (en, dom)
            else:
                single[low] = (en, dom)
        if cn and cn not in {"指南", "标准", "管理", "全球", "研究", "分析",
                             "评估", "综述", "方法", "模型", "框架", "发展",
                             "影响", "因素", "挑战", "机遇", "趋势", "现状",
                             "进展", "经验", "案例", "问题", "作用", "建议",
                             "对策", "路径", "策略", "模式", "机制", "体系",
                             "建设", "应用", "实践", "服务", "创新", "纳米",
                             "心脏", "肿瘤", "癌症", "基因", "临床", "药物",
                             "细胞", "分子", "患者", "疾病", "治疗", "诊断",
                             "数学", "物理", "化学", "天文", "统计", "仿真",
                             "模拟", "伦理", "心理"}:
            cn_map[cn] = (cn, dom)
    return single, multi, cn_map


def match_text(text, single, multi, cn_map):
    """
    对一段文本做受控词匹配，返回 {命中词: 领域}
    方法：把英文文本切成 token 集合，直接查字典（O(词数)，比逐词正则快几十倍）
    """
    if not text:
        return {}
    hits = {}
    # 1) 中文词：直接子串匹配（中文无空格，只能子串查）
    for cn, (term, dom) in cn_map.items():
        if cn in text:
            hits[term] = dom
    # 2) 英文：token 化后查字典
    low = text.lower()
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", low)
    if not tokens:
        return hits
    # 单 token 词：集合交集
    for tok in set(tokens):
        if tok in single:
            hits[single[tok][0]] = single[tok][1]
    # 多 token 短语：滑动窗口查（2~3 个 token 的短语）
    for i in range(len(tokens)):
        for n in (2, 3):
            if i + n <= len(tokens):
                phrase = " ".join(tokens[i:i + n])
                if phrase in multi:
                    hits[multi[phrase][0]] = multi[phrase][1]
    return hits


def main():
    print("[1/3] 加载词表...")
    terms = load_skwm_json(CORE_TERMS)
    single, multi, cn_map = build_term_index(terms)
    print(f"    领域词: 英文单词 {len(single)} | 英文短语 {len(multi)} | 中文 {len(cn_map)}")

    print("[2/3] 加载文献主表...")
    papers = load_skwm_json(MAIN_TABLE)
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    print(f"    论文: {len(papers)}")

    print("[3/3] 逐篇匹配...")
    result = {}
    matched_count = 0
    domain_paper_count = Counter()
    term_usage = Counter()
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        title = p.get("title") or ""
        # 只用标题匹配：keywords 是当年批量贴的宽泛标签，等于噪声，弃用
        # 中文标题 → 中文词匹配；英文标题 → 英文词匹配（防误标）
        if re.search(r"[\u4e00-\u9fff]", title):
            hits = match_text(title, {}, {}, cn_map)
        else:
            hits = match_text(title, single, multi, {})
        terms_list = sorted(hits.keys())
        domains = sorted(set(hits.values()))
        if hits:
            matched_count += 1
        for d in set(domains):
            domain_paper_count[d] += 1
        for t in terms_list:
            term_usage[t] += 1
        result[pid] = {
            "title": title,
            "year": p.get("year"),
            "matched": bool(hits),
            "terms": terms_list,
            "domains": domains,
        }

    # 保存
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # 统计报告
    total = len(result)
    print("\n" + "=" * 50)
    print(f"论文总数: {total}")
    print(f"命中至少1个领域词: {matched_count} ({matched_count / total * 100:.1f}%)")
    print(f"未命中(非领域论文): {total - matched_count} ({(total - matched_count) / total * 100:.1f}%)")
    print("\n=== 领域分布（论文数） ===")
    for d, c in domain_paper_count.most_common():
        print(f"  {d}: {c}")
    print("\n=== 高频命中术语 Top 20 ===")
    for t, c in term_usage.most_common(20):
        print(f"  {t}: {c} 篇")
    print(f"\n[完成] 结果已保存: {OUT_FILE}")


if __name__ == "__main__":
    main()
