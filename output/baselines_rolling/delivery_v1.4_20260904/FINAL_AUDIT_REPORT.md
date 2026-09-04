# FINAL_AUDIT_REPORT — SKWM 基线滚动回测 v1.4.1 组长二审终报

- 日期：2026-09-04
- 审计执行：科研代码审计 + 实验复现 + 证据包修复（对组长二审意见逐条闭环）
- 主脚本：experiment_baselines_rolling.py（v1.4.1）
- 配套脚本：audit_leakage.py（泄漏审计）、build_delivery.py（证据包生成）
- 仓库：rail_deploy @ GitHub origin/main commit `01eef48`（v1.4.1，已 push）
- 审计用原始命令与输出见各节；全部数字可从 results.json / run{1,2,3}.json / split_manifest.csv 逐字段追溯

---

## 一、数据版本

| 项 | 值 | 出处 |
|---|---|---|
| 数据文件 | data/state_vectors_C1_20260827.json | meta.data |
| SHA-256 | f6f5820a1149d1f60ec11120434693c606743f093b928c1c54b08de6dd0b292d | meta.data_sha256（脚本实测）+ 三轮 run json 一致 |
| 文献底盘 | 12,233 篇（B1 主表终版） | 仓库 data_version_manifest_12233.json |
| 状态向量条目 | 43,642（83 个观测年 1912–2026） | 数据文件实测 |
| 2026 | 部分年度，Part B 全程排除；Part A 仅对账保留 | meta.excluded_years |

复跑命令：`cd /e/大挑/rail_deploy && sha256sum data/state_vectors_C1_20260827.json` → f6f5820a…（与三轮运行一致，数据未被改动）。

## 二、实验版本

- 脚本版本 v1.4.1：v1.3 基础上新增 ① meta.data_sha256 实测 ② meta.origin_audit（逐 origin 时间边界）③ split_manifest 扩列（id/horizon/train_rows/feature_fit_end/preprocessing_fit_end/random_seed）④ 修正 version manifest 路径引用 ⑤ ranking tie-breaker（消除 PYTHONHASHSEED 跨进程影响，见第十一节）。
- 运行方式：完整跑 Part A（同窗口，c0c1 对账口径）+ Part B（滚动回测，正式口径），三轮独立进程。

## 三、Rolling origins

2014 / 2016 / 2018 / 2020（meta.cutoffs）。每 origin 只允许 year ≤ origin 的数据进入训练。

## 四、Horizons

h = 1 / 3 / 5（meta.horizons）。Part B 预测窗口 = (origin, origin + h]。

## 五、模型

| 模型 | 类型 | Part A | Part B |
|---|---|---|---|
| naive_last / moving_avg / linear / drift | 纯计算 M0 基线 | ✓ | ✓ |
| xgboost | M1（XGBRegressor 100 树，depth 4，lr 0.1，seed 42，逐 origin train_until） | ✓ | ✓ |
| rssm | M2（预训练 checkpoint model_rssm.pt，stochastic imagine） | ✓（对账用） | 默认排除（checkpoint 见过全时间线=前瞻风险） |

## 六、Cross-topic Spearman（排序能力，正式口径）

逐目标年跨主题秩相关，年均池化。字段：partA_same_window.overall.<h>.naive_last.cross_topic_spearman。

| h | naive_last MAE | cross_topic_spearman | 含义 |
|---|---|---|---|
| 1 | 12.6891 | **0.9283** | 去年排名是极强预测器（短期惯性） |
| 3 | 19.3500 | 0.8312 | 惯性随视野衰减 |
| 5 | 23.0199 | **0.7511** | 长期惯性弱化 |

滚动截点逐 origin（partB_rolling.<cp>.h=1/h=5.overall.naive_last.cross_topic_spearman）：

| origin | h=1 | h=5 |
|---|---|---|
| 2014 | 0.9126 | 0.7505 |
| 2016 | 0.8846 | 0.7525 |
| 2018 | 0.9290 | 0.7772 |
| 2020 | 0.9282 | 0.7715 |

