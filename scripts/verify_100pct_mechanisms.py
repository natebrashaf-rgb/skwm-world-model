# -*- coding: utf-8 -*-
"""
「100%命中」机制验证脚本
========================
每条查询回答一个问题，验证 100% 是真实质量还是规则构造。
用法: py -3.14 verify_100pct_mechanisms.py
"""
import json
import re
from collections import Counter

ta = json.load(open(r"E:\大挑\rail_deploy\data\topic_assignments.json", encoding="utf-8"))
b1 = json.load(open(r"E:\大挑\rail_deploy\data\B1_文献主表.json", encoding="utf-8"))
b1_by_doi = {p.get("doi"): p for p in b1}
b1_by_title = {str(p.get("title", "")).strip().lower(): p for p in b1}

def get_paper(k, v):
    return b1_by_doi.get(k) or b1_by_title.get(str(v.get("title", "")).strip().lower()) or {}

print("=" * 70)
print("机制1: 二分法构造恒真（分类器把每个样本要么标文旅、要么标非文旅）")
print("-" * 70)
matched = sum(1 for v in ta.values() if isinstance(v, dict) and v.get("matched"))
non_t = sum(1 for v in ta.values() if isinstance(v, dict) and v.get("non_tourism"))
print(f"  文旅 {matched} + 非文旅 {non_t} = {matched + non_t} / 总 {len(ta)}")
print(f"  验证: 若 文旅+非文旅 == 总数，则'文旅命中率100%'是定义恒真，非测量结果")
print(f"  → {'⚠️ 构造恒真（100%是定义，不是质量证明）' if matched + non_t == len(ta) else '→ 有未分类，100%才有意义'}")

print()
print("=" * 70)
print("机制2: 宽泛救回（rescue=broad_match 的188篇靠什么词）")
print("-" * 70)
rescued = {k: v for k, v in ta.items() if isinstance(v, dict) and v.get("rescue") == "broad_match"}
words = Counter()
for k, v in rescued.items():
    ts = v.get("terms") or []
    words[ts[0] if ts else "?"] += 1
print(f"  救回 {len(rescued)} 篇, 依据词分布: {dict(words.most_common(8))}")
ce = sum(1 for k, v in rescued.items()
         if 'cultural exchange' in str(v.get('title', '')).lower())
print(f"  其中标题含'cultural exchange'(非中阿风险) : {ce} 篇")
print(f"  验证: 运行上方词分布，若大量命中'cultural exchange'/'tourism'等宽词 → 规则太宽")

print()
print("=" * 70)
print("机制3: 单命中低阈值（只命中1个词就进文旅）")
print("-" * 70)
normal = {k: v for k, v in ta.items() if isinstance(v, dict) and v.get("matched") and not v.get("rescue")}
one = Counter()
for k, v in normal.items():
    ts = v.get("terms") or []
    if len(ts) == 1:
        one[ts[0]] += 1
print(f"  单命中论文: {sum(one.values())} / {len(normal)}")
print(f"  可疑单命中词: {dict(sorted(one.items(), key=lambda x: -x[1])[:10])}")
print(f"  验证: 'Learning'/'Text Mining'/'Culture'等词若大量单命中 → 阈值过低")

print()
print("=" * 70)
print("机制4: 关键词字段污染（匹配用了当年批量贴的宽泛keywords）")
print("-" * 70)
kw_hits = 0
for k, v in normal.items():
    p = get_paper(k, v)
    ts = v.get("terms") or []
    kws = " ".join(str(x) for x in (p.get("keywords") or []))
    # 若命中词只出现在keywords不在标题 → 关键词污染
    for t in ts:
        if t.lower() not in str(v.get("title", "")).lower() and t.lower() in kws.lower():
            kw_hits += 1
            break
print(f"  命中词仅来自keywords字段(不在标题): {kw_hits} 篇")
print(f"  验证: 若数量大 → keywords是污染源（当年批量标签）")

print()
print("=" * 70)
print("机制5: 多标签允许重叠（一篇文章可命中多词，任一词命中即算文旅）")
print("-" * 70)
multi = sum(1 for v in normal.values() if len(v.get("terms") or []) >= 2)
print(f"  命中≥2词的论文: {multi} / {len(normal)}")
print(f"  验证: 多标签本身合理，但需确认任一命中词都强相关；单看命中数无法区分")

print()
print("=" * 70)
print("结论判定")
print("-" * 70)
red = []
if matched + non_t == len(ta):
    red.append("机制1构造恒真")
if sum(one.values()) > len(normal) * 0.3:
    red.append(f"机制3单命中占比过高({sum(one.values())/max(1,len(normal))*100:.0f}%)")
if kw_hits > 500:
    red.append(f"机制4关键词污染({kw_hits}篇)")
if red:
    print(f"  ⚠️ 100%由以下机制构造: {'、'.join(red)}")
    print(f"  → 结论: 100%不可写进论文，需人工抽样验证后改写为抽样准确率")
else:
    print(f"  → 100%暂时未被明显构造机制解释，但仍需人工抽样确认")
