# -*- coding: utf-8 -*-
"""
阿语碎片修复合并脚本（2026-08-27，用户确认后执行）
=====================================================
配合 enhance_arabic_assignments.py v2（dry-run）的正式合并：
  1. 重算 27 条 language=ar 文献的新状态（hamza 归一化 + 标题/全文匹配，逻辑与 dry-run 完全一致）
  2. 与 topic_assignments.json 现状对比，只更新 same=False 的条目
  3. 类型规范化：matched/domains 写回布尔/列表；matched=true 去掉 non_tourism，false 补 non_tourism=True
  4. 保持文件格式：indent=1 + CRLF（防止幻影 diff）

用法：python3.14 scripts/apply_arabic_enhance.py
"""
import json, os, re, sys

DATA = r"E:\大挑\rail_deploy\data"
MASTER = os.path.join(DATA, "B1_文献主表.json")
TA = os.path.join(DATA, "topic_assignments.json")
CORE = os.path.join(DATA, "core_terms.json")
AR_TEXTS = os.path.join(DATA, "pdf_texts_arabic_20260819.json")

def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)

def pid_of(p):
    return str(p.get("doi") or p.get("title"))[:200]

def norm_ar(s):
    if not s:
        return ""
    return str(s).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")

def build_ar_index(terms):
    idx = {}
    for t in terms:
        dom = (t.get("domain") or "").strip()
        if dom == "通用":
            continue
        ar = (t.get("ar") or "").strip()
        en = (t.get("en") or "").strip()
        if ar and len(ar) >= 2:
            idx[norm_ar(ar)] = (en or ar, dom)
    return idx

def match_ar(text, idx):
    hits = {}
    if not text:
        return hits
    nt = norm_ar(text)
    for nk, (en, dom) in idx.items():
        if nk in nt:
            hits[en] = dom
    return hits

def compute_new_state(p, ar_idx, ar_texts):
    title = p.get("title") or ""
    hits = match_ar(title, ar_idx)
    how = "title"
    if len(hits) < 3:
        text = None
        doi = (p.get("doi") or "").strip()
        for k, v in ar_texts.items():
            if (doi and (doi in k or doi.replace("/", "_") in k)) or (norm_ar(title)[:30] in norm_ar(k)):
                text = v
                break
        if text:
            full_hits = match_ar(str(text), ar_idx)
            if len(full_hits) > len(hits):
                hits = full_hits
                how = "fulltext"
    return {
        "matched": bool(hits),
        "terms": sorted(hits.keys()),
        "domains": sorted(set(hits.values())),
        "how": how,
    }

def main():
    master = load_skwm_json(MASTER)
    ta = json.load(open(TA, encoding="utf-8"))
    terms = load_skwm_json(CORE)
    ar_texts = json.load(open(AR_TEXTS, encoding="utf-8")) if os.path.exists(AR_TEXTS) else {}

    ar_idx = build_ar_index(terms)
    print(f"ar 词表（排除通用+hamza归一化后）: {len(ar_idx)} 词")

    ar_papers = [p for p in master if p.get("language") == "ar"]
    print(f"阿语文献: {len(ar_papers)} 条\n")

    n_changed = 0
    print(f"{'#':>2} {'旧matched':>10} {'新matched':>10} {'旧词数':>5} {'新词数':>5} {'方式':<9} 标题")
    print("=" * 100)
    for i, p in enumerate(ar_papers, 1):
        pid = pid_of(p)
        cur = ta.get(pid, {})
        old_matched = bool(cur.get("matched"))
        old_terms = cur.get("terms") or []
        new_state = compute_new_state(p, ar_idx, ar_texts)
        same = (old_matched == new_state["matched"] and sorted(old_terms) == new_state["terms"])
        if same:
            continue
        # 写回
        ta[pid]["matched"] = new_state["matched"]
        ta[pid]["terms"] = new_state["terms"]
        ta[pid]["domains"] = new_state["domains"]
        ta[pid]["how"] = new_state["how"]
        if new_state["matched"]:
            ta[pid].pop("non_tourism", None)
        else:
            ta[pid]["non_tourism"] = True
        n_changed += 1
        print(f"{i:>2} {str(old_matched):>10} {str(new_state['matched']):>10} {len(old_terms):>5} {len(new_state['terms']):>5} {new_state['how']:<9} {str(p.get('title'))[:45]}")

    print("=" * 100)
    print(f"变更条目: {n_changed}/27")

    # 写回（保持 indent=1 + CRLF）
    with open(TA, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(ta, ensure_ascii=False, indent=1).replace("\n", "\r\n"))
    print(f"已写回: {TA}")

if __name__ == "__main__":
    main()
