# -*- coding: utf-8 -*-
"""
新爬PDF → B1主表 精确匹配（标题/DOI双通道）
==============================================
把 25_阿拉伯文旅新增/_PDF 的PDF对应到B1，标记has_pdf。
"""
import json
import os
import re

B1 = r"E:\大挑\rail_deploy\data\B1_文献主表.json"
PDF_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"


def norm(t):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(t).lower())


def main():
    b1 = json.load(open(B1, encoding="utf-8"))
    b1_norm = {}
    for p in b1:
        t = p.get("title") or ""
        nt = norm(t)
        if nt:
            b1_norm.setdefault(nt, p)

    pdfs = os.listdir(PDF_DIR)
    matched = 0
    unmatched = []
    for f in pdfs:
        if not f.endswith(".pdf"):
            continue
        # 文件名 → 标题：去DOI前缀
        title_part = re.sub(r"^(10\.\d+/[^_]+(?:_[0-9][^_]*)*_|10\.\d+_[^_]+_|doi_?)", "", f)
        title_part = title_part.replace(".pdf", "")
        title_part = re.sub(r"_+", " ", title_part)
        nt = norm(title_part)
        # 精确匹配
        hit = b1_norm.get(nt)
        # 前缀匹配（文件名可能截断）
        if not hit and len(nt) > 20:
            for bnt, p in b1_norm.items():
                if nt[:35] == bnt[:35] or (nt[:30] in bnt and len(nt) > 25):
                    hit = p
                    break
        if hit:
            hit["has_pdf"] = True
            hit["pdf_key"] = f
            matched += 1
        else:
            unmatched.append(f)

    with open(B1, "w", encoding="utf-8") as f:
        json.dump(b1, f, ensure_ascii=False, indent=1)

    total_pdf = sum(1 for p in b1 if p.get("has_pdf"))
    print(f"新PDF匹配: {matched} / {len(pdfs)}")
    print(f"B1总计has_pdf: {total_pdf}")
    print(f"未匹配: {len(unmatched)}")
    for u in unmatched[:8]:
        print(f"  - {u[:70]}")


if __name__ == "__main__":
    main()
