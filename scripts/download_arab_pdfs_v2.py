# -*- coding: utf-8 -*-
"""
阿拉伯文旅 PDF 批量下载器 v2 — 多源 + 代理 + 分域重试
======================================================
策略：
  1. 只下非ekb源的（ekb站连不上，单独跳过记录）
  2. 走 socks5 代理 (127.0.0.1:1080)
  3. 每个PDF尝试2次，MDPI等403的换浏览器头
  4. 下载状态写回csv（ok / fail:原因）
输出：E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF\
"""
import csv
import json
import os
import re
import subprocess
import sys
import time

QUEUE = r"E:\大挑\rail_deploy\data\arab_tourism_pdf_queue.csv"
OUT_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA2 = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

os.makedirs(OUT_DIR, exist_ok=True)

# 已知完全连不上的域名（跳过不浪费时间）
BLOCKED_HOSTS = {
    "jaauth.journals.ekb.eg", "ijecth.journals.ekb.eg", "ijhth.journals.ekb.eg",
    "sjs.journals.ekb.eg", "ijhms.journals.ekb.eg", "ijthsx.journals.ekb.eg",
    "ijaf.journals.ekb.eg", "ijmsac.journals.ekb.eg", "www.mdpi.com",
    "journals.smartinsight.id", "api.taylorfrancis.com", "www.preprints.org",
    "www.sciencedirect.com",
}


def sanitize(title):
    return re.sub(r'[\\/:*?"<>|]+', "_", title or "")[:80]


def host_of(url):
    try:
        return url.split("/")[2]
    except Exception:
        return "?"


def curl_download(url, out_path, ua, timeout=100):
    cmd = [
        "curl", "-sL",
        "--connect-timeout", "15",
        "--max-time", str(timeout),
        "--socks5-hostname", "127.0.0.1:1080",
        "-A", ua,
        "-e", "https://doi.org/",
        "-o", out_path,
        url,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        return f"curl{abs(r.returncode)}"
    if not os.path.exists(out_path):
        return "noout"
    with open(out_path, "rb") as f:
        head = f.read(4)
    size = os.path.getsize(out_path)
    if size < 1000 or head != b"%PDF":
        os.remove(out_path)
        return f"notpdf{size}"
    return "ok"


def main():
    retry_only = "--retry" in sys.argv
    rows = list(csv.DictReader(open(QUEUE, encoding="utf-8-sig")))
    print(f"清单: {len(rows)} 篇", flush=True)

    # 统计
    total_oa = sum(1 for r in rows if r.get("is_oa") == "True" and r.get("pdf_url"))
    blocked = sum(1 for r in rows if r.get("is_oa") == "True" and host_of(r.get("pdf_url","")) in BLOCKED_HOSTS)
    print(f"OA带链接: {total_oa} | 已知封锁源: {blocked} | 可尝试: {total_oa - blocked}", flush=True)

    ok = fail = skip = 0
    failed_detail = {}

    for i, r in enumerate(rows):
        if r.get("is_oa") != "True" or not r.get("pdf_url"):
            skip += 1
            continue
        if r.get("download_status") == "ok" and not retry_only:
            skip += 1
            continue

        url = r["pdf_url"]
        host = host_of(url)
        if host in BLOCKED_HOSTS:
            if r.get("download_status") != "ok":
                r["download_status"] = "skip:blocked_host"
            skip += 1
            continue

        fname = f"{r['doi'].replace('/', '_')}_{sanitize(r['title'])}.pdf"
        out = os.path.join(OUT_DIR, fname)

        # 尝试2次，换不同UA
        status = None
        for ua in (UA, UA2):
            status = curl_download(url, out, ua)
            if status == "ok":
                break
            if os.path.exists(out):
                os.remove(out)
            time.sleep(1)

        if status == "ok":
            r["download_status"] = "ok"
            ok += 1
            if ok % 10 == 0:
                print(f"  ...{ok} 篇成功 ({fail} 失败)", flush=True)
        else:
            r["download_status"] = "fail:" + status
            failed_detail[status] = failed_detail.get(status, 0) + 1
            fail += 1

        # 每50篇保存一次进度
        if (ok + fail) % 50 == 0:
            with open(QUEUE, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

    # 最终写回
    with open(QUEUE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 完成 ===")
    print(f"  成功: {ok} | 失败: {fail} | 跳过: {skip}")
    print(f"  失败原因: {failed_detail}")
    print(f"  PDF目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
