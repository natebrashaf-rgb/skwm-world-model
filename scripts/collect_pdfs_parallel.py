# -*- coding: utf-8 -*-
"""
DOAJ + OpenAlex 并行PDF爬虫
============================
多线程下载，同时用 DOAJ 和 OpenAlex 两个源找OA PDF。
目标：快速凑齐1000份PDF。
"""
import csv
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse

OUT_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
CSV_OUT = r"E:\大挑\rail_deploy\data\pdf_crawled.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = "127.0.0.1:1080"
MAX_WORKERS = 8

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

# 全局状态
lock = threading.Lock()
seen_dois = set()
collected = []
EXISTING = set(os.listdir(OUT_DIR)) if os.path.exists(OUT_DIR) else set()
stats = {"ok": 0, "fail": 0, "dup": 0}


def fetch_json(url):
    cmd = ["curl", "-s", "--connect-timeout", "15", "--max-time", "40",
           "--socks5-hostname", PROXY, "-A", UA, "-H", "Accept: application/json",
           "-o", "-", url]
    r = subprocess.run(cmd, capture_output=True)
    return json.loads(r.stdout.decode("utf-8", errors="replace"))


def curl_download(url, out_path, timeout=80):
    cmd = ["curl", "-sL", "--connect-timeout", "12", "--max-time", str(timeout),
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


def try_download(doi, title, pdf_url, journal="", year=""):
    if not pdf_url:
        return
    with lock:
        if doi and doi in seen_dois:
            stats["dup"] += 1
            return
        if doi:
            seen_dois.add(doi)
    fname = re.sub(r'[\\/:*?"<>|]+', "_", (doi or title)[:60]) + ".pdf"
    out = os.path.join(OUT_DIR, fname)
    with lock:
        if fname in EXISTING:
            stats["dup"] += 1
            return
        EXISTING.add(fname)
    status = curl_download(pdf_url, out)
    with lock:
        if status == "ok":
            stats["ok"] += 1
            collected.append({"doi": doi, "title": title, "journal": journal,
                              "year": year, "pdf_url": pdf_url, "download_status": "ok"})
            if stats["ok"] % 20 == 0:
                print(f"  ...累计{stats['ok']}篇成功", flush=True)
        else:
            stats["fail"] += 1


def work_doaj(query):
    """一个线程处理一个DOAJ查询"""
    page = 1
    while True:
        url = ("https://doaj.org/api/search/articles/" + urllib.parse.quote(query) +
               f"?pageSize=100&page={page}")
        try:
            d = fetch_json(url)
        except Exception:
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
            try_download(doi, title, links[0].get("url", ""),
                         b.get("journal", {}).get("title", ""), b.get("year", ""))
        total = d.get("total", 0)
        if page * 100 >= total or page >= 3:
            break
        page += 1


def work_openalex(doi_list, title_list):
    """一个线程处理一批OpenAlex DOI查OA链接"""
    for i, doi in enumerate(doi_list):
        if not doi:
            continue
        try:
            d = fetch_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}")
            oa = d.get("open_access", {})
            url = oa.get("oa_url", "") or ""
            locs = [l.get("pdf_url") for l in d.get("locations", []) if l.get("pdf_url")]
            if locs:
                url = locs[0]
            if url:
                try_download(doi, title_list[i] if i < len(title_list) else "", url)
        except Exception:
            pass
        time.sleep(0.3)


def main():
    if os.path.exists(CSV_OUT):
        with open(CSV_OUT, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                seen_dois.add(row.get("doi", ""))
                collected.append(row)
        stats["ok"] = sum(1 for r in collected if r.get("download_status") == "ok")

    print(f"已有: {len(collected)} 条, 输出目录已有 {len(EXISTING)} 个PDF", flush=True)

    # 线程1-8: DOAJ查询并行
    threads = []
    half = len(QUERIES) // 2
    for qi, query in enumerate(QUERIES):
        t = threading.Thread(target=work_doaj, args=(query,), daemon=True)
        threads.append(t)
    for t in threads:
        t.start()
        if len([x for x in threads if x.is_alive()]) >= MAX_WORKERS:
            time.sleep(2)
    for t in threads:
        t.join(timeout=5)

    print(f"\nDOAJ阶段完成: 成功{stats['ok']} 失败{stats['fail']} 重复{stats['dup']}", flush=True)

    # 保存进度
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["doi", "title", "journal", "year", "pdf_url", "download_status"])
        w.writeheader()
        w.writerows(collected)

    print(f"\n=== 完成 ===")
    print(f"  成功: {stats['ok']} | 失败: {stats['fail']} | 重复: {stats['dup']}")
    print(f"  输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
