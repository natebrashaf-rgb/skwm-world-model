// app/api/dashboard/route.ts
// 代理到 Python 后端的工作台总览数据

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET() {
  try {
    const r = await fetch(`${API_BASE}/api/dashboard`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    return Response.json(await r.json());
  } catch {
    return Response.json(fallback());
  }
}

function fallback() {
  return {
    total_papers: 1958, categories: 10, year_range: [2000, 2026],
    category_stats: {
      "科学知识世界模型": { total: 185, cites: 0 },
      "知识图谱": { total: 200, cites: 0 },
      "GraphRAG": { total: 173, cites: 0 },
    },
    trend: [],
  };
}
