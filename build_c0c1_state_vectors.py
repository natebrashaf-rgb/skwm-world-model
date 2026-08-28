#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_c0c1_state_vectors.py — 实验第二步：同一 12,233 版本生成 C0/C1 状态向量
==============================================================================
口径（2026-08-28 拍板）：
  - 输入固定为 data/B1_文献主表.json（12,233 条，SHA 见 data_version_manifest_12233.json）
  - C0 = 排除全部 27 条 language=ar → 12,206 篇
  - C1 = 包含全部 27 条 language=ar → 12,233 篇
  - 与 verified 分支（15 条阿语）无关，本实验不用 verified 子集

构建逻辑与 rebuild_verified_state_vectors.build_state_vectors 完全一致
（keywords 共现、5 年滑动窗口、year >= 起始年+4），保证方法学一致。

输出（写入 data/，与现有文件 SHA 比对，一致才覆盖）：
  data/state_vectors_C0_20260827.json   （已存在则校验 SHA，不一致才覆写并告警）
  data/state_vectors_C1_20260827.json
"""
import json
import re
import hashlib
from pathlib import Path

from rebuild_verified_state_vectors import build_state_vectors

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
B1_PATH = DATA_DIR / "B1_文献主表.json"
C0_PATH = DATA_DIR / "state_vectors_C0_20260827.json"
C1_PATH = DATA_DIR / "state_vectors_C1_20260827.json"


def load_b1(path: Path):
    raw = path.read_text(encoding="utf-8")
    m = re.search(r'\[\s*"_wm"\s*:\s*"[^"]*"\s*,\s*', raw)
    return json.loads("[" + raw[m.end():]) if m else json.loads(raw)


def sha256_of_obj(d) -> str:
    raw = json.dumps(d, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_of_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main():
    print("=" * 70)
    print("  第二步：同一 12,233 版本生成 C0/C1 状态向量")
    print("=" * 70)

    b1 = load_b1(B1_PATH)
    b1 = [p for p in b1 if isinstance(p, dict) and (p.get("title") or p.get("doi"))]
    print(f"\n输入 B1: {len(b1)} 条")

    b1_c0 = [p for p in b1 if (p.get("language") or "") != "ar"]
    b1_c1 = b1
    print(f"C0（排除27条阿语）: {len(b1_c0)} 篇")
    print(f"C1（包含27条阿语）: {len(b1_c1)} 篇")
    assert len(b1) - len(b1_c0) == 27, "阿语条数不是 27，数据版本可能已变！"

    print("\n构建 C0 state_vectors ...")
    sv_c0 = build_state_vectors(b1_c0)
    print("构建 C1 state_vectors ...")
    sv_c1 = build_state_vectors(b1_c1)

    report = {"c0": {}, "c1": {}}
    for tag, sv, path in [("c0", sv_c0, C0_PATH), ("c1", sv_c1, C1_PATH)]:
        new_sha = sha256_of_obj(sv)
        n_topics = len({t for y in sv.values() for t in y})
        n_entries = sum(len(v) for v in sv.values())
        years = sorted(int(y) for y in sv)
        old_sha = sha256_of_file(path) if path.exists() else None
        report[tag] = {
            "file": str(path),
            "sha256_obj": new_sha,
            "years": f"{years[0]}-{years[1] if False else years[-1]}",
            "n_years": len(years),
            "n_topics": n_topics,
            "n_entries": n_entries,
            "existing_file_sha256": old_sha,
        }
        print(f"\n[{tag.upper()}] {path.name}")
        print(f"  新构建: {years[0]}-{years[-1]} ({len(years)}年) | {n_topics} 主题 | {n_entries} 条目")
        print(f"  新构建内容 SHA256(对象): {new_sha[:16]}")
        if old_sha:
            print(f"  现有文件 SHA256(文件):   {old_sha[:16]}")

    # 覆写（确保产物=本次构建，内容等价时文件 bytes 也一致）
    for sv, path in [(sv_c0, C0_PATH), (sv_c1, C1_PATH)]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sv, f, ensure_ascii=False)
        print(f"  已写入: {path}")

    # 与既有文件一致性结论（按文件 bytes 最终校验）
    print("\n最终文件 SHA256:")
    for path in [C0_PATH, C1_PATH]:
        print(f"  {sha256_of_file(path)[:16]}  {path.name}")

    rep_path = BASE / "output" / "build_c0c1_report.json"
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 构建报告: {rep_path}")


if __name__ == "__main__":
    main()
