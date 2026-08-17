# -*- coding: utf-8 -*-
"""
第二轮PDF抢救：失败但域名可连的 → 解析HTML页面找真实PDF链接
============================================================
对 download_arab_pdfs_v2 失败的35篇：
  1. 先用浏览器UA+代理 GET 目标URL，若返回HTML则找 <a href="...pdf">
  2. 跟随重定向链
  3. 找到真实PDF地址后下载
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

os.makedirs(OUT_DIR, exist_ok=True)


def curl_get(url, ua=UA, timeout=60, follow=True):
    cmd = ["curl", "-sL" if follow else "-s",
           "--connect-timeout", "15", "--max-time", str(timeout),
           "--socks5-hostname", "127.0.0.1:1080", "-A", ua,
           "-e", "https://doi.org/", "-o", "-", "-w", "\n%{http_code}", url]
    r = subprocess.run(cmd, capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    code = out.rsplit("\n", 1)[-1].strip()
    body = out.rsplit("\n", 1)[0]
    return code, body


def find_pdf_links(html, base_url):
    links = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.I)
    links += re.findall(r'src=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.I)
    resolved = []
    for l in links:
        if l.startswith("http"):
            resolved.append(l)
        elif l.startswith("/"):
            from urllib.parse import urlparse
            p = urlparse(base_url)
            resolved.append(f"{p.scheme}://{p.netloc}{l}")
        else:
            resolved.append(l)
    return resolved


def download_pdf(url, out_path):
    cmd = ["curl", "-sL", "--connect-timeout", "15", "--max-time", "100",
           "--socks5-hostname", "127.0.0.1:1080", "-A", UA,
           "-e", "https://doi.org/", "-o", out_path, url]
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


def main():
    rows = list(csv.DictReader(open(QUEUE, encoding="utf-8-sig")))
    fails = [r for r in rows if r.get("download_status", "").startswith("fail")]
    print(f"待抢救: {len(fails)} 篇", flush=True)

    saved = 0
    still = 0
    for i, r in enumerate(fails):
        url = r["pdf_url"]
        if not url or "ekb" in url:
            still += 1
            continue
        fname = re.sub(r'[\\/:*?"<>|]+', "_", r['doi'].replace("/", "_") + "_" + (r['title'] or "")[:80]) + ".pdf"
        out = os.path.join(OUT_DIR, fname)

        # 1. 直接再试一次（可能网络抖动）
        st = download_pdf(url, out)
        if st == "ok":
            r["download_status"] = "ok"
            saved += 1
            print(f"  [{i+1}/{len(fails)}] 直接下载OK {url[:60]}", flush=True)
            continue

        # 2. 抓HTML找真实PDF
        code, body = curl_get(url)
        if not body or len(body) < 200:
            still += 1
            continue
        pdf_links = find_pdf_links(body, url)
        ok2 = False
        for pl in pdf_links[:5]:
            st2 = download_pdf(pl, out)
            if st2 == "ok":
                r["download_status"] = "ok"
                saved += 1
                ok2 = True
                print(f"  [{i+1}/{len(fails)}] HTML解析下载OK {pl[:60]}", flush=True)
                break
            if os.path.exists(out):
                os.remove(out)
        if not ok2:
            r["download_status"] = "fail:rescue"
            still += 1
            print(f"  [{i+1}/{len(fails)}] 抢救失败 {url[:60]}", flush=True)
        time.sleep(1)

    with open(QUEUE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 抢救完成 ===")
    print(f"  抢救成功: {saved} | 仍失败: {still}")


if __name__ == "__main__":
    main()
