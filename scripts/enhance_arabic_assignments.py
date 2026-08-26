# -*- coding: utf-8 -*-
"""
阿语匹配增量增强脚本 v2（2026-08-27 dry-run，不覆盖主文件）
============================================================
红线：match_topics.py 禁止全量重跑。阿语匹配只能走本脚本增量。

v2 变更：
  1. 标题匹配加 hamza 归一化（أ/إ/آ→ا，文本与词表两侧同时归一化）
  2. dry-run 输出对比表：每条阿语文献 旧terms数 vs 新真词数
  3. 从 27 条里随机抽 10 条（固定种子 20260827），新旧 terms 并排打印，供人工确认
  4. 硬约束：默认 dry-run，绝不写 topic_assignments.json（合并需用户确认后另行执行）

用法：
  python3.14 scripts/enhance_arabic_assignments.py   # dry-run v2
"""
import json, os, re, sys, random

DATA = r"E:\大挑\rail_deploy\data"
MASTER = os.path.join(DATA, "B1_文献主表.json")
TA = os.path.join(DATA, "topic_assignments.json")
CORE = os.path.join(DATA, "core_terms.json")
AR_TEXTS = os.path.join(DATA, "pdf_texts_arabic_20260819.json")
DRY_OUT = os.path.join(DATA, "_enhance_arabic_dryrun.json")
SEED = 20260827

def load_skwm_json(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)

def pid_of(p):
    return str(p.get("doi") or p.get("title"))[:200]

def norm_ar(s):
    """hamza 归一化：أ/إ/آ→ا（v2 新增，文本与词表两侧同用）"""
    if not s:
        return ""
    return str(s).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")

def build_ar_index(terms):
    """ar 词表索引（norm 后）：norm词 → (原词, domain)。domain=通用 排除。"""
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

def main():
    master = load_skwm_json(MASTER)
    ta = json.load(open(TA, encoding="utf-8"))
    terms = load_skwm_json(CORE)
    ar_texts = json.load(open(AR_TEXTS, encoding="utf-8")) if os.path.exists(AR_TEXTS) else {}

    ar_idx = build_ar_index(terms)
    print(f"ar 词表（排除通用+hamza归一化后）: {len(ar_idx)} 词")

    ar_papers = [p for p in master if p.get("language") == "ar"]
    print(f"阿语文献: {len(ar_papers)} 条（固定种子 {SEED} 抽 10 条）\n")

    changed = []
    for p in ar_papers:
        pid = pid_of(p)
        cur = ta.get(pid, {})
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
        new_state = {
            "matched": bool(hits),
            "terms": sorted(hits.keys()),
            "domains": sorted(set(hits.values())),
            "how": how,
        }
        old_terms = cur.get("terms") or []
        old_matched = bool(cur.get("matched"))
        same = (old_matched == new_state["matched"]
                and sorted(old_terms) == new_state["terms"])
        changed.append({
            "pid": pid, "title": title,
            "old_matched": old_matched, "new_matched": new_state["matched"],
            "old_terms_count": len(old_terms), "new_terms_count": len(new_state["terms"]),
            "old_terms": old_terms, "new_terms": new_state["terms"],
            "how": how, "same": same,
        })

    # dry-run 输出（不覆盖主文件）
    json.dump(changed, open(DRY_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 对比表
    print("=" * 100)
    print(f"{'#':>2} {'旧碎片数':>7} {'新真词数':>7} {'匹配方式':<9} {'状态':<6} 标题")
    print("=" * 100)
    for i, c in enumerate(changed, 1):
        st = "同" if c["same"] else "不同"
        print(f"{i:>2} {c['old_terms_count']:>7} {c['new_terms_count']:>7} {c['how']:<9} {st:<6} {c['title'][:45]}")
    n_same = sum(1 for c in changed if c["same"])
    print("=" * 100)
    print(f"完全一致: {n_same}/27 | dry-run 文件: {DRY_OUT}（未写回 topic_assignments.json）")

    # 随机抽 10 条并排打印（固定种子）
    random.seed(SEED)
    sample = random.sample(changed, 10)
    print(f"\n{'#' * 30} 随机抽 10 条（种子 {SEED}）新旧 terms 并排 {'#' * 30}")
    for i, c in enumerate(sample, 1):
        old = c["old_terms"][:30]
        new = c["new_terms"][:30]
        old_s = ", ".join(old) if old else "（无/碎片，前30个展示）"
        new_s = ", ".join(new) if new else "（无）"
        print(f"\n--- 抽样{i} [{c['old_terms_count']}->{c['new_terms_count']} {c['how']}] {c['title'][:50]}")
        print(f"  旧 terms({c['old_terms_count']}): {old_s}")
        print(f"  新 terms({c['new_terms_count']}): {new_s}")

if __name__ == "__main__":
    main()
