# 实验流水线运行说明
=====================

## 环境
```bash
pip install -r requirements.txt
```
依赖: numpy scipy xgboost torch matplotlib (fastapi/uvicorn 仅服务部署需要)

## 数据
- 观测数据: ../run/data/state_vectors.json (主题×年度 4 维状态向量)
- 文献主表: ../run/data/B1_文献主表.json (实验2/5 的论文层证据)
- 时间划分: 训练<=2015 / 验证目标年 2016-2020 / 测试目标年 2021-2025

## 运行顺序 (全部命令在 exp/ 目录下执行)
```bash
python 00_data_check.py              # 1. 数据检查报告
python 01_preprocess.py              # 2. 数据预处理
python train_rssm_frozen.sh          # 3a. 训练协议 RSSM (或手动:)
#   cd ../run && python train_rssm_v3.py --steps 12000 --out model_rssm_frozen_s42.pt --seed 42 --split-year 2016
#   cd ../run && python train_rssm_v3.py --steps 12000 --out model_rssm_frozen_s43.pt --seed 43 --split-year 2016
python 03_backtest.py --models B0_last B0_ma B0_linear B1 B2 --tag _part1   # 4a. 基线+XGB+GRU
python 03_backtest.py --models M --tag _part2                                # 4b. RSSM (需要冻结模型)
# 合并: 运行 --tag "" 全部模型, 或手动合并 npz
python 04_emerging.py --tag _all     # 5. 新兴主题回测
python 05_ablation.py                # 6. RSSM 消融 (需先训练消融变体)
python 06_robustness.py --tag _all   # 7. 稳健性分层
python 07_service_materials.py       # 8. 盲评材料 (A/B, 随机化, 评分表)
python 08_analysis_template.py       # 9. 评分分析 (等待真实评分)
python 09_figures.py                 # 15. 论文图表
```

## 输出
- output/check/ 数据检查报告
- output/dataset/ 预处理数据集
- output/backtest/ 实验1 全部中间结果+汇总
- output/emerging/ 实验2
- output/ablation/ 实验3
- output/robustness/ 实验4
- output/service_materials/ 实验5 材料+评分表
- output/figures/ 论文图表 (pdf+png)
- output/logs/ 运行日志

## 防泄漏约定 (全流水线强制)
1. 任何模型训练只用 <=2015 数据 (冻结协议)
2. 推理只用 <= eval_year 的历史窗口
3. 候选主题以评测年 heat>=5 过滤 (只用当年及以前信息)
4. RSSM 训练主题筛选只用训练期 max_heat (不用未来信息)
5. 多种子报告 mean±std+95%CI, 不挑最好种子
