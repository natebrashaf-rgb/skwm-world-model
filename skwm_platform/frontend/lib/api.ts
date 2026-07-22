// lib/api.ts —— 前端统一请求封装（放到 skwm-platform/lib/api.ts）
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
  entities: number;
  relations: number;
  state_vectors: number;
  snapshots: number;
  year_range: [number, number];
};
export type HotItem = {
  name: string;
  heat: number;
  growth: number;
  centrality: number;
  connections: number;
  context_weight: number;
  context_score: number;
};
export type EmergingItem = { name: string; heat: number; growth: number };
export type TimelineRow = { year: number; nodes: number; edges: number };
export type ReportMeta = {
  id: string;
  title: string;
  date: string;
  type: string;
  status: string;
  size: string;
};

export const USER_LABELS: Record<string, string> = {
  teacher: "教师科研",
  student: "学生学习",
  librarian: "馆员服务",
  manager: "科研管理",
};

export const skwmApi = {
  health: () => get<{ ok: boolean; llm: string }>("/api/health"),
  overview: () => get<Overview>("/api/overview"),
  timeline: () => get<{ timeline: TimelineRow[] }>("/api/timeline"),
  graphData: (year?: number, limit = 500, minHeat = 0, lang = "zh") =>
    get<any>(
      `/api/graph-data?limit=${limit}&min_heat=${minHeat}&lang=${lang}${year ? `&year=${year}` : ""}`,
    ),
  graphClusters: (lang = "zh", year?: number) =>
    get<{ year: string; clusters: any[]; total_entities: number; total_types: number; library_total: number; library_edges_raw: number; library_edges_unique: number; library_years: number[] }>(
      `/api/graph-clusters?lang=${lang}${year !== undefined ? `&year=${year}` : ""}`,
    ),
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
    get<any>(
      `/api/graph${entity ? `?entity=${encodeURIComponent(entity)}` : ""}`,
    ),
  reports: () => get<{ reports: ReportMeta[]; total: number }>("/api/reports"),
  query: (question: string, user = "teacher", context = "default") =>
    post<any>("/api/query", { question, user, context }),
  report: (
    topic: string,
    user = "librarian",
    opts: { push?: boolean; sediment?: boolean } = {},
  ) =>
    post<any>("/api/report", {
      topic,
      user,
      sediment: opts.sediment ?? true,
      push: opts.push ?? false,
    }),

  // ── 阿文智能体（策划案第72条） ──────────────────────
  arabicDetect: (text: string) =>
    get<any>(`/api/arabic/detect?text=${encodeURIComponent(text)}`),
  arabicTranslate: (term: string, source = "auto", target = "cn") =>
    get<any>(`/api/arabic/translate?term=${encodeURIComponent(term)}&source_lang=${source}&target_lang=${target}`),
  arabicEntity: (entity: string) =>
    get<any>(`/api/arabic/entity?entity=${encodeURIComponent(entity)}`),
  arabicAlign: (terms: string[], source = "auto", target = "cn") =>
    post<any>("/api/arabic/align", { terms, source_lang: source, target_lang: target }),

  // ── 科学地图（第四阶段） ────────────────────────────
  publicationTrends: () =>
    get<{ trends: { year: number; nodes: number; edges: number }[]; total_years: number; year_range: number[] }>("/api/science-map/publication-trends"),
  entityTypeDistribution: (year?: number) =>
    get<{ year: number; types: { type: string; count: number; avg_heat: number }[]; total_entities: number }>(`/api/science-map/entity-types${year ? `?year=${year}` : ""}`),
  collaborationNetwork: (year?: number) =>
    get<any>(`/api/science-map/collaboration${year ? `?year=${year}` : ""}`),

  // ── GraphRAG 智能问答 ──────────────────────────────
  queryKg: (question: string, user = "teacher") =>
    post<any>("/api/query/kg", { question, user }),

  // ── 机构/作者画像（第三层） ────────────────────────
  institutionProfiles: (topK = 20) =>
    get<{ institutions: { name: string; heat: number; centrality: number; connections: number; years_active: number }[]; total: number }>(`/api/profiles/institutions?top_k=${topK}`),
  authorProfiles: (topK = 20) =>
    get<{ authors: { name: string; collab_count: number }[]; total: number; total_collaborations: number }>(`/api/profiles/authors?top_k=${topK}`),
};
