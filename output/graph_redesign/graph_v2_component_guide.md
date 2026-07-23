# SKWM 知识图谱新组件 + 模块联动方案

## 一、新图谱组件架构 (GraphV2.tsx)

参考 `skwm_platform/frontend_new/src/pages/GraphPage.tsx` 改造。

### 核心改进

```
旧版                        → 新版
─────────────────────────────────────────────────
25节点固定数据               → 50核+200邻域动态加载
无类型区分                    → 8类实体按Schema着色
无边标签                     → 7类语义标签边
无社区                       → 11个Louvain社区着色
全节点平铺                    → 核心子图(50) + 邻域展开
无搜索/最短路径              → 搜索框 + 路径查询
只有中英                      → 中阿英三语切换
无联动                        → 热点/时间轴/GraphRAG联动
```

### 组件接口

```tsx
interface GraphV2Props {
  lang: 'zh' | 'ar' | 'en';       // 语言切换
  highlightNodes?: string[];        // 高亮节点（模块联动）
  timelineYear?: number;            // 时间轴年份（模块联动）
  onNodeClick?: (node: GraphNode) => void;  // 点击回调
  onCommunityClick?: (communityId: number) => void;
}

// 数据源：/api/graph-data?v2=true （返回规范图数据）
```

### 渲染策略

1. **首次加载**：核心子图 50 节点（PageRank Top 50 + 社区代表）
2. **点击节点** → 请求 `/api/graph-ego?node={id}&hops=1` → 展开 1-hop 邻域（动态加载，最多 200 节点）
3. **双击节点** → 收起其邻域
4. **缩放到 5px 以下** → 聚合为社区气泡（semantic zoom）
5. **搜索框输入** → 聚焦匹配节点，高亮其 1-hop 邻域

### 颜色方案（按 Schema）

```typescript
const TYPE_COLORS: Record<string, string> = {
  'Paper': '#dbeafe', 'Author': '#ccfbf1', 'Organization': '#fef3c7',
  'Topic': '#e0e7ff', 'Location': '#d1fae5', 'Policy': '#fce7f3',
  'Term': '#f5f5f4', 'TourismDestination': '#ffedd5', 'CulturalHeritage': '#ede9fe',
}

const RELATION_COLORS: Record<string, string> = {
  'cites': '#93c5fd', 'collaborates': '#6ee7b7', 'co_occurs': '#fcd34d',
  'affiliated_with': '#a78bfa', 'corresponds_to': '#f472b6',
  'influences': '#fb923c', 'evolves_to': '#34d399', 'same_as': '#9ca3af',
}
```

---

## 二、模块联动方案

### 2.1 热点 → 图谱联动

```
[OverviewPage: 点击热点TOP5主题]
  ↓ 触发 graphSearchEvent('tourism')
  ↓ 携带 { term: 'tourism', source: 'hotspot' }
[GraphV2Page: 监听事件]
  ↓ 搜索匹配节点 → 高亮 1-hop 邻域 → 聚焦居中
```

**实现方式**：使用 `window.dispatchEvent(new CustomEvent('graph:search', { detail: { term, source } }))`

### 2.2 时间轴 → 图谱联动

```
[TimelinePage: 滑块拖动到2021]
  ↓ 触发 graphTimelineEvent(2021)
[GraphV2Page: 监听事件]  
  ↓ 过滤掉非2021的文献/事件节点 → 剩余节点重新布局
```

**实现方式**：`window.dispatchEvent(new CustomEvent('graph:timeline', { detail: { year } }))`

### 2.3 智能问答 → 图谱联动

```
[QaPage: 发送问题 → 收到答案含证据子图]
  ↓ 答案展示 3 篇引用文献的 ID 列表
  ↓ 触发 graphEvidenceEvent(['paper-123', 'paper-456', 'paper-789'])
[GraphV2Page: 监听事件]
  ↓ 高亮这 3 篇文献节点 + 它们的 1-hop 邻域
  ↓ 用金色边框标记证据节点
```

**实现方式**：`window.dispatchEvent(new CustomEvent('graph:evidence', { detail: { nodeIds } }))`

### 2.4 接收方统一接口

```typescript
// 在 GraphV2 组件中
useEffect(() => {
  const handlers = {
    'graph:search': (e: CustomEvent) => {
      focusAndHighlight(e.detail.term, e.detail.source);
    },
    'graph:timeline': (e: CustomEvent) => {
      filterByYear(e.detail.year);
    },
    'graph:evidence': (e: CustomEvent) => {
      highlightEvidence(e.detail.nodeIds);
    },
  };
  
  Object.entries(handlers).forEach(([event, fn]) => {
    window.addEventListener(event, fn as EventListener);
  });
  return () => {
    Object.entries(handlers).forEach(([event, fn]) => {
      window.removeEventListener(event, fn as EventListener);
    });
  };
}, []);
```

---

## 三、GraphRAG 支撑

### 3.1 `app_legacy.py` 新增端点

```
GET /api/graph-v2          → 返回核心子图 (50节点 + 社区信息)
GET /api/graph-ego?id=X&hops=1  → 返回节点X的1-hop邻域
GET /api/graph-path?s=A&t=B     → 返回A→B最短路径
GET /api/graph-community?id=C   → 返回社区C的摘要
GET /api/graph-search?q=tourism → 搜索匹配节点
```

### 3.2 社区摘要格式

```json
{
  "community_id": 3,
  "size": 71,
  "top_types": {"Topic": 68, "Term": 3},
  "representatives": ["tourism", "heritage", "cultural tourism", "digital heritage"],
  "summary": "社区3: 文旅融合与遗产保护领域，包含 tourism/heritage 等 71 个实体",
  "relevance_to_query": 0.87
}
```

### 3.3 答案溯源

GraphRAG 查询结果携带：
```json
{
  "answer": "...",
  "evidence": {
    "sources": [
      {"type": "subgraph", "community_id": 3, "confidence": 0.92},
      {"type": "paper", "id": "paper-123", "title": "...", "confidence": 0.85}
    ]
  }
}
```

---

## 四、实施路线图

| 阶段 | 内容 | 优先级 |
|:----|:-----|:------:|
| P0 | Schema文档 + 去重管线 + graph_v2.json | ✅ DONE |
| P1 | 新 GraphV2 组件（核心子图+ego展开+社区着色） | 现在 |
| P2 | 搜索/最短路径/三语切换 | P1后 |
| P3 | Timeline/热点/GraphRAG 联动 | P2后 |
| P4 | G6 迁移（当前d3-force占位，后续换G6） | 备选 |
