# 数据画像报告（第0步产出）

## 一、文件清单

### 1.1 state_vectors.json（主数据源）
| 属性 | 值 |
|------|:----:|
| 路径 | `02_deliverables/world_model/state_vectors.json` |
| 大小 | ~3.1 MB |
| 年份覆盖 | 1895–2026（89年） |
| 实体数(2026) | **2,194** 个 |
| 总实体×年 | ~43,5xx（跨年累计） |
| 每条格式 | `实体名: [heat, growth, centrality, connections]` |
| 2026热点TOP5 | ①旅游6555 ②tour5676 ③文化3956 ④nation3119 ⑤遗产2417 |

### 1.2 temporal_snapshots.json（时序切片）
| 属性 | 值 |
|------|:----:|
| 路径 | `02_deliverables/world_model/temporal_snapshots.json` |
| 大小 | ~50 MB |
| 年份 | 89年（1895–2026） |
| 早期密度 | 1895: 3节点 / 1912: 2节点（极稀疏） |
| 密度阈值年 | **~2000年**后持续 > 400节点 |
| 最近密度 | 2026: 2194节点 / 52,603边 |
| entity_types | 每年为空——未填充 |

### 1.3 kg_stats.json（知识图谱统计）
| 属性 | 值 |
|------|:----:|
| 节点 | **3,467**（Paper:2000 Topic:820 Author:385 Concept:200...） |
| 边 | **1,320**（studies:738 authored_by:541 related_to:19...） |
| 口径说明 | 这是"知识图谱1.0"的主题网络，与state_vectors不同口径 |

### 1.4 core_terms.json（核心术语）
| 属性 | 值 |
|------|:----:|
| 条数 | **9,013** |
| 三语 | en/cn/ar 三字段，**98.4%** 含阿文 |
| 领域分布 | 旅游1949 / 文化艺术1373 / 经济贸易1337 / 文化遗产921... |

### 1.5 dynamics_xgboost.pkl
| 属性 | 值 |
|------|:----:|
| 大小 | ~464 KB |
| 内容 | XGBoost模型，AUC≈0.9408 |

---

## 二、2026热点基准校验

| 关键词 | 期望heat | 实际heat | 结果 |
|:-------|:--------:|:--------:|:----:|
| 旅游 | 6555 | **6555** | ✅ |
| 文化 | 3956 | **3956** | ✅ |
| 遗产 | 2417 | **2417** | ✅ |
| 数字 | 1330 | **1330** | ✅ |
| 阿拉伯 | 1132 | **1132** | ✅ |

**5/5全部通过 ✅**

---

## 三、前沿榜原始噪声词

从2026年实体列表截取（存在大量通用英文词/噪声）：
```
burden, gene, rate, search, access, change, case, cell, report, 
analysis, data, development, effect, evaluation, expression, 
group, health, impact, level, management, method, model, network, 
performance, process, research, response, result, review, risk, 
role, score, state, status, study, system, technology, test, 
treatment, use, value
```
这些属于通用学术词，需用停用词表过滤。

---

## 四、仓库内数字矛盾标记

| 指标 | 来源A | 来源B | 说明 |
|:-----|:-----:|:-----:|:-----|
| 状态向量总数 | 43,537（知识卡） | 43,526（实际计算） | ✅不同口径：跨年累计vs某个切片，不矛盾 |
| 共现关系 | 586,912（知识卡） | 1320（kg_stats） | ⚠️混用！586,912是state_vectors所有年份connections总和；1320是知识图谱1.0的边数 |
| 文献数 | 15,478（app_legacy） | 11,601（B1文件） | ⚠️15,478是B1+阿语+目录之和，11,601是B1主表 |

---

## 五、工程建议

1. **热点API**：从`state_vectors[year]`直接读`[0]`（heat字段），无需计算
2. **前沿API**：frontier = 相邻年份growth差值，从state_vectors读`[1]`（growth字段）
3. **时间轴**：默认展示2000–2026（密度≥400节点），全89年可选
4. **噪声过滤**：内置~80个通用学术英文停用词
5. **三语**：对接core_terms.json的en→cn→ar映射
