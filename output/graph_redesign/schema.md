# SKWM 知识图谱本体设计
## Property Graph Schema v2.0 + CIDOC-CRM 映射

---

## 一、实体类型（9类）

| 类型 | 中文 | 颜色 | 形状(G6) | 属性 | CIDOC-CRM 映射 |
|------|------|------|----------|------|----------------|
| `Paper` | 文献 | `#dbeafe` (蓝) | circle | id, title, year, lang, authors, abstract, citations | E31 Document |
| `Author` | 作者 | `#ccfbf1` (青) | diamond | id, name_zh, name_en, name_ar, org, h_index, paper_count | E39 Actor |
| `Organization` | 机构 | `#fef3c7` (黄) | square | id, name_zh, name_en, name_ar, country, type | E40 Legal Body |
| `Topic` | 主题 | `#e0e7ff` (靛) | circle | id, label_zh, label_en, label_ar, domain, heat, growth | E55 Type |
| `Location` | 地点 | `#d1fae5` (绿) | triangle | id, name_zh, name_en, name_ar, country, region | E53 Place |
| `Policy` | 政策 | `#fce7f3` (粉) | star | id, name_zh, name_en, name_ar, year, level | E30 Right |
| `Term` | 术语 | `#f5f5f4` (灰) | hexagon | id, label_zh, label_en, label_ar, domain | E55 Type |
| `TourismDestination` | 文旅目的地 | `#ffedd5` (橙) | circle | id, name_zh, name_en, name_ar, country, type, heritage_level | E27 Site |
| `CulturalHeritage` | 文化遗产 | `#ede9fe` (紫) | triangle | id, name_zh, name_en, name_ar, type, period, status | E1 CRM Entity |

## 二、关系类型（7类 + 1类对齐）

| 关系 | 中文 | 颜色 | 标签 | 语义 | 方向 |
|------|------|------|------|------|------|
| `cites` | 引用 | `#93c5fd` | 引用 | A引用B → A受B影响 | Paper→Paper |
| `collaborates` | 合作 | `#6ee7b7` | 合作 | A与B共同发表 | Author↔Author, Org↔Org |
| `co_occurs` | 共现 | `#fcd34d` | 共现 | A与B在同一文献中出现 | Topic↔Topic |
| `affiliated_with` | 隶属 | `#a78bfa` | 隶属 | A隶属于B | Author→Org, Paper→Org |
| `corresponds_to` | 对应 | `#f472b6` | 对应 | A与B跨语言/跨本体对应 | Topic↔Topic（三语对齐） |
| `influences` | 影响 | `#fb923c` | 影响 | A影响B的发展方向 | Topic→Topic, Policy→Topic |
| `evolves_to` | 演化 | `#34d399` | 演化 | A演化为B（时间序列） | Topic→Topic |
| `same_as` | 等同 | `#9ca3af` | = | 跨语言/跨数据源等同实体 | Any↔Any（消歧后） |

## 三、三语标签设计

每个实体节点必须有：
```json
{
  "id": "...",
  "label_zh": "文化遗产旅游",
  "label_en": "Cultural Heritage Tourism",
  "label_ar": "سياحة التراث الثقافي",
  "type": "Topic",
  // ... 其他属性
}
```

前端通过 `lang` 状态切换显示：
```tsx
const displayLabel = node[`label_${lang}`] || node.label_en;
```

## 四、属性图 Schema（Cypher/Cypher-like）

```cypher
// 节点: Paper
CREATE (p:Paper {
  id: string, title: string, year: int, lang: string,
  authors: [string], abstract: string, citations: int,
  source: string
})

// 节点: Topic  
CREATE (t:Topic {
  id: string, label_zh: string, label_en: string, label_ar: string,
  domain: string, heat: float, growth: float, centrality: float
})

// 关系: 共现
CREATE (t1:Topic)-[:CO_OCCURS {
  weight: float, sources: [string], first_year: int, last_year: int
}]->(t2:Topic)

// 关系: 对应 (三语对齐)
CREATE (t1:Topic {label_en: "tourism"})-[:CORRESPONDS_TO {
  confidence: float, method: string
}]->(t2:Topic {label_zh: "旅游"})
```

## 五、社区检测参数

- 算法: Louvain 社区发现
- 分辨率: 1.0（默认）
- 最小社区: 5 节点
- 社区着色: 10 色调循环色板（Tableau 10）
- 节点大小: `size = 5 + 10 * (pageRank / maxPageRank)`
- 边宽: `width = 0.5 + 2 * (weight / maxWeight)`

## 六、Ego-Network 展开策略

1. 默认渲染：核心子图（PageRank Top 50 + 顶层社区代表）
2. 点击节点 → 加载其 1-hop 邻域（最多 200 节点）
3. 双击已展开节点 → 收起其邻域
4. 缩放至 5px 以下 → 节点聚合为社区气泡（semantic zoom）
5. 聚合气泡内显示社区名 + 节点数

## 七、GraphRAG 支撑字段

每个实体附加：
```json
{
  "community_id": 7,
  "community_summary": "文旅融合与数字技术交叉领域",
  "page_rank": 0.042,
  "degree": 23,
  "embedding": [0.12, -0.34, ...]  // LaBSE 向量，用于子图检索
}
```

每个子图检索返回：
```json
{
  "subgraph": {
    "nodes": [...],
    "edges": [...],
    "community_summary": "...",
    "relevance_score": 0.87
  }
}
```
