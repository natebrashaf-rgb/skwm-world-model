// app/api/hotspots/route.ts

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const year = searchParams.get("year") || "2024";
  try {
    const r = await fetch(`${API_BASE}/api/hotspots?year=${year}`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    return Response.json(await r.json());
  } catch {
    return Response.json({ hotspots: [], emerging_topics: [], trend: [], total_papers: 0 });
  }
}