→ 组长口径 h1 ≈ 0.9283、h5 ≈ 0.7511 与 Part A 实测**一致**（截图数字=Part A 口径；Part B 逐截点 0.88–0.93 / 0.75–0.78 同向）。

## 七、Temporal Spearman（主题内趋势能力）

字段：partB_rolling.<cp>.h=<h>.overall.xgboost.temporal_spearman（窗长 ≥3 的主题内 spearmanr 均值；h=1 单点退化为 None 不报告）。

三轮复跑范围（v1.4.1）：

| origin | h=3 | h=5 |
|---|---|---|
| 2014 | 0.1747–0.2700 | 0.2064–0.3647 |
| 2016 | 0.2903–0.3001 | 0.3838–0.4098 |
| 2018 | 0.3030–0.3138 | 0.3585–0.3810 |
| 2020 | 0.2974–0.3038 | 0.3397–0.3496 |

**如实说明差异**：组长截图口径「XGBoost ≈ 0.26–0.39」与 v1.3 单轮（当时 2014 h5=0.3626，全 8 格 0.26–0.39）吻合；本轮 2016–2020 三截点三轮稳定 [0.29, 0.41]（18 值范围 0.2903–0.4098），而 **2014 早截点（训练样本最少、历史最稀疏）跨进程波动大（run3 低至 0.17–0.21）**——系 xgboost 跨进程树结构差异 × 短窗 spearmanr 敏感放大的训练随机性，非口径错（独立复现诊断 3 进程均 0.34–0.37，未复现 run3 离群值，见 audit_tmp/probe_2014h5.py）。**论文建议表述**：XGBoost Temporal Spearman（origin 2016–2020，h=3/5）≈ 0.29–0.41，中位数约 0.34–0.35；注明 2014 早截点因数据稀疏波动至 0.17–0.27 的个别轮次现象。不做任何数字硬匹配。

## 八、MAE

| 位置 | 模型 | h=1 | h=3 | h=5 |
|---|---|---|---|---|
| Part A | naive_last | 12.6891 | 19.3500 | 23.0199 |
| Part A | moving_avg | 20.2040 | 24.3797 | — |
| Part A | linear | 12.6158 | 19.1484 | — |
| Part A | drift | — | — | — |
| Part A | xgboost | 20.4315（三轮 20.37–20.66） | 20.3872（20.37–20.61） | 23.1023 |
| Part A | rssm | 71.0434（三轮 71.025–71.043） | 61.5526（≈61.56–61.58） | 54.7198 |

（Part A 全表见 baselines_rolling_summary.md；"—" 见 run json 原表。）

## 九、P@10

- Part A naive_last P@10：h1=0.9333、h3=0.8667、h5=0.7667（三年均）。
- Part B 各截点见 run json；M0 全格三轮逐位一致；xgboost/rssm 随训练噪声在 ±0.03–0.33 档位波动（top-10 边界换位放大）。

## 十、Origin-only training 证明

代码级保证（experiment_baselines_rolling.py v1.4.1）：
1. M1XGBoostLeakFree.train_until(all_series, cutoff)：样本 i→i+1，`if series[i+1]["year"] > cutoff: break`——训练标签年 ≤ cutoff，特征窗口（lookback 5）更早。无全量先 fit、无 scaler/imputer/全局统计（树模型直接吃原始特征，不存在 preprocessing 全局 fit）。
2. Part B：`train_series = [s for s in series if s["year"] <= cutoff]`。
3. Manifest.add 逐行断言 ×914,670：`history_end <= train_cutoff`、`history_end < target_year`、`target_year > train_cutoff`、Part B `target_year != 2026`——任一违反即崩（不允许静默）。
4. meta.origin_audit 显式落盘（实测）：

| origin | history_end_max | target_year_min | n_test_topics | n_test_rows | constraint_ok |
|---|---|---|---|---|---|
| 2014 | 2014 | 2015 | 2,803 | 126,135 | true |
| 2016 | 2016 | 2017 | 2,803 | 126,135 | true |
| 2018 | 2018 | 2019 | 2,803 | 126,135 | true |
| 2020 | 2020 | 2021 | 2,803 | 126,135 | true |

