# -*- coding: utf-8 -*-
"""
PDF全文 → B1主表 匹配脚本
===========================
把 rail_deploy/data/pdf_texts.json 里的5520个PDF全文key，
匹配到 B1_文献主表.json 的论文，标记 has_pdf=true。
匹配方式：标题归一化（小写/去标点/去空格）后做子串/相等匹配。
输出：
  rail_deploy/data/B1_has_pdf.json   B1 + has_pdf 字段
  匹配报告打印
"""
import json
import re
import os

B1_PATH = r"E:\大挑\rail_deploy\data\B1_文献主表.json"
PDFTEXT_PATH = r"E:\大挑\rail_deploy\data\pdf_texts.json"
OUT_PATH = r"E:\大挑\rail_deploy\data\B1_has_pdf.json"


def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)


def norm_title(t):
    """归一化标题：小写、去标点/空格/控制字符"""
    t = str(t or "").lower()
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t, flags=re.UNICODE)
    return t.strip()


def extract_title_from_key(key):
    """从pdf_texts的key提取标题：去掉 '03_' / 'Arab_0000_' / 'Arab_' 前缀"""
    k = key
    m = re.match(r"^\d+_(.+)$", k)
    if m:
        return m.group(1)
    m = re.match(r"^Arab_\d+_(.+)$", k)
    if m:
        return m.group(1)
    m = re.match(r"^Arab_(.+)$", k)
    if m:
        return m.group(1)
    return k


def main():
    print("[1/4] 加载B1...", flush=True)
    papers = load_skwm_json(B1_PATH)
    print(f"  B1: {len(papers)} 篇", flush=True)

    print("[2/4] 加载pdf_texts...", flush=True)
    pt = json.load(open(PDFTEXT_PATH, encoding="utf-8"))
    print(f"  PDF全文: {len(pt)} 个", flush=True)

    # 建立 PDF key 的归一化标题索引
    pdf_index = {}  # norm_title -> [key...]
    for k in pt:
        t = extract_title_from_key(k)
        nt = norm_title(t)
        if nt:
            pdf_index.setdefault(nt, []).append(k)
    print(f"  可匹配标题: {len(pdf_index)}", flush=True)

    print("[3/4] 逐篇匹配...", flush=True)
    matched = 0
    matched_by = {"exact": 0, "contains": 0, "contained": 0}
    matched_keys = set()

    for p in papers:
        title = p.get("title") or ""
        nt = norm_title(title)
        if not nt:
            p["has_pdf"] = False
            continue
        # 1) 精确匹配
        if nt in pdf_index:
            p["has_pdf"] = True
            p["pdf_key"] = pdf_index[nt][0]
            matched_keys.add(pdf_index[nt][0])
            matched += 1
            matched_by["exact"] += 1
            continue
        # 2) 子串匹配：pdf标题包含论文标题（去前缀后标题可能带尾注）
        hit = None
        for pk, keys in pdf_index.items():
            if len(nt) >= 15 and nt in pk:
                hit = keys[0]
                break
        if hit:
            p["has_pdf"] = True
            p["pdf_key"] = hit
            matched_keys.add(hit)
            matched += 1
            matched_by["contains"] += 1
            continue
        # 3) 论文标题包含pdf标题
        for pk, keys in pdf_index.items():
            if len(pk) >= 15 and pk in nt:
                hit = keys[0]
                break
        if hit:
            p["has_pdf"] = True
            p["pdf_key"] = hit
            matched_keys.add(hit)
            matched += 1
            matched_by["contained"] += 1
            continue
        # 4) 前缀匹配：pdf标题被截断（如 '03_A new criterion for assessing discriminant va'）
        #    归一化后 pdf标题(pk) 是 B1标题(nt) 的子串 → 已由第3步覆盖
        #    这里补：pk 是 nt 的前缀（pdf标题完整但B1标题更长）
        hit = None
        for pk, keys in pdf_index.items():
            if len(pk) >= 20 and nt.startswith(pk):
                hit = keys[0]
                break
        if hit:
            p["has_pdf"] = True
            p["pdf_key"] = hit
            matched_keys.add(hit)
            matched += 1
            matched_by["prefix"] = matched_by.get("prefix", 0) + 1
            continue
        p["has_pdf"] = False

    print(f"  匹配成功: {matched} / {len(papers)}", flush=True)
    print(f"  匹配方式: {matched_by}", flush=True)

    print("[4/4] 保存...", flush=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=1)

    total_pdf = len(pt)
    print(f"\n=== 结果 ===")
    print(f"  B1总数: {len(papers)}")
    print(f"  有PDF全文: {matched}")
    print(f"  pdf_texts未匹配: {total_pdf - len(matched_keys)}")
    print(f"  输出: {OUT_PATH}")


if __name__ == "__main__":
    main()
