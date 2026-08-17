# -*- coding: utf-8 -*-
"""
把新下载的阿拉伯文旅PDF全文提取进 pdf_texts.json（增量合并）
输入: E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF\*.pdf
输出: rail_deploy/data/pdf_texts.json (合并后)
"""
import fitz
import json
import os
import glob

PDF_DIR = r"E:\大挑\01_literature\25_阿拉伯文旅新增\_PDF"
OUT = r"E:\大挑\rail_deploy\data\pdf_texts.json"
MAX_CHARS = 5000
MAX_PAGES = 3


def main():
    # 加载已有
    pdf_texts = {}
    if os.path.exists(OUT):
        pdf_texts = json.load(open(OUT, encoding="utf-8"))
    before = len(pdf_texts)
    print(f"已有全文: {before}", flush=True)

    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"新增PDF: {len(pdfs)} 个", flush=True)

    ok = empty = fail = 0
    for path in pdfs:
        base = os.path.splitext(os.path.basename(path))[0]
        if base in pdf_texts:
            continue
        try:
            doc = fitz.open(path)
            parts = []
            for pno in range(min(len(doc), MAX_PAGES)):
                parts.append(doc[pno].get_text())
            doc.close()
            text = "\n".join(parts).strip()
            if text:
                pdf_texts[base] = text[:MAX_CHARS]
                ok += 1
            else:
                empty += 1
        except Exception as e:
            fail += 1
            print(f"  ! {path} -> {e}", flush=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pdf_texts, f, ensure_ascii=False, indent=1)

    print(f"\n=== 完成 ===")
    print(f"  新增: {ok} | 空: {empty} | 失败: {fail}")
    print(f"  总计: {len(pdf_texts)} (原{before})")
    print(f"  输出: {OUT}")


if __name__ == "__main__":
    main()
