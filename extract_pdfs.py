# -*- coding: utf-8 -*-
"""
PDF 全文提取 — 后台跑
输入: E:\\大挑\\01_literature 下所有 _PDF 目录的 PDF
输出: E:\\大挑\\rail_deploy\\data\\pdf_texts.json
      {文件名(去扩展名): 前3页文本(截断5000字符)}
"""
import fitz
import glob
import json
import os
import sys

PDF_ROOTS = [
    r"E:\大挑\01_literature",
]
OUT_FILE = r"E:\大挑\rail_deploy\data\pdf_texts.json"
MAX_CHARS = 5000
MAX_PAGES = 3


def main():
    pdfs = []
    for root in PDF_ROOTS:
        pdfs.extend(glob.glob(os.path.join(root, "**", "*_PDF", "*.pdf"), recursive=True))
        pdfs.extend(glob.glob(os.path.join(root, "**", "*_pdf", "*.pdf"), recursive=True))
    # 去重
    pdfs = sorted(set(pdfs))
    print(f"发现 PDF: {len(pdfs)} 个", flush=True)

    result = {}
    ok = 0
    fail = 0
    empty = 0
    for i, path in enumerate(pdfs):
        base = os.path.splitext(os.path.basename(path))[0]
        try:
            doc = fitz.open(path)
            text_parts = []
            for pno in range(min(len(doc), MAX_PAGES)):
                text_parts.append(doc[pno].get_text())
            doc.close()
            text = "\n".join(text_parts).strip()
            if text:
                result[base] = text[:MAX_CHARS]
                ok += 1
            else:
                empty += 1
        except Exception as e:
            fail += 1
            result[base] = ""  # 提取失败标记为空
        if (i + 1) % 500 == 0:
            print(f"  进度 {i + 1}/{len(pdfs)} | 成功 {ok} | 空 {empty} | 失败 {fail}", flush=True)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"\n[完成] 成功 {ok} | 空文本 {empty} | 提取失败 {fail} | 总计 {len(pdfs)}")
    print(f"输出: {OUT_FILE}")


if __name__ == "__main__":
    main()
