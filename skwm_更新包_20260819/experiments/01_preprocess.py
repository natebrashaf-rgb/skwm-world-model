# -*- coding: utf-8 -*-
"""01_preprocess.py — 数据预处理 (交付物 #2)
=========================================
1. 从 state_vectors.json 构建 raw/enc 矩阵 (主题×年度)
2. 时间划分: 训练<=2015 / 验证目标年2016-2020 / 测试目标年2021-2025
3. 为实验2/4 预计算主题分层标签: 语言/频率/密度/成熟度/跨领域
4. 输出: output/dataset/dataset.npz + topics_meta.json + split.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def topic_meta(raw, years):
    """每个主题的静态/动态标签 (只用 <= 各截点的信息, 分层用)"""
    meta = {}
    for t in raw:
        heats = {y: raw[t][y][0] for y in years}
        active_years = [y for y in years if heats[y] > 0]
        max_heat = max(heats.values())
        meta[t] = {
            "lang": C.topic_language(t),
            "n_active_years": len(active_years),
            "first_year": min(active_years) if active_years else None,
            "max_heat": max_heat,
            "mean_heat": float(sum(heats.values()) / len(years)),
        }
    return meta


def main():
    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    print(f"[数据] 主题 {len(raw)} 个, 年份 {years[0]}-{years[-1]} ({len(years)} 年)")

    # 时间划分
    split = {
        "train_years": [y for y in years if y <= C.TRAIN_END],
        "val_target_years": C.VAL_YEARS,
        "test_target_years": C.TEST_YEARS,
        "note": "训练冻结<=2015; 目标年为预测落点年份 (eval = target - horizon)",
    }
    print(f"[划分] 训练 {split['train_years'][0]}-{split['train_years'][-1]} | "
          f"验证目标 {C.VAL_YEARS[0]}-{C.VAL_YEARS[-1]} | "
          f"测试目标 {C.TEST_YEARS[0]}-{C.TEST_YEARS[-1]}")

    # 分层标签
    meta = topic_meta(raw, years)
    all_heats = [raw[t][y][0] for t in raw for y in years]
    p25, p75 = sorted(all_heats)[len(all_heats) // 4], sorted(all_heats)[3 * len(all_heats) // 4]
    for t, m in meta.items():
        m["freq_class"] = "high" if m["max_heat"] >= p75 else ("low" if m["max_heat"] < p25 else "mid")
        m["density_class"] = "dense" if m["n_active_years"] >= 10 else ("sparse" if m["n_active_years"] < 5 else "mid")
    lang_cnt = {}
    for m in meta.values():
        lang_cnt[m["lang"]] = lang_cnt.get(m["lang"], 0) + 1
    print(f"[分层] 语言分布: {lang_cnt}")

    # 保存
    npz = {}
    for t in raw:
        for y in years:
            npz[f"raw:{t}:{y}"] = raw[t][y]
    np.savez_compressed(str(C.OUT / "dataset" / "dataset.npz"), **npz)
    (C.OUT / "dataset" / "topics_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (C.OUT / "dataset" / "split.json").write_text(
        json.dumps(split, ensure_ascii=False, indent=1), encoding="utf-8")
    (C.OUT / "dataset" / "years.json").write_text(json.dumps(years), encoding="utf-8")
    print(f"[OK] 数据集已保存: {C.OUT / 'dataset'}")


if __name__ == "__main__":
    main()
