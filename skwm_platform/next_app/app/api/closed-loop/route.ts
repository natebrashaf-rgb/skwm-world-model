// app/api/closed-loop/route.ts
// 代理到 Python 世界模型算法服务（实时计算 propose→simulate→revise）

import { NextResponse } from "next/server";

const API_BASE = process.env.WM_API_URL || "http://localhost:8001";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const user = searchParams.get("user") || "teacher";
  const M = searchParams.get("M") || "4";
  const L = searchParams.get("L") || "3";
  const B = searchParams.get("B") || "6";
  const t0 = searchParams.get("t0") || "2020";
  const T = searchParams.get("T") || "2024";

  try {
    const url = `${API_BASE}/api/closed-loop?user=${user}&M=${M}&L=${L}&B=${B}&t0=${t0}&T=${T}`;
    const r = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!r.ok) throw new Error(`后端返回 ${r.status}`);
    const data = await r.json();
    return NextResponse.json(data);
  } catch (e: any) {
    // 降级: 本地静态数据
    const fallback = getFallbackData(user);
    return NextResponse.json({
      user, fallback: true,
      error: e.message,
      ...fallback,
    });
  }
}

function getFallbackData(user: string) {
  const all: Record<string, any> = {
    teacher: { decisions: [
      { year: 2020, note: "强调: topic_14, topic_3", score: 441.17, topics: ["topic_14","topic_3","topic_10"] },
      { year: 2021, note: "强调: topic_0, topic_9",  score: 779.39, topics: ["topic_0","topic_9","topic_4"] },
      { year: 2022, note: "强调: topic_2, topic_1",  score: 671.70, topics: ["topic_2","topic_1","topic_4"] },
      { year: 2023, note: "强调: topic_6, topic_9",  score: 644.54, topics: ["topic_6","topic_9","topic_18"] },
      { year: 2024, note: "强调: topic_9, topic_11", score: 652.39, topics: ["topic_9","topic_11","topic_4"] },
    ]},
    student: { decisions: [
      { year: 2020, note: "强调: topic_14, topic_3", score: 265.60, topics: ["topic_14","topic_3","topic_10"] },
      { year: 2021, note: "强调: topic_0, topic_9",  score: 469.53, topics: ["topic_0","topic_9","topic_4"] },
      { year: 2022, note: "强调: topic_2, topic_1",  score: 404.62, topics: ["topic_2","topic_1","topic_4"] },
      { year: 2023, note: "强调: topic_6, topic_9",  score: 386.99, topics: ["topic_6","topic_9","topic_18"] },
      { year: 2024, note: "强调: topic_9, topic_11", score: 391.60, topics: ["topic_9","topic_11","topic_4"] },
    ]},
  };
  return all[user] || all["teacher"];
}
