# -*- coding: utf-8 -*-
"""
SemanticScholar 补充PDF采集
============================
从B1里挑"已命中主题但没有PDF"的文旅文献，用SemanticScholar查OA链接并下载。
"""
import json
import os
import re
import subprocess
import threading
import time

B1 = r"E:\大挑\rail_deploy\data\B1_文献主表.json"
OUT_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = "127.0.0.1:1080"

lock = threading.Lock()
EXISTING = set(os.listdir(OUT_DIR)) if os.path.exists(OUT_DIR) else set()
stats = {"ok": 0, "fail": 0, "no_oa": 0}


def fetch_json(url, timeout=25):
    cmd = ["curl", "-s", "--connect-timeout", "10", "--max-time", str(timeout),
           "--socks5-hostname", PROXY, "-A", UA, "-o", "-", url]
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


def worker(items):
    for doi, title in items:
        try:
            d = fetch_json(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,title")
            pdf = (d.get("openAccessPdf") or {}).get("url", "")
            if not pdf:
                with lock:
                    stats["no_oa"] += 1
                continue
            fname = re.sub(r'[\\/:*?"<>|]+', "_", (doi or title)[:60]) + ".pdf"
            out = os.path.join(OUT_DIR, fname)
            with lock:
                if fname in EXISTING:
                    stats["no_oa"] += 1
                    continue
                EXISTING.add(fname)
            status = curl_download(pdf, out)
            with lock:
                if status == "ok":
                    stats["ok"] += 1
                    if stats["ok"] % 20 == 0:
                        print(f"  ...SS累计{stats['ok']}篇", flush=True)
                else:
                    stats["fail"] += 1
        except Exception:
            with lock:
                stats["fail"] += 1
        time.sleep(1.2)  # SS限流保护


def main():
    b1 = json.load(open(B1, encoding="utf-8"))
    # 挑：有DOI、无PDF、标题非噪声的
    candidates = []
    seen = set()
    for p in b1:
        doi = str(p.get("doi", "")).strip()
        if not doi or doi.startswith("10.17119"):  # 跳过伪DOI
            continue
        if p.get("has_pdf"):
            continue
        title = str(p.get("title", ""))
        if not title:
            continue
        if doi in seen:
            continue
        seen.add(doi)
        candidates.append((doi, title))
    print(f"候选(有DOI无PDF): {len(candidates)}", flush=True)

    # 分批8线程
    N = 8
    chunks = [candidates[i::N] for i in range(N)]
    threads = []
    for ch in chunks:
        t = threading.Thread(target=worker, args=(ch,), daemon=True)
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=900)

    print(f"\n=== SS采集完成 ===")
    print(f"  成功: {stats['ok']} | 失败: {stats['fail']} | 无OA: {stats['no_oa']}")
    print(f"  目录PDF: {len(os.listdir(OUT_DIR))}")


if __name__ == "__main__":
    main()