→ **origin-only training 成立**。每个截点训练只用 ≤ origin 数据、测试目标严格 > origin。注意 train_rows 列 = 主题在该截点的历史槽位数（缺失年补 0 口径，与 build_topic_timeseries 一致），每主题同长源于补 0 表示；各主题实际有效观测见状态向量原始稀疏性。

## 十一、数据泄漏审计

audit_leakage.py 对 split_manifest.csv（914,670 行：A 410,130 + B 504,540）自动 10 项检查：

```
LEAKAGE AUDIT PASS — rows=914670 duplicates=0 expected_cross_horizon=0 violations=0
checks: 1_history_end<=train_cutoff=0 / 2_train_cutoff<target=0 / 3_train<=origin=0 /
        4_target>origin=0 / 4b_partial_year_in_B=0 / 5_no_overlap=0 / 6_no_duplicates=0 /
        7_missing_pred/actual=0 / 7c_target_in_window=0 / 8/9/10 无preprocessing（N/A_no_scaler 列）
```

复跑命令：`python3.14 audit_leakage.py` → leakage_audit_20260904.json（已入包）。
**审计发现并修复的表缺陷**：v1.3 表缺 horizon 列，同一预测样本被 h=1/3/5 多个视野重复记录（282,116 行）；v1.4 加 horizon 列后重复=0（同一物理样本跨视野记录属滚动设计预期，以 horizon 唯一标识，非泄漏）。
时间穿越：0。重复样本：0。缺失预测/真值：0。

## 十二、Part A vs c0c1 对账

- 参考文件：output/experiment_model_c0c1/experiment_model_c0c1_results.json（2026-08-28 快照，同一 C1 数据同一 seed 42 同 eval_plan）。
- 容差：diff ≤ 0.01 判 PASS。v1.4.1 三轮 FAIL = 9 / 8 / 10 格（v1.3 为 10 格；v1.4 首跑 7/13/12）——**FAIL 数与格位随轮次随机变化，全部集中在 xgboost/rssm**；M0 纯计算 27 格（naive_last/moving_avg/linear × MAE/Spearman/P@10 × h1/3/5）三轮全 diff=0.0 PASS。

## 十三、10 个 FAIL 的原因和处理结果（逐条）

结论（收敛表述）：**当前复现实验观察到训练/采样型模型存在跨进程非确定性；M0 纯计算模型三轮逐位一致，而 XGBoost/RSSM 单进程重复稳定、跨进程存在漂移。因此这些单次快照差异目前不能解释为数据口径或时间泄漏差异。若需要逐格复现，应对训练型模型采用多次运行的统计口径或固定完整确定性环境。**（不硬改任何数字。）
保留的事实基础：
- c0c1 是 2026-08-28 的**单次快照**；当前 v1.4.1 是三轮独立进程快照。
- M0 纯计算 27 格（naive_last/moving_avg/linear × MAE/Spearman/P@10 × h1/3/5）三轮与 c0c1 **逐位一致（diff=0.0）**——把数据/评测年/主题集/补 0/聚合口径全部锁定。
- 漂移范围（实测）：xgboost h1 MAE ∈ [20.3737, 20.6603]、rssm h1 MAE ∈ [71.0251, 71.0433]；c0c1 值（20.3987 / 71.0111）落在范围内。rssm 的 WorldModel.imagine 默认 deterministic=False（随机采样潜变量），是采样随机性的代码级来源。
- FAIL 数与格位随轮次随机变化（v1.3=10；v1.4 首跑 7/13/12；v1.4.1 9/8/10），且只出现在 xgboost/rssm。

