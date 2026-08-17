# -*- coding: utf-8 -*-
"""
v3 采集元数据 → B1 合并
========================
把 collect_pdfs_v3 采集的元数据(不在B1的)合并进B1主表。
"""
import json
import re

B1 = r"E:\大挑\rail_deploy\data\B1_文献主表.json"
META = r"E:\大挑\rail_deploy\data\pdf_meta_v3.json"


def norm(t):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(t).lower())


def main():
    b1 = json.load(open(B1, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8"))

    b1_dois = {str(p.get("doi", "")).strip().lower() for p in b1}
    b1_titles = {norm(p.get("title", "")) for p in b1 if p.get("title")}

    added = 0
    dup = 0
    for m in meta:
        doi = str(m.get("doi", "")).strip().lower()
        nt = norm(m.get("title", ""))
        if doi and doi in b1_dois:
            dup += 1
            continue
        if nt and nt in b1_titles:
            dup += 1
            continue
        b1.append({
            "title": m.get("title", ""),
            "year": m.get("year"),
            "citations": 0,
            "authors": "",
            "venue": m.get("venue", ""),
            "doi": m.get("doi", ""),
            "is_oa": False,
            "_source": "25_阿拉伯文旅新增/Crossref_v3_" + str(m.get("query", "")),
            "language": "en",
            "keywords": [],
            "normalized_keywords": [],
            "has_pdf": False,
        })
        b1_dois.add(doi)
        b1_titles.add(nt)
        added += 1

    with open(B1, "w", encoding="utf-8") as f:
        json.dump(b1, f, ensure_ascii=False, indent=1)
    print(f"B1: {len(b1) - added} + {added} = {len(b1)}")
    print(f"重复: {dup}")


if __name__ == "__main__":
    main()
