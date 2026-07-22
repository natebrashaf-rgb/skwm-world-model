# SKWM 平台接线指南（前端全部页面已改为 fetch 真实数据）

本升级包已经把 Next.js 平台的 **全部 7 个数据页面** 从写死的假数据改成
调用真实世界模型后端（`skwm_aligned_v4.py` + C/P 升级模块）。

接线只有 3 步，纯复制粘贴 + 启动后端，**不用再改任何页面代码**。

---

## 第 1 步：启动后端 API（约 5 分钟）

把以下文件放到你 `skwm_aligned_v4.py` 的**同一个目录**：

```
skwm_context.py      # C：语境引擎（读取 context.json）
skwm_service.py      # P：服务规则（推荐/审核/推送/沉淀）
api.py               # FastAPI 封装（暴露 /api/*）
context.json         # C 的语境权重配置（可编辑）
requirements.txt
```

然后：

```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

验证：浏览器打开 http://localhost:8000/api/health 应返回 `{"ok": true, ...}`；
交互式接口文档在 http://localhost:8000/docs 。

> ⚠️ 后端读取真实数据的路径写在 `skwm_aligned_v4.py` 里
> （`REAL_DATA_DIR = E:\大挑\02_deliverables\world_model`）。
> 如果数据不在该路径，改这一行即可。
> `xgboost` 装不上时预测接口会降级，其它接口照常。

---

## 第 2 步：前端搭桥（约 5 分钟，复制即可）

1. 把 `frontend/lib/api.ts` 复制到平台项目的 `lib/api.ts`。
2. 把 `frontend/next.config.js` 的 `rewrites` 合并进你的 `next.config.js`
   （作用：把前端的 `/api/*` 代理到 `localhost:8000`，规避跨域）。

如果你的项目已有 `next.config.js`，只需把其中的 `async rewrites()` 段落合并进去。

---

## 第 3 步：替换页面（1 步）

把本包的 `frontend/app/` **整个目录**覆盖到平台项目的 `app/`。

已改写为真实数据的页面：

| 页面 | 数据来源 |
|:--|:--|
| `dashboard` | `/api/overview` + `/api/frontier` + `/api/reports` |
| `scientometrics` | `/api/hotspots`(C加权) + `/api/frontier` + `/api/timeline` |
| `knowledge-graph` | `/api/overview` + `/api/graph`（含实体关系查询） |
| `reports` | `/api/reports` + `/api/report`（P 全链路生成） |
| `rag-advisor` | `/api/report`（真实报告智能体 + P.audit 审核） |
| `scenarios` | `/api/hotspots`（按 U 用户类型实时加权预览） |
| `settings` | `/api/health` + `/api/overview`（真实探测） |
| `literature` | `/api/overview`（实体/关系）＋标注待接文献库 API |

> `settings`/`literature` 里后端确实没有的字段（GraphRAG/BGE-M3/H20、
> 全文索引、PDF 原文）已**如实标注为“规划中/待接入”**，不再显示与论文冲突的假数字。

启动前端：

```bash
npm install   # 若未装依赖
npm run dev   # http://localhost:3000
```

后端未启动时，每个页面顶部会显示黄色提示条，指导你运行 uvicorn，不会白屏。

---

## 新增的两个后端接口

- `GET /api/timeline` —— 逐年真实节点/边数（科学计量页的年度演化柱状图）。
- `GET /api/reports` —— 列出 Obsidian 沉淀目录里的已生成报告。

---

## 可选：飞书推送 / Obsidian 沉淀（P 规则）

设置环境变量后自动启用；未设置时报告推送会回退写入 `push_outbox.log`：

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export OBSIDIAN_VAULT="/path/to/your/obsidian/vault"
```

---

## 数据流向一句话总结

```
真实数据(89年切片×4.3万状态向量) → skwm_aligned_v4.py(E/R/S/T/U)
    → skwm_context.py(C 语境加权) + skwm_service.py(P 推荐/审核/推送/沉淀)
    → api.py(/api/*) → next.config 代理 → lib/api.ts → 各页面 fetch 渲染
```
