# -*- coding: utf-8 -*-
"""
大规模采集器 v3 — Crossref 5000+ 篇 + OpenAlex OA链接 + 多线程下载
====================================================================
目标：把阿拉伯文旅文献采集量扩到5000+篇，OA PDF 全下载。
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
CSV_OUT = r"E:\大挑\rail_deploy\data\pdf_crawled_v3.csv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PROXY = "127.0.0.1:1080"

# 扩大查询集：每个方向 3-4 个变体
QUERIES = [
    # 阿拉伯文旅核心
    "arab tourism", "arabic tourism", "arab cultural tourism", "arab heritage tourism",
    "saudi arabia tourism", "egypt tourism cultural", "uae tourism", "qatar tourism",
    "oman tourism", "jordan tourism", "morocco tourism", "tunisia tourism",
    "gulf tourism", "middle east tourism",
    # 宗教/朝觐
    "hajj pilgrimage", "religious tourism islam", "islamic tourism", "halal tourism",
    "umrah tourism", "pilgrimage tourism",
    # 中阿关系
    "sino arab", "china arab cooperation", "chinese arab relations", "belt and road tourism",
    "silk road heritage", "maritime silk road", "china tourism arab",
    # 文旅分支
    "cultural heritage tourism", "heritage tourism digital", "museum tourism",
    "archaeological tourism", "dark tourism", "ecotourism desert",
    "gastronomy tourism arab", "food tourism arab", "festival tourism",
    "souq market tourism", "medina tourism", "desert tourism",
    "luxury tourism arab", "business tourism gulf", "medical tourism arab",
    "sports tourism arab", "film tourism arab", "wedding tourism",
    # 数字文旅
    "digital heritage", "virtual reality tourism", "smart tourism arab",
    "augmented reality heritage", "social media tourism arab",
    # 中国游客
    "chinese tourists", "outbound tourism china", "chinese visitors arab",
    "china outbound travel", "chinese travel behavior",
    # 阿拉伯游客
    "arab tourists", "arab travelers", "arab visitors europe",
]

# 已知的医学噪声关键词（标题含这些跳过）
SKIP_TITLE = re.compile(
    r"(cancer|tumor|clinical|medical\b|patient|disease|protein|gene|genom|"
    r"drug|vaccine|therapy|diagnos|nursing|cardiac|neurolog|bacteri|virol|"
    r"immun|pharma|molecular|cell\b|dental|pediatr|obstetr|psychiatr|"
    r"quantum|physics|chemistry|gromacs|hitran)", re.I
)

lock = threading.Lock()
seen_dois = set()
collected = []
EXISTING = set(os.listdir(OUT_DIR)) if os.path.exists(OUT_DIR) else set()
stats = {"ok": 0, "fail": 0, "dup": 0, "meta": 0}
meta_all = {}  # doi -> meta


def fetch_json(url, timeout=40):
    cmd = ["curl", "-s", "--connect-timeout", "15", "--max-time", str(timeout),
           "--socks5-hostname", PROXY, "-A", UA,
           "-H", "Accept: application/json", "-o", "-", url]
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
    if not pdf_url or not title:
        return
    if SKIP_TITLE.search(title):
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
                print(f"  ...PDF累计{stats['ok']}篇", flush=True)
        else:
            stats["fail"] += 1


def work_crossref(query):
    """Crossref 采集元数据，只记下 doi+title，交给后续OpenAlex找OA"""
    try:
        d = fetch_json(
            "https://api.crossref.org/works?query=" + urllib.parse.quote(query)
            + "&rows=100&select=DOI,title,issued,container-title,type")
    except Exception:
        return
    for it in d.get("message", {}).get("items", []):
        doi = it.get("DOI", "")
        title = (it.get("title") or [""])[0]
        if not doi or not title or SKIP_TITLE.search(title):
            continue
        year = None
        issued = it.get("issued", {}).get("date-parts", [[None]])
        if issued and issued[0]:
            year = issued[0][0]
        venue = (it.get("container-title") or [""])[0]
        with lock:
            if doi not in meta_all:
                meta_all[doi] = {"doi": doi, "title": title, "year": year,
                                 "venue": venue, "query": query}


def work_openalex_batch(doi_titles):
    """用OpenAlex批量查OA链接（每次并发几个）"""
    for doi, title, year, venue in doi_titles:
        try:
            d = fetch_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}", timeout=25)
            oa = d.get("open_access", {})
            url = oa.get("oa_url", "") or ""
            locs = [l.get("pdf_url") for l in d.get("locations", []) if l.get("pdf_url")]
            if locs:
                url = locs[0]
            if url:
                try_download(doi, title, url, venue, year)
        except Exception:
            pass
        time.sleep(0.2)


def main():
    print(f"输出目录已有 {len(EXISTING)} 个PDF", flush=True)

    # 阶段1: Crossref 并行采集元数据
    threads = []
    for q in QUERIES:
        t = threading.Thread(target=work_crossref, args=(q,), daemon=True)
        threads.append(t)
    for t in threads:
        t.start()
        if sum(1 for x in threads if x.is_alive()) >= 6:
            time.sleep(1.5)
    for t in threads:
        t.join(timeout=60)
    print(f"Crossref 采集元数据: {len(meta_all)} 篇(去重前)", flush=True)

    # 去重
    uniq = {}
    for doi, m in meta_all.items():
        t = m["title"].strip().lower()
        if t and t not in uniq:
            uniq[t] = m
    metas = list(uniq.values())
    print(f"去重后: {len(metas)} 篇", flush=True)

    # 阶段2: OpenAlex 查OA + 下载（多线程）
    batch = []
    for m in metas:
        batch.append((m["doi"], m["title"], m["year"], m["venue"]))
    # 分批交给线程
    N = 8
    chunks = [batch[i::N] for i in range(N)]
    t2s = []
    for ch in chunks:
        t = threading.Thread(target=work_openalex_batch, args=(ch,), daemon=True)
        t2s.append(t)
    for t in t2s:
        t.start()
    for t in t2s:
        t.join(timeout=600)
    print(f"OpenAlex OA查询+下载完成", flush=True)

    # 保存
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["doi", "title", "journal", "year", "pdf_url", "download_status"])
        w.writeheader()
        w.writerows(collected)
    with open(r"E:\大挑\rail_deploy\data\pdf_meta_v3.json", "w", encoding="utf-8") as f:
        json.dump(metas, f, ensure_ascii=False, indent=1)

    print(f"\n=== 完成 ===")
    print(f"  元数据: {len(metas)}")
    print(f"  PDF成功: {stats['ok']} | 失败: {stats['fail']} | 重复: {stats['dup']}")
    print(f"  目录PDF: {len(os.listdir(OUT_DIR))}")


if __name__ == "__main__":
    main()
