# service_experiment/ — 图书馆服务增量实验
# ========================================
# 对应论文 §4.2 实验二：S0/S1/S2 服务对照
#
# 目录结构:
#   service_queries.csv          馆员服务问题集 (中/英/阿, 简单/困难/零结果)
#   neo4j_static_service.py      S0: Neo4j 静态检索 + 当前科学计量
#   temporal_baseline_service.py S1: S0 + 普通趋势/XGBoost
#   rssm_prediction_service.py   S2: S0 + RSSM 多步预测 + 不确定性
#   run_blind_experiment.py      生成盲评材料 + 汇总评价
#   evidence_trace.csv           证据追溯记录
#   condition_S0/                S0 条件输出
#   condition_S1/                S1 条件输出
#   condition_S2/                S2 条件输出
#
# 三组必须使用相同知识库、截止年份、任务、界面、结果数量和证据数量，
# 只改变预测机制。评价者看不到条件名称。
#
# 运行:
#   python service_experiment/run_blind_experiment.py
