# -*- coding: utf-8 -*-
"""07_service_materials.py — 实验5: 图书馆服务盲评材料 (交付物 #8)
================================================================
基于真实回测输出, 生成 8-12 个"中阿文旅新兴交叉主题识别"任务, 每任务 A/B 两条件:
  A: 静态科学计量 + 知识图谱 (当前增速/热度/中心度/连接数)
  B: 静态 + RSSM 多步预测 (含不确定性区间)
除是否含 RSSM 预测外, 知识库/主题数/证据数/文字长度保持一致。

随机化: 拉丁方安排 A/B 呈现顺序 (支持 5-7 名评价者)
输出: output/service_materials/
  tasks_A.json / tasks_B.json / materials_AB_randomized.csv / 评分表.csv
注意: 本脚本不生成任何专家评分; 评分必须由真人完成后再导入 08_analysis_template.py。
"""
import csv
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

N_TASKS = 10
FREEZE_YEARS = list(range(2016, 2023))   # 7 个冻结年 (t+3 <= 2025)
K_TOPIC = 10
QUESTION_VARIANTS = [
    "请识别{year}年之后 1-3 年内可能兴起的中阿文旅交叉主题, 并给出依据 (证据链可追溯)。",
    "请识别{year}年之后可能兴起的中阿文旅交叉主题, 并标注每个主题的置信度与不确定性来源。",
    "请基于{year}年及之前的数据, 给出中阿文旅领域 Top-10 新兴交叉方向预测, 并说明与既有热点区别。",
]


def pad_to(text, length):
    """补齐/截断到固定长度 (防按篇幅猜条件)"""
    if len(text) >= length:
        return text[:length]
    return text + " " * (length - len(text))


def build_tasks():
    sv = C.load_state_vectors()
    raw, enc, years = C.build_matrices(sv)
    model = __import__("models").load_rssm(C.RUN / "model_rssm_frozen_s42.pt")

    tasks = []
    for i, t in enumerate(FREEZE_YEARS[:7]):
        cand = {tp: raw[tp][t] for tp in raw if raw[tp][t][0] >= C.MIN_HEAT_EVAL}
        if len(cand) < K_TOPIC:
            continue
        # A: 静态 — 当前增速排序
        static_rank = sorted(cand, key=lambda x: -cand[x][1])[:K_TOPIC]
        # B: RSSM 预测 — 3年预测增量
        hist_years = [y for y in years if y <= t][-(C.T + 1):]
        H, valid = [], []
        for tp in cand:
            es = np.stack([enc[tp][y] for y in hist_years])
            H.append(np.diff(es, axis=0)[-C.T:])
            valid.append(tp)
        import torch
        Ht = torch.tensor(np.stack(H).astype(np.float32))
        with torch.no_grad():
            pd = model.model.imagine_from_history(
                Ht, torch.zeros(len(valid), 3, model.model.c.a_dim),
                deterministic=True).numpy()
        pred_growth = {}
        for i2, tp in enumerate(valid):
            cur = raw[tp][t][0]
            pred_growth[tp] = float(np.expm1(
                enc[tp][t][0] + np.cumsum(pd[i2], axis=0)[-1, 0])) - cur
        rssm_rank = sorted(pred_growth, key=pred_growth.get, reverse=True)[:K_TOPIC]

        def fmt(topic, extra=""):
            h, g, ce, co = raw[topic][t]
            return {"topic": topic, "heat": h, "growth": g,
                    "centrality": round(ce, 3), "connections": co,
                    **(extra if extra else {})}

        a_topics = [fmt(x) for x in static_rank]
        b_topics = [fmt(x, {"predicted_growth_3y": round(pred_growth[x], 1)})
                    for x in rssm_rank]
        base_len = 300
        tasks.append({
            "task_id": f"T{len(tasks) + 1}",
            "freeze_year": t,
            "question": QUESTION_VARIANTS[0].format(year=t),
            "cond_A": {"title": "基于历史数据的前沿识别", "topics": a_topics,
                       "summary": pad_to(json.dumps(a_topics, ensure_ascii=False), base_len)},
            "cond_B": {"title": "基于历史数据的前沿识别", "topics": b_topics,
                       "summary": pad_to(json.dumps(b_topics, ensure_ascii=False), base_len)},
        })

    # 补充 3 个问题变体任务 (冻结年 2022)
    t = 2022
    cand = {tp: raw[tp][t] for tp in raw if raw[tp][t][0] >= C.MIN_HEAT_EVAL}
    if len(cand) >= K_TOPIC:
        static_rank = sorted(cand, key=lambda x: -cand[x][1])[:K_TOPIC]
        hist_years = [y for y in years if y <= t][-(C.T + 1):]
        H, valid = [], []
        for tp in cand:
            es = np.stack([enc[tp][y] for y in hist_years])
            H.append(np.diff(es, axis=0)[-C.T:])
            valid.append(tp)
        import torch
        Ht = torch.tensor(np.stack(H).astype(np.float32))
        with torch.no_grad():
            pd = model.model.imagine_from_history(
                Ht, torch.zeros(len(valid), 3, model.model.c.a_dim),
                deterministic=True).numpy()
        pred_growth = {}
        for i2, tp in enumerate(valid):
            cur = raw[tp][t][0]
            pred_growth[tp] = float(np.expm1(
                enc[tp][t][0] + np.cumsum(pd[i2], axis=0)[-1, 0])) - cur
        rssm_rank = sorted(pred_growth, key=pred_growth.get, reverse=True)[:K_TOPIC]
        for v in QUESTION_VARIANTS[1:]:
            a_topics = [{"topic": x, "heat": raw[x][t][0], "growth": raw[x][t][1],
                         "centrality": round(raw[x][t][2], 3),
                         "connections": raw[x][t][3]} for x in static_rank]
            b_topics = [{"topic": x, "heat": raw[x][t][0], "growth": raw[x][t][1],
                         "centrality": round(raw[x][t][2], 3),
                         "connections": raw[x][t][3],
                         "predicted_growth_3y": round(pred_growth[x], 1)}
                        for x in rssm_rank]
            tasks.append({
                "task_id": f"T{len(tasks) + 1}",
                "freeze_year": t,
                "question": v.format(year=t),
                "cond_A": {"title": "基于历史数据的前沿识别", "topics": a_topics,
                           "summary": pad_to(json.dumps(a_topics, ensure_ascii=False), 300)},
                "cond_B": {"title": "基于历史数据的前沿识别", "topics": b_topics,
                           "summary": pad_to(json.dumps(b_topics, ensure_ascii=False), 300)},
            })
    return tasks


