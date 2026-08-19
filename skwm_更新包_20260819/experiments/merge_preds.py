# -*- coding: utf-8 -*-
"""merge_preds.py — 合并分 tag 的预测 npz 为 predictions_all.npz
用法: python merge_preds.py [tag1 tag2 ...]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main():
    tags = sys.argv[1:] or ["_part1", "_part2"]
    merged = {}
    for tag in tags:
        p = C.OUT / "backtest" / f"predictions{tag}.npz"
        if not p.exists():
            print(f"[跳过] {p} 不存在")
            continue
        d = np.load(p, allow_pickle=True)
        for k in d.files:
            merged[k] = d[k]
        print(f"[合并] {p}: {len(d.files)} 个键")
    out = C.OUT / "backtest" / "predictions_all.npz"
    np.savez_compressed(str(out), **merged)
    print(f"[OK] 合并完成: {out} ({len(merged)} 键)")


if __name__ == "__main__":
    main()
