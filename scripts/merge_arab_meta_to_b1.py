# -*- coding: utf-8 -*-
"""
阿拉伯文旅元数据 → B1主表 合并脚本
====================================
把 collect_arab_meta.py 采集的965篇阿拉伯文旅文献元数据，
合并进 B1_文献主表.json（去重：DOI/标题）。
输出：
  rail_deploy/data/B1_merged.json   合并后的完整主表
  rail_deploy/data/merge_report.json  合并报告
"""
import json
import re
import shutil

B1_PATH = r"E:\大挑\rail_deploy\data\B1_has_pdf.json"
META_PATH = r"E:\大挑\rail_deploy\data\arab_tourism_meta.json"
OUT_PATH = r"E:\大挑\rail_deploy\data\B1_merged.json"
REPORT_PATH = r"E:\大挑\rail_deploy\data\merge_report.json"


def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def norm_title(t):
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(t).lower())


def main():
    print("[1/4] 加载B1...", flush=True)
    b1 = json.load(open(B1_PATH, encoding="utf-8"))
    print(f"  B1: {len(b1)} 篇", flush=True)

    print("[2/4] 加载采集元数据...", flush=True)
    meta = json.load(open(META_PATH, encoding="utf-8"))
    print(f"  采集: {len(meta)} 篇", flush=True)

    b1_dois = {str(p.get("doi", "")).strip().lower() for p in b1}
    b1_titles = {norm_title(p.get("title", "")) for p in b1 if p.get("title")}

    added = []
    dup_doi = 0
    dup_title = 0
    for m in meta:
        doi = str(m.get("doi", "")).strip().lower()
        nt = norm_title(m.get("title", ""))
        if doi and doi in b1_dois:
            dup_doi += 1
            continue
        if nt and nt in b1_titles:
            dup_title += 1
            continue
        # 转成 B1 同格式
        paper = {
            "title": m.get("title", ""),
            "year": m.get("year"),
            "citations": m.get("citations", 0),
            "authors": ", ".join(m.get("authors") or []),
            "venue": m.get("venue", ""),
            "doi": m.get("doi", ""),
            "is_oa": False,
            "_source": "25_阿拉伯文旅新增/Crossref采集_" + (m.get("query_source") or "unknown"),
            "language": "en",
            "keywords": [],
            "normalized_keywords": [],
            "has_pdf": False,
            "crossref_link": m.get("link") or [],
        }
        b1.append(paper)
        b1_dois.add(doi)
        b1_titles.add(nt)
        added.append(paper)

    print(f"  新增: {len(added)} | DOI重复: {dup_doi} | 标题重复: {dup_title}", flush=True)

    print("[3/4] 保存合并表...", flush=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(b1, f, ensure_ascii=False, indent=1)

    print("[4/4] 保存报告...", flush=True)
    report = {
        "b1_before": len(b1) - len(added),
        "meta_total": len(meta),
        "added": len(added),
        "dup_doi": dup_doi,
        "dup_title": dup_title,
        "b1_after": len(b1),
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"\n=== 合并完成 ===")
    print(f"  合并前 B1: {report['b1_before']}")
    print(f"  新增: {len(added)}")
    print(f"  合并后 B1: {len(b1)}")
    print(f"  输出: {OUT_PATH}")


if __name__ == "__main__":
    main()
