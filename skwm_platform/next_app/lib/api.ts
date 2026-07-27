// lib/api.ts —— 前端统一请求封装
// 配合 next.config.js 的 rewrites，所有路径都走相对的 /api/*

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`API ${path} 失败: ${r.status}`);
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`API ${path} 失败: ${r.status}`);
  return r.json();
}

export type Overview = {
  entities: number; relations: number; state_vectors: number;
  snapshots: number; year_range: [number, number];
};
export type HotItem = {
  name: string; heat: number; growth: number;
  centrality: number; connections: number;
  context_weight: number; context_score: number;
};
export type EmergingItem = { name: string; heat: number; growth: number };
export type TimelineRow = { year: number; nodes: number; edges: number };
export type ReportMeta = {
  id: string; title: string; date: string;
  type: string; status: string; size: string;
};

export const USER_LABELS: Record<string, string> = {
  teacher: "教师科研", student: "学生学习",
  librarian: "馆员服务", manager: "科研管理",
};

export const skwmApi = {
  health: () => get<{ ok: boolean; llm: string }>("/api/health"),
  overview: () => get<Overview>("/api/overview"),
  timeline: () => get<{ timeline: TimelineRow[] }>("/api/timeline"),
  hotspots: (user = "teacher", year?: number) =>
    get<{ year: number; hotspots: HotItem[]; active_context_dims: string[] }>(
      `/api/hotspots?user=${user}${year ? `&year=${year}` : ""}`,
    ),
  frontier: (year?: number) =>
    get<{ year: number; emerging_topics: EmergingItem[]; count: number }>(
      `/api/frontier${year ? `?year=${year}` : ""}`,
    ),
  predict: (delta = 5, year?: number) =>
    get<any>(`/api/predict?delta=${delta}${year ? `&year=${year}` : ""}`),
  graph: (entity?: string) =>
    get<any>(`/api/graph${entity ? `?entity=${encodeURIComponent(entity)}` : ""}`),
  reports: () => get<{ reports: ReportMeta[]; total: number }>("/api/reports"),
  query: (question: string, user = "teacher", context = "default") =>
    post<any>("/api/query", { question, user, context }),
  report: (topic: string, user = "librarian", opts: { push?: boolean; sediment?: boolean } = {}) =>
    post<any>("/api/report", { topic, user, sediment: opts.sediment ?? true, push: opts.push ?? false }),
  // 世界模型
  wmPredict: (year?: number, horizon?: number) =>
    get<any>(`/api/wm/predict${year ? `?year=${year}&horizon=${horizon || 5}` : ""}`),
  wmAlignment: (year?: number) =>
    get<any>(`/api/wm/alignment${year ? `?year=${year}` : ""}`),
  wmIntervene: (year?: number, concept?: string) =>
    get<any>(`/api/wm/intervene${year ? `?year=${year}&concept=${encodeURIComponent(concept || "")}` : ""}`),
};
