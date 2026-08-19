# SKWM 数据集说明（README）

> 本文件说明仓库 data/ 目录下每个数据文件的用途、字段、条数、来源。
> 生成时间: 2026-08-19（按当时仓库内容核对）
> 最近更新: 2026-08-19 阿语文献同步（B1 12179 条, 阿语主题 98 个）
> 2026-08-19 晚间: 双条修复（B1 12179→12177, 删 2 条英文重复采集, 保留阿语版）

## ⚠️ 已知限制（先看这里，别漏）

| # | 限制 | 影响 |
|---|------|------|
| 1 | 埃及知识银行(EKB) 171 篇被拦，没拿到（名单在 ekb_blocked_list.json） | 埃及相关文献不完整 |
| 2 | 558 篇付费文献没有全文 | pdf_texts.json 只有 6063 篇，不是全部 12155 篇 |
| 3 | 阿语标题文献只有 17 篇（占 0.14%），阿语主题数为 0 | 阿语子方向预测不可靠（论文 RQ4 已写明） |
| 4 | state_vectors.json 里 growth/centrality/connections 的精确计算脚本没有全部入库 | 口径来源待确认，论文需注明 |
| 5 | 2026 年是不完整年 | 预测目标截止到 2025 年 |
| 6 | 核心术语.json 是损坏残留文件（14 字节），别用它 | 用 core_terms.json |
| 7 | B1_has_pdf.bak.json、B1_merged.json、B1_文献主表.bak_20260817.json 是历史中间版本 | 一律以 B1_文献主表.json 为准，别混用 |
| 8 | 部分 JSON 开头带 "_wm" 隐形水印（防泄漏标记） | 读取时要先剥掉（wm_server.py 已处理） |

## 一、核心数据（实验和服务都在用）

### 1. B1_文献主表.json — 文献主表
- 条数: 12177 条（2026-08-19 双条修复后）
  - 原 12155 + 阿语撰写文献 13 条 + 阿旅英文文献 11 条 = 12179
  - 删 2 条英文重复采集（10.58205/fber.v3i1.1462、10.47832/2717-8293.16.26 的英文版，
    与阿语版同 DOI，保留阿语版）→ 12177
- 语言分布: en 11586 / zh 564 / **ar 27**
- 生成: 多轮检索+去重+扩充（2026-08-18 数据扩充 + 2026-08-19 阿语同步），生成脚本分散，无单一脚本
- 字段:

| 字段 | 含义 |
|------|------|
| title | 论文标题 |
| year | 发表年份 |
| citations | 被引次数 |
| authors | 作者列表 |
| venue | 期刊/会议 |
| doi | DOI 编号 |
| is_oa | 是否开放获取 |
| _source | 来源（数据库/站点） |
| language | 语言 |
| keywords | 关键词 |
| normalized_keywords | 归一化后的关键词 |
| has_pdf | 是否有 PDF 全文 |

### 2. topic_assignments.json — 论文→主题分配
- 条数: 12155 键（键是 DOI，和主表一一对应）
- 生成: match_topics.py / merge_pdf_matching.py
- 字段: title, year, matched（是否匹配上）, terms（匹配到的词）, domains（所属领域）, non_tourism（是否非旅游主题）

### 3. pdf_texts.json — PDF 全文文本
- 条数: 6063 篇（键是文件名，值是全文纯文本）
- 生成: extract_pdfs.py
- 注意: 只有 6063 篇有全文，其余 6092 篇没有（付费 558 篇 + 埃及站 171 篇 + 其他未抓到）

### 4. core_terms.json — 三语受控词表
- 条数: 9014 词
- 生成: skwm_trilingual_pipeline.py
- 字段: en（英文）, cn（中文）, ar（阿语）, domain（领域）, freq（词频）, type（词类型）
- 注意: 文件开头带 "_wm" 水印，读取需剥离

### 5. state_vectors.json — 主题×年度状态向量（实验核心输入）
- 条数: 90 年（1895-2026），每年若干主题
- 格式: 每个主题-年度 = [heat, growth, centrality, connections] 4 维向量
- 生成: scripts/state_snapshot.py（as-of 语义，防未来信息泄漏）
- **阿语主题: 98 个（2026-08-19 阿语文献同步后，从 0 起步）**
  如 سياحة(旅游)、تراث(遗产)、ثقافة(文化)、حج(朝觐)、دبي(迪拜)、العراق(伊拉克)
- 注意: growth/centrality/connections 的精确计算脚本未全部入库（见限制 #4）

### 5b. 阿语文献（2026-08-19 同步）
- 来源: E盘 01_literature 5688 个 PDF 全量扫描（阿语字符占比），精选 16 篇阿拉伯语撰写文旅文献
- 13 篇已入主表（language=ar），全文在 pdf_texts_arabic_20260819.json
- 阿语主题 98 个已入 state_vectors.json（详见 E:\大挑\产出\交接_20260819\阿语文献同步报告_20260819.md）

### 6. temporal_snapshots.json — 逐年图快照
- 条数: 89 年
- 字段: nodes, edges, n_nodes, n_edges（每年知识图谱节点/边）

## 二、图谱相关

| 文件 | 内容 | 说明 |
|------|------|------|
| knowledge_graph.gexf | 知识图谱（40MB GEXF 格式） | 全量图 |
| graph_node_index.json | 节点索引，4472 个节点，字段 type | 主题→节点类型 |
| dynamics_xgboost.pkl | XGBoost 动力学模型（474KB） | 已入库，但 AUC=0.9408 无法复现（无训练脚本），标记未复现 |

## 三、阿语数据采集记录

| 文件 | 条数 | 说明 |
|------|------|------|
| _arabic_bulk_metadata.json | 4194 | 阿语批量元数据（arxiv 来源） |
| arab_tourism_meta.json | 965 | 阿语旅游文献元数据 |
| arab_tourism_progress.json | — | 采集进度（done_queries 等） |
| arab_tourism_pdf_queue.csv | — | PDF 下载队列 |
| ekb_blocked_list.json | 171 | 埃及站被拦截名单（未拿到） |
| doaj_collected.csv | — | DOAJ 采集记录 |
| pdf_crawled.csv / pdf_crawled_v3.csv | — | PDF 爬取记录（v3 为最新） |
| pdf_meta_v3.json | 1899 | PDF 元数据 v3 |

## 四、清理与杂项

| 文件 | 内容 |
|------|------|
| noise_removed_record.json | 噪声文献删除记录（441 条） |
| noise_med_cleanup.json | 中级清理记录（438 条） |
| merge_report.json | 合并报告（合并前后数量） |
| literature_catalog.md | 文献目录说明 |
| datiao/ | 目录（空/待用） |
| state_snapshots/ | 状态快照目录 |
| 核心术语.json | ⚠️ 损坏残留（14 字节），勿用 |

## 五、使用约定

1. 主表一律用 `B1_文献主表.json`（12155 条），不要用任何 .bak / B1_merged / B1_has_pdf
2. 读取带水印的 JSON（core_terms 等）先剥 `"_wm"` 标记
3. 论文/报告引用数据时，数字以本 README 为准（12155 / 6063 / 9014 / 89 年）
4. 实验流水线只消费 state_vectors.json；新增文献要让实验生效，必须先构建进 state_vectors（主题提取→年度统计→4 维向量）
