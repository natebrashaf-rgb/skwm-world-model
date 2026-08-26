# -*- coding: utf-8 -*-
"""
第5步：修复 11 条非阿语字符串 terms 脏数据（2026-08-27）
=====================================================
问题：terms/domains/matched/non_tourism 被错误序列化成字符串
  - terms   = '["contemporary", "issues", ...]'（JSON数组文本）
  - domains = '["阿拉伯文旅"]'
  - matched = 'True' / non_tourism = 'False'（字符串）
修复：json.loads 无损还原成 list/布尔，不重新匹配、不丢词。
用法：python3.14 scripts/fix_str_typed_entries.py
"""
import json, os, re, shutil, datetime

DATA = r"E:\大挑\rail_deploy\data"
TA = os.path.join(DATA, "topic_assignments.json")
BAK_DIR = r"E:\大挑\产出\重建_20260826\backup"

def load_ta(path):
    raw = open(path, encoding="utf-8").read()
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    if m:
        return json.loads("[" + raw[m.end():])
    return json.loads(raw)

def main():
    # 1. 备份（带时间戳）
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(BAK_DIR, f"topic_assignments.bak_strfix_{ts}.json")
    shutil.copy2(TA, bak)
    print(f"备份: {bak}")

    ta = load_ta(TA)
    fixed = 0
    for pid, v in ta.items():
        if not isinstance(v, dict):
            continue
        changed = False
        # terms: 字符串 → json.loads
        if isinstance(v.get("terms"), str):
            try:
                parsed = json.loads(v["terms"])
                if isinstance(parsed, list):
                    v["terms"] = parsed
                    changed = True
            except Exception:
                pass
        # domains: 字符串 → json.loads
        if isinstance(v.get("domains"), str):
            try:
                parsed = json.loads(v["domains"])
                if isinstance(parsed, list):
                    v["domains"] = parsed
                    changed = True
            except Exception:
                pass
        # matched/non_tourism: 字符串 → 布尔
        if isinstance(v.get("matched"), str):
            v["matched"] = v["matched"] == "True"
            changed = True
        if isinstance(v.get("non_tourism"), str):
            v["non_tourism"] = v["non_tourism"] == "True"
            changed = True
        if changed:
            fixed += 1
    print(f"修复条目: {fixed}")

    # 2. 写回（indent=1 + CRLF，保持格式）
    with open(TA, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(ta, ensure_ascii=False, indent=1).replace("\n", "\r\n"))
    print(f"已写回: {TA}")

    # 3. 验证
    ta2 = load_ta(TA)
    str_terms = [pid for pid, v in ta2.items() if isinstance(v.get("terms"), str)]
    str_matched = [pid for pid, v in ta2.items() if isinstance(v.get("matched"), str)]
    print(f"验证: 剩余字符串 terms {len(str_terms)} 条 | 剩余字符串 matched {len(str_matched)} 条")

if __name__ == "__main__":
    main()
