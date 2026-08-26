# -*- coding: utf-8 -*-
"""
阿语匹配增量增强脚本（2026-08-27 重建入库）
============================================
背景红线：match_topics.py 禁止全量重跑（8/26 实测：纯标题+中英文词表，纯阿语标题无法匹配，
主题 1174→1115、阿语 25/27→12/27、non_tourism 3524→0，已回滚）。阿语匹配必须走本脚本的增量逻辑。

本脚本逻辑（复现 8/19-8/21 阿语增强的口径）：
  1. 只处理 language=ar 的阿语文献（当前 27 条），不改其他文献的匹配结果
  2. 用 core_terms.json 的 ar 词表（8,873 词）匹配：先匹配标题，标题未命中再用
     pdf_texts_arabic_20260819.json 全文匹配（有全文的文献）
  3. 输出增强结果（默认 dry-run 写到 _enhance_arabic_dryrun.json，不覆盖 topic_assignments.json；
     加 --apply 才合并写回主文件——默认不要用，红线要求增量且经人工确认）

用法：
  python3.14 scripts/enhance_arabic_assignments.py            # dry-run，输出对比报告
"""
import json, os, re, sys, datetime

DATA = r"E:\大挑\rail_deploy\data"
MASTER = os.path.join(DATA, "B1_文献主表.json")
TA = os.path.join(DATA, "topic_assignments.json")
CORE = os.path.join(DATA, "core_terms.json")
AR_TEXTS = os.path.join(DATA, "pdf_texts_arabic_20260819.json")
DRY_OUT = os.path.join(DATA, "_enhance_arabic_dryrun.json")

def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)

def pid_of(p):
    return str(p.get("doi") or p.get("title"))[:200]

def build_ar_index(terms):
    """ar 词表索引：ar 词 → (词条原词, domain)。domain=通用 的排除（与 match_topics 一致）。"""
    idx = {}
    for t in terms:
        dom = (t.get("domain") or "").strip()
        if dom == "通用":
            continue
        ar = (t.get("ar") or "").strip()
        en = (t.get("en") or "").strip()
        if ar and len(ar) >= 2:
            idx[ar] = (en or ar, dom)
    return idx

def match_ar(text, idx):
    hits = {}
    if not text:
        return hits
    for ar, (en, dom) in idx.items():
        if ar in text:
            hits[en] = dom
    return hits

def main():
    master = load_skwm_json(MASTER)
    ta = json.load(open(TA, encoding="utf-8"))
    terms = load_skwm_json(CORE)
    ar_texts = json.load(open(AR_TEXTS, encoding="utf-8")) if os.path.exists(AR_TEXTS) else {}

    ar_idx = build_ar_index(terms)
    print(f"ar 词表（排除通用后）: {len(ar_idx)} 词")

    ar_papers = [p for p in master if p.get("language") == "ar"]
    print(f"阿语文献: {len(ar_papers)} 条")

    changed = []
    for p in ar_papers:
        pid = pid_of(p)
        cur = ta.get(pid, {})
        title = p.get("title") or ""
        # 1) 标题匹配
        hits = match_ar(title, ar_idx)
        how = "title"
        # 2) 标题未命中（或命中少）时用全文（pdf_texts_arabic 的 key 是 DOI 或文件名）
        if len(hits) < 3:
            text = None
            doi = (p.get("doi") or "").strip()
            for k, v in ar_texts.items():
                if (doi and (doi in k or doi.replace("/", "_") in k)) or (title[:30] in k):
                    text = v
                    break
            if text:
                full_hits = match_ar(str(text), ar_idx)  # 全文全量匹配（现有产物 terms=255 为全文全量口径）
                if len(full_hits) > len(hits):
                    hits = full_hits
                    how = "fulltext"
        new_state = {
            "title": title,
            "year": p.get("year"),
            "matched": bool(hits),
            "terms": sorted(hits.keys()),
            "domains": sorted(set(hits.values())),
            "non_tourism": False,
            "_enhance": how,
        }
        old_state = {k: v for k, v in cur.items() if k not in ("_enhance",)}
        same = (old_state.get("matched") == new_state["matched"]
                and sorted(old_state.get("terms") or []) == new_state["terms"]
                and sorted(old_state.get("domains") or []) == new_state["domains"])
        changed.append({
            "pid": pid, "old_matched": bool(cur.get("matched")), "new_matched": new_state["matched"],
            "old_terms": len(cur.get("terms") or []), "new_terms": len(new_state["terms"]),
            "how": how, "same": same, "title": title[:40],
        })

    # dry-run 输出（不覆盖主文件）
    json.dump(changed, open(DRY_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_same = sum(1 for c in changed if c["same"])
    print(f"\n=== 对比报告（dry-run，未写回 topic_assignments.json）===")
    print(f"阿语 27 条: 与现有版本完全一致 {n_same}/27")
    for c in changed:
        flag = "同" if c["same"] else "不同!!"
        print(f"  [{flag}] {c['old_matched']}->{c['new_matched']} terms {c['old_terms']}->{c['new_terms']} ({c['how']}) {c['title']}")
    print(f"""
=== 重要说明（2026-08-27 审计发现）===
现有 topic_assignments 中阿语文献的 terms 为「单字符碎片伪匹配」：以 #15（沙漠旅游）为例，
terms=255 但 0/255 命中 core_terms 词表（ar 词表 8873 词），内容为拆开的单字母
（'س','ي','ا','ح','ة' = سياحة 的字母）并混入 '['、'"'、',' 等符号。
8/19-8/21 的阿语增强原始脚本已不存在，按其产物推断其逻辑存在按字符拆分缺陷。
本脚本改用完整阿语词匹配（增量），dry-run 结果与现有碎片版不同（如 #15：33 个真词 vs 255 个碎片）。
本脚本默认 dry-run 不写回主文件；如需修复碎片问题，须人工确认后 --apply 或手工合并（涉及数据变更，需用户拍板）。
dry-run 文件: {DRY_OUT}""")

if __name__ == "__main__":
    main()