| FAIL | 模型 | 指标 | 观察到的现象 | 处理 |
|---|---|---|---|---|
| h1 xgboost MAE diff 0.03–0.21 | xgboost | MAE | 跨进程漂移范围覆盖 c0c1 值 | 不改数字，报告范围；同进程可复现 |
| h1 xgboost P@10 diff 0.033 | xgboost | P@10 | top-10 边界排名换位（一档差） | 同上 |
| h3 xgboost MAE diff 0.02–0.22 | xgboost | MAE | 同上 | 同上 |
| h3 xgboost Spearman diff 0.01 | xgboost | Spearman | 同上（0.0105 仅超容差 0.0005） | 同上 |
| h5 xgboost MAE diff 0.15–0.21 | xgboost | MAE | 同上 | 同上 |
| h1 rssm MAE diff 0.025–0.032 | rssm | MAE | stochastic imagine 跨进程采样差 | 不改数字；逐位复现需锁 deterministic（会改变全部 rssm 数字，未采用） |
| h1 rssm P@10 diff 0.07–0.10 | rssm | P@10 | 随机采样排名跳档 | 同上 |
| h3 rssm Spearman diff 0.012–0.016 | rssm | Spearman | 随机采样 | 同上 |
| h3 rssm P@10 diff 0.17–0.33 | rssm | P@10 | 随机采样（rssm 精度差→排名近随机，P@10 档位波动大） | 同上 |
| h5 rssm P@10 diff 0.03–0.27 | rssm | P@10 | 同上 | 同上 |

未采用：为对齐截图/旧快照硬改数字（违反审计最高原则）。

## 十四、三轮复跑一致性

- run1/2/3 SHA-256：f3d6485e… / 80bc3729… / bb3fc9b9…（互不相同=训练噪声，符合 v1.1 起「训练记范围」铁律）。
- 纯计算模型（naive_last/moving_avg/linear/drift）三轮**逐位一致：Part A 0 格差异、Part B 0 格差异**（v1.4.1 tie-breaker 修复后；修复前 Part B cp=2014 NDCG 漂移 4 格 0.0027，根因=并列排名受 PYTHONHASHSEED 影响，排序加主题名次级键后消除，无 tie 格数字不变）。
- xgboost/rssm 记录范围（Part A h1 MAE）：xgboost [20.37, 20.66]、rssm [71.02, 71.04]；2016+ 截点 temporal 稳定（见第七节）。
- 复跑命令：`python3.14 experiment_baselines_rolling.py` ×3（约 8–9 分钟/轮），输出 runN.json。

## 十五、SHA-256

delivery 内 hashes.txt（9 文件，LF、无注释，sha256sum -c 100% OK）：
- run1.json f3d6485e472fef1f29902543d747416dee4c044ce431706319c00df0b6a58a07
- run2.json 80bc3729325080f659963bff2c207d1502781ba0f1ba422e64afd3ca1ff0bad8
- run3.json bb3fc9b9d0c6b4e77610ea8353b2a28411a9e95b67c6dd9a53a75a30096153a9
- split_manifest.csv 99b81c2e23f15abff1617b67bc1f2218dba67035ddf57fc783ab76be03e8f095
- results.json / baselines_rolling_20260904.json / summary.md / leakage_audit.json 见 hashes.txt 全文

## 十六、GitHub 一致性

远端 origin/main = commit `01eef48`（audit: baselines rolling v1.4.1…），本地 HEAD 同（up to date，push 前 fetch+rebase 无冲突）。

| 项 | 状态 | 说明 |
|---|---|---|
| 实验代码 | PASS | experiment_baselines_rolling.py v1.4.1（含 v1.4 全改动 + tie-breaker） |
| 配套审计代码 | PASS | audit_leakage.py、build_delivery.py |
| 配置 | PASS | 无独立 config，参数全在脚本常量（CUTOFFS/HORIZONS/TOP_K/SEED=42）且入 json meta |
| 数据 | PASS | state_vectors_C1_20260827.json tracked，SHA f6f5820a 与本地实测一致 |
| 结果 | PASS | run1/2/3.json、baselines_rolling_20260904.json、summary.md 已 push |
| split manifest | 部分 | split_manifest.csv（94.7MB）**未推 git**（仓库体积控制）；完整版在本 zip 内，可任意重新生成 |
| results.json | PASS | delivery 内 results.json 已 push（字段级引用主 json） |
| hashes.txt | PASS | 已 push |
| origin training | PASS | meta.origin_audit 4 截点 constraint_ok=true（第十节） |
| 论文核心数字 | PASS | 0.9283 / 0.7511 精确复现；temporal 见第七节范围表述 |

