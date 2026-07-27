// app/api/reports/route.ts

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET() {
  try {
    const r = await fetch(`${API_BASE}/api/reports`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
    return Response.json(await r.json());
  } catch {
    return Response.json({ reports: [], total: 0 });
  }
}
