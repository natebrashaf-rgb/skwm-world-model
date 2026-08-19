# -*- coding: utf-8 -*-
"""09_figures.py — 论文图表 (交付物 #15)
======================================
图1: 实验1 MAE (模型×视野, 均值±95%CI 误差棒)
图2: 实验1 level_Spearman / growth_P@10
图3: 实验2 新兴主题 P@10 随冻结年
图4: 实验3 消融对比
图5: 实验4 稳健性热力图
所有图用英文标签 (避免 CJK 字体缺字)。
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIG = C.OUT / "figures"
MODELS = ["B0_last", "B0_ma", "B0_linear", "B1", "B2", "M"]
HORIZONS = [1, 3, 5]


def load_summary():
    p = C.OUT / "backtest" / "results_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def fig1_mae():
    rows = load_summary()
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, h in zip(axes, HORIZONS):
        names, mus, los, his = [], [], [], []
        for r in rows:
            if r["horizon"] != h or r["split"] != "test":
                continue
            m = r["metrics"].get("level_MAE")
            if not m:
                continue
            names.append(r["model"])
            mus.append(m["mean"])
            ci = m.get("ci95")
            los.append(m["mean"] - ci[0] if ci and ci[0] is not None else 0)
            his.append(ci[1] - m["mean"] if ci and ci[1] is not None else 0)
        ax.errorbar(range(len(names)), mus, yerr=[los, his], fmt="o-", capsize=4)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=30)
        ax.set_title(f"Horizon {h}y (test 2021-2025)")
        ax.set_ylabel("Level MAE (mean +/- 95%CI)")
    fig.tight_layout()
    fig.savefig(FIG / "fig1_mae.pdf")
    fig.savefig(FIG / "fig1_mae.png", dpi=150)
    plt.close(fig)


def fig2_rho_p10():
    rows = load_summary()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, key, title in ((axes[0], "level_Spearman", "Level Spearman (test)"),
                           (axes[1], "growth_P@10", "Growth P@10 (test)")):
        for h, marker in zip(HORIZONS, "os^"):
            names, vals = [], []
            for r in rows:
                if r["horizon"] != h or r["split"] != "test":
                    continue
                m = r["metrics"].get(key)
                if not m:
                    continue
                names.append(r["model"])
                vals.append(m["mean"])
            ax.plot(range(len(names)), vals, marker + "-", label=f"{h}y")
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, rotation=30)
        ax.set_title(title)
        ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "fig2_rho_p10.pdf")
    fig.savefig(FIG / "fig2_rho_p10.png", dpi=150)
    plt.close(fig)


def fig3_emerging():
    p = C.OUT / "emerging" / "emerging_metrics.json"
    if not p.exists():
        print("[fig3] 实验2结果缺失, 跳过")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(8, 5))
    by_model = {}
    for r in d["per_freeze_year"]:
        if r["horizon"] != 3:
            continue
        by_model.setdefault(r["model"], []).append((r["freeze_year"], r["P@10"]))
    for model, pts in by_model.items():
        pts = sorted(pts)
        ax.plot([x[0] for x in pts], [x[1] for x in pts], "o-", label=model)
    ax.set_xlabel("Freeze year (predict 3y ahead)")
    ax.set_ylabel("Emerging-topic P@10")
    ax.set_title("Experiment 2: emerging topic hit rate over freeze years (h=3)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "fig3_emerging.pdf")
    fig.savefig(FIG / "fig3_emerging.png", dpi=150)
    plt.close(fig)


def fig4_ablation():
    p = C.OUT / "ablation" / "ablation_results.json"
    if not p.exists():
        print("[fig4] 实验3结果缺失, 跳过")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    variants = ["A_full", "B_nostoch", "C_nodyn", "D_gru"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, h in zip(axes, HORIZONS):
        names, maes = [], []
        for v in variants:
            s = d["summary"].get(f"{v}|{h}")
            if s and s.get("level_MAE") is not None:
                names.append(v)
                maes.append(s["level_MAE"])
        ax.bar(range(len(names)), maes)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=20)
        ax.set_title(f"Horizon {h}y (val targets 2016-2020)")
        ax.set_ylabel("Level MAE")
    fig.tight_layout()
    fig.savefig(FIG / "fig4_ablation.pdf")
    fig.savefig(FIG / "fig4_ablation.png", dpi=150)
    plt.close(fig)


def fig5_robustness():
    p = C.OUT / "robustness" / "robustness_results.json"
    if not p.exists():
        print("[fig5] 实验4结果缺失, 跳过")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = [r for r in d if r["model"] in ("B1", "M") and r["horizon"] == 3]
    if not rows:
        print("[fig5] 数据不足, 跳过")
        return
    slices = sorted(set(r["slice"] for r in rows))
    fig, ax = plt.subplots(figsize=(12, 5))
    width = 0.38
    for i, model in enumerate(("B1", "M")):
        vals = []
        for s in slices:
            rs = [r for r in rows if r["slice"] == s and r["model"] == model]
            vals.append(np.mean([r["Spearman"] for r in rs]) if rs else np.nan)
        ax.bar([x + (i - 0.5) * width for x in range(len(slices))], vals,
               width=width, label=model)
    ax.set_xticks(range(len(slices)))
    ax.set_xticklabels(slices, rotation=40, ha="right")
    ax.set_ylabel("Growth Spearman (h=3)")
    ax.legend()
    ax.set_title("Experiment 4: robustness across topic/period slices")
    fig.tight_layout()
    fig.savefig(FIG / "fig5_robustness.pdf")
    fig.savefig(FIG / "fig5_robustness.png", dpi=150)
    plt.close(fig)


def main():
    fig1_mae()
    fig2_rho_p10()
    fig3_emerging()
    fig4_ablation()
    fig5_robustness()
    print(f"[OK] 图表已保存: {FIG}")


if __name__ == "__main__":
    main()