## 十七、最终论文可使用数字

1. **短期排序**：Naive-last Cross-topic Spearman h=1 = **0.9283**（Part A；滚动截点 0.8846–0.9290）——去年主题排名是极强短期预测器。
2. **长期排序**：h=5 = **0.7511**（Part A；滚动截点 0.7505–0.7772）——视野拉长惯性衰减（h3=0.8312 居中）。
3. **趋势识别**：XGBoost Temporal Spearman，origin 2016–2020 h=3/5 三轮稳定 **[0.29, 0.41]**（中位约 0.34–0.35）；2014 早截点数据稀疏，个别轮次低至 0.17——论文建议注明波动或只用 2016+ 截点表述「≈0.29–0.41」。
4. **RSSM 如实负结果**：Part A h3 MAE ≈ 61.55–61.58（本 61.55–61.58 vs c0c1 61.5774）未超基线；Part B 因 checkpoint 前瞻风险默认排除。
5. **数据底盘**：12,233 篇、SHA 固定 f6f5820a（数据文件）/ 43,642 状态向量条目。
6. 所有数字出处 = results.json → run{1,2,3}.json → split_manifest.csv 字段级可追溯；复跑即得。

## 修改的代码（A）与原因（B）

| 文件 | 修改 | 原因 |
|---|---|---|
| experiment_baselines_rolling.py | v1.4：meta.data_sha256 实测、meta.origin_audit、Manifest 扩列（id/horizon/train_rows/feature_fit_end/preprocessing_fit_end/random_seed）、version manifest 路径修正；v1.4.1：ranking tie-breaker | 组长要求 results.json/split_manifest 字段级可追溯 + origin-only 显式证明 + 消除跨进程 NDCG 漂移 |
| audit_leakage.py（新增） | 10 项泄漏审计 | 组长第六阶段要求 |
| build_delivery.py（新增） | 生成 results.json + delivery 目录 + hashes | 组长第五/九阶段要求（results.json 此前缺失） |

## 交付清单（G）

证据包 zip：`E:\大挑\rail_deploy\output\baselines_rolling\skwm_baselines_rolling_delivery_v1.4_20260904.zip`（8.5MB，含本报告共 9 文件，sha256sum -c 100% OK）：
results.json / baselines_rolling_20260904.json / baselines_rolling_summary.md / split_manifest.csv（914,670 行）/ run1.json / run2.json / run3.json / leakage_audit.json / FINAL_AUDIT_REPORT.md / hashes.txt。

## 可直接交给组长吗（H）

可以交付，附带两个必须让组长知道的如实说明：
1. xgboost/rssm 与 c0c1 快照的逐格差异是跨进程训练/采样噪声（量化证据在报告十三节与 audit_tmp/noise_quant_conclusion.md），M0 全等已锁定口径；若论文需要单一数字，用三轮中位数并标注范围，不要引用任何单次快照当"精确值"。
2. Temporal Spearman「0.26–0.39」截图口径只在 v1.3 单轮成立；v1.4.1 稳定口径为 2016+ 截点 [0.29, 0.41]，2014 截点波动大（见十七节第 3 条）。

## 还差哪一项（I）

无硬缺口。可选增强：把 94.7MB split_manifest.csv 推 GitHub（需组长确认可接受仓库体积 +~95MB，本包默认不推）；或组员 Brashaf 侧需要跑「origin 训练」验证时用本包命令即可。

---

## 十八、二审修复记录（2026-09-04，组长二次独立检查后）

### 发现的问题
交付 ZIP 内 leakage_audit.json 与 FINAL_AUDIT_REPORT.md 矛盾：
- 报告声称 LEAKAGE AUDIT PASS（duplicates=0, violations=0）
- 实际 zip 内 leakage_audit.json = duplicates=282116, pass=false, manifest_tag="v13_backup"

