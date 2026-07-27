// app/api/literature/route.ts

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET() {
  try {
    const r = await fetch(`${API_BASE}/api/literature`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    return Response.json(await r.json());
  } catch {
    return Response.json({ total: 0, categories: [], recent: [], yearly: [] });
  }
}
