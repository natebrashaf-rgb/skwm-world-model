# -*- coding: utf-8 -*-
"""
PDF 全文补充匹配
1. PDF 文件名 ↔ 主表 title 对应（规范化模糊匹配）
2. 对标题未命中(matched=false)的论文，用 PDF 全文再做受控词匹配
3. 合并结果回 topic_assignments.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match_topics import load_skwm_json, build_term_index, match_text  # noqa: E402

DATA_DIR = r"E:\大挑\rail_deploy\data"
MAIN_TABLE = os.path.join(DATA_DIR, "B1_文献主表.json")
ASSIGNMENTS = os.path.join(DATA_DIR, "topic_assignments.json")
PDF_TEXTS = os.path.join(DATA_DIR, "pdf_texts.json")
CORE_TERMS = r"E:\大挑\03_knowledge_graph\core_terms.json"


def normalize_title(t):
    t = (t or "").lower()
    t = re.sub(r"^[\d_\.\-\s]+", "", t)
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def main():
    print("[1/4] 加载数据...")
    papers = load_skwm_json(MAIN_TABLE)
    papers = [p for p in papers if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    assigns = json.load(open(ASSIGNMENTS, encoding="utf-8"))
    pdf_texts = json.load(open(PDF_TEXTS, encoding="utf-8"))
    print(f"    论文 {len(papers)} | 匹配结果 {len(assigns)} | PDF文本 {len(pdf_texts)}")

    # 词表索引（和 match_topics 一致）
    print("[2/4] 构建词表索引...")
    terms = load_skwm_json(CORE_TERMS)
    single, multi, cn_map = build_term_index(terms)
    print(f"    英文单词 {len(single)} | 短语 {len(multi)} | 中文 {len(cn_map)}")

    # PDF 文件名 → 主表论文
    print("[3/4] PDF 文件名 ↔ 主表 对应...")
    norm_map = {}  # 规范化标题 -> pid
    for p in papers:
        pid = str(p.get("doi") or p.get("title"))[:200]
        nt = normalize_title(p.get("title"))
        if nt:
            norm_map.setdefault(nt, pid)
    matched_pdf = 0
    for fname in pdf_texts:
        nf = normalize_title(fname)
        if not nf:
            continue
        if nf in norm_map:
            matched_pdf += 1
    print(f"    精确匹配 {matched_pdf}")

    # 模糊匹配（文件名是标题前缀等）
    pdf_to_pid = {}
    norm_keys = sorted(norm_map.keys())
    for fname, ftext in pdf_texts.items():
        if not ftext:
            continue
        nf = normalize_title(fname)
        if not nf:
            continue
        pid = norm_map.get(nf)
        if not pid:
            # 文件名前30字符匹配标题前缀
            pre30 = nf[:30]
            for nt in norm_keys:
                if pre30 and len(nt) >= 20 and nt.startswith(pre30):
                    pid = norm_map[nt]
                    break
        if pid:
            pdf_to_pid[fname] = pid
    print(f"    PDF↔主表 共匹配 {len(pdf_to_pid)} / {len(pdf_texts)}")

    # 全文匹配：只对标题未命中的论文
    print("[4/4] 全文匹配（标题未命中论文）...")
    newly_matched = 0
    updated = 0
    for fname, pid in pdf_to_pid.items():
        if pid not in assigns:
            continue
        v = assigns[pid]
        if v.get("matched"):
            continue  # 标题已命中，不重复
        text = pdf_texts.get(fname) or ""
        if len(text) < 200:
            continue  # 全文太少，跳过
        # 截取前 2500 字符（标题+摘要+引言区域）做匹配
        sample = text[:2500]
        if re.search(r"[\u4e00-\u9fff]", sample):
            hits = match_text(sample, {}, {}, cn_map)
        else:
            hits = match_text(sample, single, multi, {})
        if hits:
            v["matched"] = True
            v["terms"] = sorted(set(v.get("terms", [])) | set(hits.keys()))
            v["domains"] = sorted(set(v.get("domains", [])) | set(hits.values()))
            v["via"] = "pdf_fulltext"
            updated += 1
            newly_matched += 1

    # 保存
    with open(ASSIGNMENTS, "w", encoding="utf-8") as f:
        json.dump(assigns, f, ensure_ascii=False, indent=1)

    total = len(assigns)
    hit = sum(1 for v in assigns.values() if v.get("matched"))
    print(f"\n全文补充命中: {newly_matched} 篇")
    print(f"最终: 命中 {hit} ({hit / total * 100:.1f}%) | 未命中 {total - hit} ({100 - hit / total * 100:.1f}%)")
    print(f"[完成] {ASSIGNMENTS}")


if __name__ == "__main__":
    main()
