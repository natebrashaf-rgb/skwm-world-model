# -*- coding: utf-8 -*-
"""
交叉检验样本抽取脚本 v3（严格文旅筛选 + 8 篇）
==========================================
v2 的问题：全文匹配太宽，混入噪声论文（单细胞/量子物理/生物软件）。
v3 改进：
  1. 必须命中"强文旅词"才算数（Tourism/Heritage/Culture/Arab/旅游/文化/遗产...）
  2. 只抽 8 篇：主主题 3 篇 + 其他主题各 1 篇（共 5 个主题层）
  3. 固定种子可复现，记录命中词
输出：E:\大挑\产出\交叉检验_样本清单.csv
"""
import csv
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, r"E:\大挑\rail_deploy")
from match_topics import load_skwm_json, build_term_index, match_text  # noqa: E402

PDF_ROOT = r"E:\大挑\01_literature"
OUT_CSV = r"E:\大挑\产出\交叉检验_样本清单.csv"
TERMS = r"E:\大挑\03_knowledge_graph\core_terms.json"
PDF_TEXTS = r"E:\大挑\rail_deploy\data\pdf_texts.json"

# 强文旅词：命中了这些才算"文旅相关"（排除 Learning/University 这种宽泛词）
STRONG = [
    "tourism", "tourist", "destination", "travel", "hotel", "heritage",
    "culture", "cultural", "museum", "archaeolog", "arab", "arabic",
    "islam", "islamic", "muslim", "silk road", "silk", "pilgrim",
    "旅游", "游客", "文化", "遗产", "博物馆", "阿拉伯", "丝绸之路", "伊斯兰",
]

# 分层：主主题抽 3，其他 4 个主题各抽 1（共 7-8 篇）
LAYER_PLAN = [
    ("07_sino_arab_cultural_tourism/_PDF", 3),
    ("22_digital_tourism_extension/01_metaverse_tourism/_PDF", 1),
    ("23_sino_arab_civilization/01_belt_road_exchange/_PDF", 1),
    ("24_arab_tourism_communication/01_gulf_tourism_transition/_PDF", 1),
    ("25_cross_disciplinary/01_aigc_heritage/_PDF", 1),
]

# 1. 加载
print("[1/4] 加载词表 + PDF 全文...")
terms = load_skwm_json(TERMS)
single, multi, cn_map = build_term_index(terms)
pdf_texts = json.load(open(PDF_TEXTS, encoding="utf-8"))

# 2. 逐层筛选 + 随机抽
print("[2/4] 分层筛选（必须命中强文旅词）...")
random.seed(20260804)
picked = []
for layer, n in LAYER_PLAN:
    dirpath = os.path.join(PDF_ROOT, layer)
    if not os.path.isdir(dirpath):
        continue
    pdfs = [f for f in os.listdir(dirpath) if f.lower().endswith(".pdf")]
    # 只留命中强文旅词的
    good = []
    for f in pdfs:
        text = pdf_texts.get(f[:-4], "")
        if not text:
            continue
        hits = match_text(text, single, multi, cn_map)
        strong_hits = [h for h in hits if any(s in h.lower() for s in STRONG)]
        if strong_hits:
            good.append((f, strong_hits, os.path.getsize(os.path.join(dirpath, f))))
    print(f"    {layer.split('/')[0]}: {len(pdfs)} 篇 → 文旅 {len(good)} 篇")
    if not good:
        continue
    for f, hits, size in random.sample(good, min(n, len(good))):
        picked.append((layer.split("/")[0], f, hits, size))

# 3. 输出
print("[3/4] 生成清单...")
rows = []
for i, (topic, fname, hits, size) in enumerate(picked, 1):
    rows.append({
        "样本编号": f"S{i:02d}",
        "主题目录": topic,
        "文件名": fname,
        "命中主题": "、".join(hits[:5]),
        "大小KB": round(size / 1024),
    })
    print(f"  S{i:02d} [{topic}] {fname[:50]} 命中:{'、'.join(hits[:4])} ({round(size/1024)}KB)")

with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["样本编号", "主题目录", "文件名", "命中主题", "大小KB"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✓ 已保存: {OUT_CSV}（{len(rows)} 个样本）")
