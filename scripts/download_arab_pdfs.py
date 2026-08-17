# -*- coding: utf-8 -*-
"""
阿拉伯文旅文献 PDF 一键补下脚本
================================
前提：网络环境能访问国外站点时运行（当前校园网被墙，先存清单，换网后跑这个）
输入：arab_tourism_pdf_queue.csv（965篇，其中407篇OA有PDF链接）
输出：E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF\ 下所有能下到的PDF
      下载状态写回 csv（ok / fail）
用法：
  py -3.14 download_arab_pdfs.py            # 下载所有OA的
  py -3.14 download_arab_pdfs.py --retry    # 重试失败的
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

QUEUE = r"E:\大挑\rail_deploy\data\arab_tourism_pdf_queue.csv"
OUT_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

os.makedirs(OUT_DIR, exist_ok=True)


def sanitize(title):
    return re.sub(r'[\\/:*?"<>|]+', "_", title or "")[:80]


import subprocess


def download_pdf(url, out_path, timeout=120):
    """用 curl 走 socks5 代理下载（urllib 不支持 socks5）"""
    cmd = [
        "curl", "-sL",
        "--connect-timeout", "15",
        "--max-time", str(timeout),
        "--socks5-hostname", "127.0.0.1:1080",
        "-A", UA,
        "-o", out_path,
        url,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise ValueError(f"curl exit {r.returncode}: {r.stderr.decode(errors='replace')[:100]}")
    if not os.path.exists(out_path):
        raise ValueError("无输出文件")
    with open(out_path, "rb") as f:
        head = f.read(4)
        size = os.path.getsize(out_path)
    if size < 1000 or head != b"%PDF":
        os.remove(out_path)
        raise ValueError(f"非PDF内容: {size} bytes")
    return size


def main():
    retry_only = "--retry" in sys.argv
    rows = list(csv.DictReader(open(QUEUE, encoding="utf-8-sig")))
    print(f"清单: {len(rows)} 篇")

    ok = fail = skip = 0
    for i, r in enumerate(rows):
        if r.get("download_status") == "ok" and not retry_only:
            skip += 1
            continue
        if r.get("is_oa") != "True" or not r.get("pdf_url"):
            skip += 1
            continue
        url = r["pdf_url"]
        fname = f"{r['doi'].replace('/', '_')}_{sanitize(r['title'])}.pdf"
        out = os.path.join(OUT_DIR, fname)
        try:
            n = download_pdf(url, out)
            r["download_status"] = "ok"
            ok += 1
            if ok % 20 == 0:
                print(f"  ...{ok} 篇成功", flush=True)
        except Exception as e:
            r["download_status"] = "fail:" + str(e)[:50]
            fail += 1
        time.sleep(1)  # 礼貌间隔

    # 写回状态
    with open(QUEUE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== 完成 ===")
    print(f"  成功: {ok} | 失败: {fail} | 跳过: {skip}")
    print(f"  PDF目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
