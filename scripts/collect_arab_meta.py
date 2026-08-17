# -*- coding: utf-8 -*-
"""
阿拉伯文旅文献元数据采集 — Crossref + unpaywall
=================================================
目标：从 Crossref 批量拉取"阿拉伯文旅"相关文献元数据（标题/作者/年份/DOI/期刊），
     并用 unpaywall 查每篇的 OA PDF 链接，生成补下清单。
输出：
  E:\大挑\rail_deploy\data\arab_tourism_meta.json   全部元数据
  E:\大挑\rail_deploy\data\arab_tourism_pdf_queue.csv   PDF补下清单(能下的标记ok)
断点续传：进度存 E:\大挑\rail_deploy\data\arab_tourism_progress.json
"""
import json
import csv
import os
import re
import time
import urllib.request
import urllib.parse

OUT_DIR = r"E:\大挑\rail_deploy\data"
META_OUT = os.path.join(OUT_DIR, "arab_tourism_meta.json")
QUEUE_OUT = os.path.join(OUT_DIR, "arab_tourism_pdf_queue.csv")
PROGRESS = os.path.join(OUT_DIR, "arab_tourism_progress.json")
EMAIL = "test@bisu.edu.cn"
UA = "SKWM-Research/1.0 (mailto:" + EMAIL + ")"

# 检索主题：阿拉伯文旅的多个方向（中英混合，crossref 支持关键词）
QUERIES = [
    "cultural tourism arab",
    "arab tourism heritage",
    "sino arab tourism",
    "china arab cultural tourism",
    "heritage tourism saudi arabia",
    "cultural tourism egypt",
    "religious tourism mecca hajj",
    "gulf tourism cultural",
    "arab cultural heritage digital",
    "tourism uae cultural",
    "arabic cultural tourism hospitality",
    "silk road cultural tourism china arab",
    "halal tourism arab",
    "museum tourism arab heritage",
]

# 需要跳过的噪声期刊（医学/生物/纯技术）
SKIP_VENUE = re.compile(
    r"(cancer|oncol|clinical|medical|gene|genom|protein|cell|molecular|"
    r"biochem|biolog|pharma|drug|vaccine|nursing|surg|cardio|neuro|"
    r"physics|chemistry|materia|optical|quantum|engineering)", re.I
)


def fetch(url, timeout=25, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def load_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    return {"done_queries": [], "results": {}}


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False)


def main():
    pg = load_progress()
    for qi, query in enumerate(QUERIES):
        if query in pg["done_queries"]:
            print(f"[skip] {query} 已采集", flush=True)
            continue
        print(f"[{qi+1}/{len(QUERIES)}] 采集: {query}", flush=True)
        try:
            d = fetch(
                "https://api.crossref.org/works?query=" + urllib.parse.quote(query)
                + "&rows=100&select=DOI,title,author,issued,container-title,"
                + "publisher,is-referenced-by-count,link,type"
            )
        except Exception as e:
            print(f"  ! 采集失败: {e}", flush=True)
            continue

        items = d.get("message", {}).get("items", [])
        got = 0
        for it in items:
            doi = it.get("DOI", "")
            if not doi or doi in pg["results"]:
                continue
            title = (it.get("title") or [""])[0]
            venue = (it.get("container-title") or [""])[0]
            if SKIP_VENUE.search(venue):
                continue
            year = None
            issued = it.get("issued", {}).get("date-parts", [[None]])
            if issued and issued[0]:
                year = issued[0][0]
            authors = []
            for a in (it.get("author") or [])[:8]:
                nm = (a.get("given", "") + " " + a.get("family", "")).strip()
                if nm:
                    authors.append(nm)
            pg["results"][doi] = {
                "doi": doi,
                "title": title,
                "authors": authors,
                "year": year,
                "venue": venue,
                "publisher": it.get("publisher", ""),
                "citations": it.get("is-referenced-by-count", 0) or 0,
                "type": it.get("type", ""),
                "link": [l.get("URL", "") for l in (it.get("link") or [])],
                "query_source": query,
            }
            got += 1
        pg["done_queries"].append(query)
        save_progress(pg)
        print(f"  新增 {got} 篇 (累计 {len(pg['results'])})", flush=True)
        time.sleep(1)  # Crossref 礼貌间隔

    print(f"\n=== 元数据采集完成: {len(pg['results'])} 篇 ===", flush=True)

    # 去重（同标题保留1篇）
    by_title = {}
    for doi, r in pg["results"].items():
        t = (r["title"] or "").strip().lower()
        if t and t not in by_title:
            by_title[t] = r
    uniq = list(by_title.values())
    print(f"按标题去重后: {len(uniq)} 篇", flush=True)

    with open(META_OUT, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)

    # 用 unpaywall 查 OA PDF 链接
    print("\n=== unpaywall 查 OA PDF ===", flush=True)
    rows = []
    oa_count = 0
    for i, r in enumerate(uniq):
        try:
            up = fetch(
                "https://api.unpaywall.org/v2/" + urllib.parse.quote(r["doi"])
                + "?email=" + EMAIL
            )
            loc = up.get("best_oa_location") or {}
            pdf = loc.get("url_for_pdf") or ""
            if up.get("is_oa"):
                oa_count += 1
            rows.append({
                "doi": r["doi"],
                "title": r["title"],
                "year": r["year"],
                "venue": r["venue"],
                "is_oa": up.get("is_oa", False),
                "pdf_url": pdf,
                "download_status": "pending",
            })
        except Exception:
            rows.append({
                "doi": r["doi"],
                "title": r["title"],
                "year": r["year"],
                "venue": r["venue"],
                "is_oa": False,
                "pdf_url": "",
                "download_status": "unknown",
            })
        if (i + 1) % 20 == 0:
            print(f"  ...{i+1}/{len(uniq)} (OA {oa_count})", flush=True)
        time.sleep(0.6)

    with open(QUEUE_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [
            "doi", "title", "year", "venue", "is_oa", "pdf_url", "download_status"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 完成 ===")
    print(f"  元数据: {META_OUT} ({len(uniq)} 篇)")
    print(f"  PDF清单: {QUEUE_OUT} (OA {oa_count} 篇)")


if __name__ == "__main__":
    main()