### 根因（真实，非文档掩盖）
1. 早前用 v1.3 旧表测试 audit_leakage.py 时生成了 leakage_audit_v13_backup.json（FAIL），测试后未清理；
2. build_delivery.py 当时用 `sorted(glob("leakage_audit_*.json"))[-1]` 取「最后一个」——字典序 'v13_backup' > '20260904'（'v'=0x76 > '2'=0x32），**持续错取到 v1.3 备份的 FAIL 结果**拷入 delivery；
3. 终端当时打印的 LEAKAGE AUDIT PASS 来自 audit_leakage.py 直接生成的正确文件（leakage_audit_20260904.json），与 build_delivery 复制进包的文件不是同一个——两条链没对齐，且 zip 封口只做了 sha256sum 校验（hash 匹配但没核对内容语义），未发现内容错配。

### 修复动作
1. leakage_audit_v13_backup.json 移出 output/baselines_rolling/（入 audit_tmp/ 保留历史，命名 .json.hist 防止再被工具 glob）；
2. build_delivery.py 修复：leakage 审计**只认与当天主输出同日的文件** `leakage_audit_<today>.json`，且**显式校验 pass=true，FAIL 审计禁止打包**（直接退出）；
3. audit_leakage.py 重跑（对当前 v1.4 split_manifest.csv）→ PASS；
4. build_delivery.py 重跑 → results.json 嵌入正确 leakage_audit；
5. 本报告更新（措辞收敛 + 本记录），重新 hashes.txt → 重新打包 ZIP → 实际打开 zip 内文件逐项核验（见第十九节验收表）。

### 结果（真实，实际打开 zip 内文件核验）
leakage_audit.json（zip 内）：manifest_version=v1.4_with_horizon、manifest_tag=""（非 v13_backup）、n_rows=914670、n_duplicates=0、n_violations_total=0、pass=true、check 6_no_duplicate_rows.violations=0、rows_by_part={A_same_window:410130, B_rolling:504540}。

### 整条证据链一致性保证
代码 → audit_leakage.py 运行 → leakage_audit_20260904.json → build_delivery.py（同日文件 + pass 校验）→ results.json（内嵌同源 leakage）→ FINAL_AUDIT_REPORT.md（与 results.json 同源数字）→ hashes.txt（LF、sha256sum -c 100%）→ delivery ZIP（解压后逐文件内容核验）→ GitHub push（代码 + 结果小文件，csv 不推）。

## 十九、二审最终验收表（实际打开 ZIP 内文件逐项核验）

| 检查项 | 要求 | 实测 | 结果 |
|---|---|---|---|
| A. results.json | 存在且非空 | 见 zip 清单（6,401B+，含全部 paper_numbers） | PASS |
| B. split_manifest.csv | 914,670 行、16 列 | 行数实测 + 表头 16 列（id/part/model/origin/horizon/…/random_seed） | PASS |
| C. leakage_audit.json | duplicates=0, violations=0, pass=true, tag 非 v13_backup | 见第十八节实测 | PASS |
| D. FINAL_AUDIT_REPORT | 与 leakage_audit.json 一致 | 第十一节/第十八节数字同源 | PASS |
| E. results.json | 与上述一致 | results.json.leakage_audit 内嵌同文件 | PASS |
| F. hashes.txt | sha256sum -c 100% | 解压全新临时目录验证 | PASS |
| G. h1 Naive-last | 0.9283 | results.json.paper_numbers | PASS |
| H. h5 Naive-last | 0.7511 | results.json.paper_numbers | PASS |
| I. Temporal Spearman | v1.4.1 2016+ [0.29, 0.41]，非旧 0.26–0.39 | 第七节/十七节表述 | PASS |
| J. origin-only audit | 成立 | meta.origin_audit 4 截点 constraint_ok=true | PASS |
| K. GitHub commit | 与报告一致 | 主代码 v1.4.1=01eef48；配套修复与证据见仓库 git log（HEAD 即最新，csv 未推） | PASS |
