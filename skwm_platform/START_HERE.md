# SKWM 平台（已合并成品）—— 直接跑就行

前端和后端已经缝好，你（或 Hermes）只剩 3 件事：① 告诉后端真实数据在哪里
② 启动后端  ③ 启动前端。

目录结构：
```
skwm_platform_merged/
├─ backend/     ← 后端（已含算法 + C/P 模块 + api.py）
└─ frontend/    ← 前端（已把 8 个页面改成 fetch 真实数据 + lib/api.ts + next.config.js）
```

> 唯一没法内置的是你那 ~13GB 的**真实数据**（在你电脑 `E:\大挑\02_deliverables\world_model`），
> 它不在本包里，请确保运行后端的那台机器上有这份数据。

---

## ① 启动后端（:8000）

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

如果你的真实数据**不在** `E:\大挑\02_deliverables\world_model`，
打开 `backend/skwm_aligned_v4.py`，把顶部的
`REAL_DATA_DIR = ...` 改成你实际的数据目录。

验证：浏览器开 http://localhost:8000/api/health → `{"ok": true}`；
http://localhost:8000/api/overview 的 entities/relations 不为 0 = 真实数据已加载。

（可选）DeepSeek key：放 `.deepseek_key` 或 `export DEEPSEEK_API_KEY=...`；
不配也能跑，只是报告描述用兜底文案。

---

## ② 启动前端（:3000）

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:3000 ，会自动跳到 `/dashboard`。

---

## ③ 验证连接成功

- 先后端后前端（前端的 `/api/*` 会被 `next.config.js` 代理到 :8000）。
- **成功标志**：工作台的“知识实体 / 关系 / 状态向量”显示真实数字（万级），
  而不是写死的 1,284 / 4,672。
- 页面顶部如出现黄色“未能连接后端”提示条 = :8000 没起，回到第①步。

---

## 连接关系

```
真实数据(E:\大挑\...) → backend/skwm_aligned_v4.py(E/R/S/T/U)
     + skwm_context.py(C) + skwm_service.py(P) → api.py → :8000/api/*
          ↑ next.config.js 代理
     frontend/lib/api.ts → app/ 各页面 fetch → :3000
```

更详细的接口对照见 `backend/INTEGRATION.md`。
