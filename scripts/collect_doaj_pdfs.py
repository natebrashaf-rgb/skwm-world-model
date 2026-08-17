# -*- coding: utf-8 -*-
"""
DOAJ 批量采集 — 中阿文旅相关开放获取PDF
=========================================
用多组关键词搜索 DOAJ，提取每篇的 fulltext PDF 链接并下载。
目标：凑够1000份PDF（当前已有89份）
输出：E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF\
      E:\大挑\rail_deploy\data\doaj_collected.csv
"""
import csv
import json
import os
import re
import subprocess
import time
import urllib.request
import urllib.parse

OUT_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
CSV_OUT = r"E:\大挑\rail_deploy\data\doaj_collected.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = "127.0.0.1:1080"

# 中阿文旅各方向关键词（DOAJ搜索）
QUERIES = [
    "cultural tourism", "heritage tourism", "arab tourism", "sino arab",
    "silk road tourism", "china tourism cultural", "islamic tourism",
    "halal tourism", "religious tourism hajj", "museum tourism",
    "destination marketing arab", "cultural heritage arab",
    "tourist behavior china", "hospitality arab", "travel culture arab",
    "digital heritage tourism", "archaeology tourism arab",
    "tourism sustainability arab", "eco tourism arab", "gastronomy tourism",
    "festival tourism cultural", "rural tourism heritage",
    "cultural exchange china arab", "arabic culture tourism",
]

# 已有PDF文件名（避免重复下载）
EXISTING = set()
if os.path.exists(OUT_DIR):
    EXISTING = set(os.listdir(OUT_DIR))


def curl_download(url, out_path, timeout=90):
    cmd = ["curl", "-sL", "--connect-timeout", "15", "--max-time", str(timeout),
           "--socks5-hostname", PROXY, "-A", UA, "-o", out_path, url]
    subprocess.run(cmd, capture_output=True)
    if not os.path.exists(out_path):
        return "noout"
    with open(out_path, "rb") as f:
        head = f.read(4)
    size = os.path.getsize(out_path)
    if size < 1000 or head != b"%PDF":
        os.remove(out_path)
        return f"notpdf{size}"
    return "ok"


def fetch_json(url):
    """用 curl 走 socks5 代理请求 JSON"""
    cmd = ["curl", "-s", "--connect-timeout", "15", "--max-time", "40",
           "--socks5-hostname", PROXY, "-A", UA, "-H", "Accept: application/json",
           "-o", "-", url]
    r = subprocess.run(cmd, capture_output=True)
    return json.loads(r.stdout.decode("utf-8", errors="replace"))


def main():
    collected = []
    ok = fail = dup = 0
    # 已有csv则续传
    seen_dois = set()
    if os.path.exists(CSV_OUT):
        with open(CSV_OUT, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                seen_dois.add(row.get("doi", ""))
                collected.append(row)

    for qi, query in enumerate(QUERIES):
        page = 1
        while True:
            url = ("https://doaj.org/api/search/articles/" +
                   urllib.parse.quote(query) +
                   f"?pageSize=100&page={page}")
            try:
                d = fetch_json(url)
            except Exception as e:
                print(f"  ! 查询失败 {query} p{page}: {str(e)[:50]}", flush=True)
                break
            results = d.get("results", [])
            if not results:
                break
            for r in results:
                b = r.get("bibjson", {})
                title = b.get("title", "")
                links = [l for l in (b.get("link") or []) if l.get("content_type") == "pdf"]
                if not links:
                    continue
                doi = ""
                for ident in (b.get("identifier") or []):
                    if ident.get("type") == "doi":
                        doi = ident.get("id", "")
                if doi and doi in seen_dois:
                    dup += 1
                    continue
                pdf_url = links[0].get("url", "")
                # 下载
                fname = re.sub(r'[\\/:*?"<>|]+', "_", (doi or title)[:60]) + ".pdf"
                out = os.path.join(OUT_DIR, fname)
                if fname in EXISTING:
                    dup += 1
                    continue
                status = curl_download(pdf_url, out)
                if status == "ok":
                    ok += 1
                    row = {
                        "doi": doi, "title": title,
                        "journal": b.get("journal", {}).get("title", ""),
                        "year": b.get("year", ""),
                        "pdf_url": pdf_url, "download_status": "ok",
                    }
                    collected.append(row)
                    seen_dois.add(doi)
                    EXISTING.add(fname)
                    if ok % 20 == 0:
                        print(f"  ...{ok} 篇成功", flush=True)
                else:
                    fail += 1
                time.sleep(0.5)
            total = d.get("total", 0)
            if page * 100 >= total or page >= 3:
                break
            page += 1
        print(f"[{qi+1}/{len(QUERIES)}] {query}: 累计成功{ok}", flush=True)

    # 保存csv
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["doi", "title", "journal", "year", "pdf_url", "download_status"])
        w.writeheader()
        w.writerows(collected)

    print(f"\n=== DOAJ采集完成 ===")
    print(f"  成功: {ok} | 失败: {fail} | 重复: {dup}")
    print(f"  总计: {len(collected)}")
    print(f"  输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
