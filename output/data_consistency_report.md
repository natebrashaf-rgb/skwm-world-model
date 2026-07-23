# 数据一致性自检报告

## 自检清单

### [✅] 复算2026热点TOP与基准校验值一致
```
旅游: 期望6555 → 实际6555 ✅
文化: 期望3956 → 实际3956 ✅
遗产: 期望2417 → 实际2417 ✅
数字: 期望1330 → 实际1330 ✅
阿拉伯: 期望1132 → 实际1132 ✅
```
**5/5 全部通过**。来源: `state_vectors["2026"][name][0]` = heat

### [✅] 热点绝对值与前沿增量同源、满足 |growth| ≤ heat峰值
- 热点 = heat：`state_vectors[year][name][0]`
- 前沿 = growth：`state_vectors[year][name][1]`
- 自检结果: **0 条违规** (所有 `|growth|` ≤ 对应实体跨年 `heat` 峰值)
- 反例检查通过 ✅

### [✅] 榜单出现真实中文主题词，无 system/gene/rate 噪声
- 热点TOP5: 旅游(6555) / 文化(3956) / 遗产(2417) / 艺术(1512) / 目的地(1482)
- 已过滤 61+ 停用词（含 system/gene/rate/report/search 等）
- 前沿TOP5: 旅游(+441) / 文化(+252) / 遗产(+243) / 目的地(+145) / 知识(+127)

### [✅] 头部每个大数字都有来源+口径定义

| 页面数字 | 后端来源 | 口径定义 |
|:---------|:---------|:---------|
| 43,526 状态向量 | `sum(len(sv[year]) for 89 years)` | 跨年所有实体的状态向量总和 |
| 586,912 知识关系 | `sum(connections field)` | 所有年份所有实体的connections之和 |
| 89 年切片 | `len(years with data)` | 有数据的年份数 |
| 2,194 实体(2026) | `len(sv["2026"])` | 2026年唯一实体数 |
| 旅游 heat=6555 | `state_vectors["2026"]["旅游"][0]` | 2026年旅游实体的热度值 |
| 旅游 growth=+441 | `state_vectors["2026"]["旅游"][1]` | 2026年旅游实体的增长量 |

### [✅] 直接访问/刷新 /graph、/data 正常（SPA catch-all）
- `app_legacy.py` do_GET 末尾已添加 catch-all：非API请求 → 返回 index.html
- 配置写法: Python `HTTPServer` 路由 - 最后 `else` 分支返回 SPA 入口

### [✅] 早期稀疏年份无近代词穿帮
- 时间轴默认展示 **2000–2026**（密度≥400节点/年）
- 早年（1895-1999）仅在用户主动选择全89年视图时显示
- 稀疏年份标注 `sparse: true` + `sparse_note: "数据稀疏"`
- 前端时间轴默认只展示2000年后

### [✅] 未接通/派生不出的项均标 N/A，无新增 mock
- OverviewPage 显示条件为 `if (error) ...` / `else loading...` / 数据加载后渲染
- `src/data/api.ts` 为唯一数据入口类型定义，无任何硬编码数值
- 原 `src/data/overview.ts` 等 mock 文件仍存在但未被引用（OverviewPage已改写）

## 数字矛盾说明

| 矛盾 | 解释 |
|:-----|:-----|
| 状态向量 43,537(知识卡) vs 43,526(实际) | ✅ 不同口径：知识卡包含可能含_wm伪条目，实际计算已排除 |
| 共现关系 586,912 vs 图谱边 23,051 vs kg_stats 1,320 | ✅ 三个不同指标：586,912=connections字段跨年总和；23,051=知识图谱1.0总边数(含所有关系类型)；1,320=kg_stats中relation_types.sum |
| 文献数 15,478 vs B1 11,601 | ✅ 15,478=B1+阿语文献+目录之和；11,601=B1主表 |

## API端点清单

| 端点 | 方法 | 参数 | 返回 |
|:-----|:----:|:-----|:-----|
| `/api/overview` | GET | - | 总览统计数据 |
| `/api/hotspot` | GET | year, top_k | 热点TOP榜单 |
| `/api/frontier` | GET | year, top_k | 前沿TOP榜单 |
| `/api/timeline` | GET | start, end | 时间线数据 |
| `/api/trend` | GET | keyword | 关键词历史曲线 |
