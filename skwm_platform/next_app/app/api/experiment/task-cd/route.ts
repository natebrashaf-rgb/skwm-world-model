const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET() {
  try {
    const response = await fetch(`${API_BASE}/api/experiment/task-cd`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ available: false, version: "v3" }, { status: 503 });
  }
}
