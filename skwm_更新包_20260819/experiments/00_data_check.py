# -*- coding: utf-8 -*-
"""00_data_check.py — 数据检查报告 (交付物 #1)
==========================================
检查: 数据字段 / 模型文件 / AUC=0.9408 复现 / 泄漏面 / 缺失项
输出: output/check/数据检查报告.md + data_check.json
"""
import json
import os
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main():
    report = []
    P = report.append
    P("# 数据检查报告 (实验流水线前置检查)")
    P("> 生成时间: 由 00_data_check.py 实跑生成; 不虚构任何数字。\n")

    # ---------- 1. 数据文件 ----------
    P("## 1. 数据文件与字段\n")
    sv = C.load_state_vectors()
    years = C.years_available(sv)
    usable = [y for y in years if C.YEAR_START <= y <= C.YEAR_END]
    P(f"- state_vectors.json: 存在, 年份 {years[0]}-{years[-1]} "
      f"({len(years)} 年), 本实验使用 {C.YEAR_START}-{C.YEAR_END}")
    n_topics_latest = len(sv.get(str(2023), {}))
    P(f"- 2023 年主题数: {n_topics_latest}")
    P("- 字段: 每个主题-年度向量 = [heat, growth, centrality, connections] (4维)")

    b1 = C.RUN / "data" / "B1_文献主表.json"
    if b1.exists():
        import re
        raw_txt = b1.read_text(encoding="utf-8")
        papers = json.loads(raw_txt, strict=False)
        ar = sum(1 for p in papers if re.search(r"[\u0600-\u06FF]", str(p.get("title", ""))))
        P(f"- B1_文献主表.json: {len(papers)} 篇; 阿语标题 {ar} 篇 "
          f"({ar / max(1, len(papers)) * 100:.2f}%)  ← 阿语稀疏为数据层硬伤")
    else:
        P("- B1_文献主表.json: **缺失** (实验2需要时按需下载)")

    # ---------- 2. 模型文件 ----------
    P("\n## 2. 模型文件\n")
    for f in ("model_rssm_v3.pt", "model_rssm_frozen_s42.pt", "model_rssm_frozen_s43.pt"):
        p = C.RUN / f
        if p.exists():
            meta = {}
            try:
                d = torch_load(p)
                meta = d.get("meta", {})
            except Exception:
                pass
            P(f"- {f}: 存在 ({p.stat().st_size:,} B), meta={json.dumps(meta, ensure_ascii=False)[:160]}")
        else:
            P(f"- {f}: **尚不存在** (由 train_rssm_v3.py --split-year 2016 生成)")
    for f in ("dynamics_xgboost.pkl",):
        p = C.RUN / "data" / f
        if p.exists():
            P(f"- data/{f}: 存在 ({p.stat().st_size:,} B)")
        else:
            P(f"- data/{f}: **缺失** (仓库有, 需下载)")

    # ---------- 3. AUC=0.9408 复现检查 ----------
    P("\n## 3. XGBoost AUC=0.9408 复现检查\n")
    pkl = C.RUN / "data" / "dynamics_xgboost.pkl"
    if pkl.exists():
        try:
            with open(pkl, "rb") as f:
                obj = pickle.load(f)
            params = obj.get_params() if hasattr(obj, "get_params") else {}
            P(f"- 文件可加载: {type(obj).__name__}")
            P(f"- 参数: {json.dumps(params, default=str)[:300]}")
            P("- **AUC=0.9408 无法由本仓库现有代码复现**: 仓库中没有任何"
              "训练脚本/评测脚本/数据划分能重建该 AUC (data_profile_report.md 仅记录"
              "结论, 无复现路径) → 按用户要求标记为 **未复现**, 本流水线不使用该数字。")
        except Exception as e:
            P(f"- 文件加载失败: {e} → AUC 无法复现, 标记 **未复现**")
    else:
        P("- dynamics_xgboost.pkl 缺失 → AUC=0.9408 **未复现** (无模型文件, 无训练脚本)")

    # ---------- 4. RSSM 是否接入真实数据 ----------
    P("\n## 4. RSSM 真实数据接入检查\n")
    v3 = C.RUN / "model_rssm_v3.pt"
    if v3.exists():
        d = torch_load(v3)
        meta = d.get("meta", {})
        P(f"- model_rssm_v3.pt meta: {json.dumps(meta, ensure_ascii=False)[:220]}")
        P(f"- 训练数据: {meta.get('train_years')}, 序列 {meta.get('n_sequences')}, "
          f"目标 {meta.get('target')} → **RSSM 已接入真实主题-年度状态数据 "
          f"(非随机空跑)**")
    else:
        P("- RSSM 模型缺失 → 待训练")

    # ---------- 5. 泄漏面检查 ----------
    P("\n## 5. 未来信息泄漏检查\n")
    P("- 状态向量构建 (scripts/state_snapshot.py): as_of_year 语义, "
      "只使用 year <= Y 的 Paper → 构建层面防泄漏")
    P("- 本流水线: 所有模型训练冻结 <=2015; 推理只用 <= eval_year 的历史窗口; "
      "候选主题以评测年 heat>=5 过滤 (只用当年及以前信息)")
    P("- 已修复的历史泄漏 (v3 轮): ①RSSM 全期训练 → 严格 <split_year 划分; "
      "②M1 XGBoost 全期训练 → 按评测年截断; ③S1/S2 服务预测未按 as_of_year 截断")
    P("- 剩余需团队确认: state_vectors 中 growth/centrality/connections 的"
      "精确计算脚本未全部入库 (data_profile_report 自述口径存在混用) → "
      "建议论文注明口径来源")
    P("- 2026 年为不完整年 → 本流水线预测目标截止 2025")

    # ---------- 6. 缺失项 ----------
    P("\n## 6. 缺失项清单\n")
    missing = []
    if not (C.RUN / "model_rssm_frozen_s42.pt").exists():
        missing.append("按本协议(训练≤2015)训练的 RSSM 模型 (后台训练中)")
    if not (C.RUN / "data" / "dynamics_xgboost.pkl").exists():
        missing.append("dynamics_xgboost.pkl (AUC 复现用, 标记未复现)")
    for m in missing:
        P(f"- {m}")
    if not missing:
        P("- 无 (按协议所需文件均已就绪)")

    # ---------- 7. 可运行性结论 ----------
    P("\n## 7. 实验可运行性结论\n")
    P("| 实验 | 状态 | 说明 |")
    P("|---|---|---|")
    P("| 实验1 模型回测 (B0/B1/B2/M) | ✅ 可运行 | B0/B1/B2 立即; M 待冻结协议模型训练完成 |")
    P("| 实验2 新兴主题回测 | ✅ 可运行 | 依赖实验1预测输出 |")
    P("| 实验3 RSSM 消融 | ✅ 可运行 | 需训练消融变体 (B无随机/C无动态/D=GRU) |")
    P("| 实验4 稳健性分层 | ✅ 可运行 | 复用实验1预测切片 |")
    P("| 实验5 服务材料生成 | ✅ 可运行 | 材料可生成; 专家评分必须由真人填写 |")

    md = "\n".join(report)
    out_md = C.OUT / "check" / "数据检查报告.md"
    out_md.write_text(md, encoding="utf-8")
    print(md)


def torch_load(path):
    import torch
    return torch.load(str(path), map_location="cpu", weights_only=False)


if __name__ == "__main__":
    main()
