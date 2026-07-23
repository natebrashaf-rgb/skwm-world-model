// SKWM API 类型契约（所有数字必须来自后端，禁止 mock）
export interface OverviewData {
  state_vectors: number; knowledge_relations: number; snapshots: number
  latest_year_entities: number; year_range: string; latest_year: number
  sources: Record<string, string>; definitions: Record<string, string>
  note: string
}
export interface HotspotItem {
  rank: number; name: string; heat: number; growth: number
  centrality: number; connections: number
  label_zh: string; label_en: string; label_ar: string; domain: string
  definition: string
}
export interface FrontierItem {
  rank: number; name: string; growth: number; heat: number
  heat_peak: number; growth_valid: boolean
  label_zh: string; label_en: string; label_ar: string; domain: string
  definition: string
}
export interface TimelineYear {
  year: number; entities: number; entities_clean: number
  sparse: boolean; sparse_note: string
}
export interface TrendPoint { year: number; heat: number; growth: number }

const API = {
  async get<T>(path: string): Promise<T> {
    const r = await fetch(path)
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`)
    return r.json()
  },
  overview: () => API.get<OverviewData>('/api/overview'),
  hotspot: (year = '2026', topK = 20) => API.get<{hotspots: HotspotItem[]; total: number}>(`/api/hotspot?year=${year}&top_k=${topK}`),
  frontier: (year = '2026', topK = 20) => API.get<{frontier: FrontierItem[]; total: number}>(`/api/frontier?year=${year}&top_k=${topK}`),
  timeline: (start?: number, end?: number) => API.get<{timeline: TimelineYear[]}>(`/api/timeline${start ? `?start=${start}&end=${end||''}` : ''}`),
  trend: (keyword: string) => API.get<{trend: TrendPoint[]}>(`/api/trend?keyword=${encodeURIComponent(keyword)}`),
}
export default API
