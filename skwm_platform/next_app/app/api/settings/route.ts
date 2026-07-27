// app/api/settings/route.ts — 系统设置真实状态

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET() {
  try {
    const r = await fetch(`${API_BASE}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    const h = await r.json();
    const d = await fetch(`${API_BASE}/api/dashboard`, { signal: AbortSignal.timeout(5000) }).then(r => r.json());

    return Response.json({
      data_source: h.data_source || "未知",
      year_range: h.year_range || [],
      algorithm: h.algorithm || "未知",
      total_papers: d.total_papers || 0,
      categories: d.categories || 0,
      category_count: Object.keys(d.category_stats || {}).length,
      rng_mode: "规则模式（无LLM Key）",
      graphrag_mode: "待接入",
      last_update: new Date().toISOString().split("T")[0],
    });
  } catch {
    return Response.json(fallback());
  }
}

function fallback() {
  return {
    data_source: "文献资料库（降级）",
    year_range: [2000, 2026],
    algorithm: "propose→simulate→revise",
    total_papers: 1958,
    categories: 10,
    category_count: 10,
    rng_mode: "规则模式",
    graphrag_mode: "未连接",
    last_update: new Date().toISOString().split("T")[0],
  };
}