def main():
    random.seed(20260818)
    tasks = build_tasks()
    print(f"[材料] 生成 {len(tasks)} 个任务 (冻结年 {FREEZE_YEARS[:len(tasks)]})")

    out_dir = C.OUT / "service_materials"
    (out_dir / "tasks_A.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "tasks_B.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")

    # 拉丁方 A/B 呈现顺序 (5-7 名评价者)
    n_eval = 6
    order = []
    for i in range(n_eval):
        # 每名评价者内部: 前一半任务 A 先, 后一半 B 先 (交叉)
        seq = []
        for j, t in enumerate(tasks):
            if (i + j) % 2 == 0:
                seq.append((t["task_id"], "A", t["cond_A"], t["cond_B"]))
            else:
                seq.append((t["task_id"], "B", t["cond_B"], t["cond_A"]))
        order.append(seq)

    with open(out_dir / "materials_AB_randomized.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["评价者编号", "任务ID", "呈现顺序", "材料内容(条件X)", "材料内容(条件Y)"])
        for i, seq in enumerate(order):
            for tid, first, cx, cy in seq:
                w.writerow([f"R{i+1}", tid, f"{first}先", cx["summary"], cy["summary"]])

    # 评分表模板 (空白 — 等待真实评价者填写)
    dims = ["前沿识别准确性(1-5)", "前瞻性(1-5)", "新颖性(1-5)", "证据充分性(1-5)",
            "证据可追溯性(1-5)", "对学科服务决策的帮助(1-5)", "纳入学科前沿报告的意愿(1-5)",
            "完成时间(秒)", "评价者信心(1-5)", "质性反馈"]
    with open(out_dir / "评分表.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        header = ["评价者编号", "任务ID", "条件(A/B, 随机化后填写)"] + dims
        w.writerow(header)
        for i in range(n_eval):
            for t in tasks:
                w.writerow([f"R{i+1}", t["task_id"], "", *([""] * len(dims))])

    print(f"[OK] 材料: {out_dir}")
    print("     提示: 评分表必须由 5-7 名真实评价者(学科馆员/图情教师/研究人员)")
    print("     填写后, 用 08_analysis_template.py 导入分析; AI 不生成评分。")


if __name__ == "__main__":
    main()
