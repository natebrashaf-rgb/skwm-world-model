"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TrendingUp, LineChart, Network, Download, Eye, Calendar } from "lucide-react";

export default function ScientometricsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(2024);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/hotspots?year=${year}`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [year]);

  const total = data?.total_papers || 0;
  const hotspots = data?.hotspots || [];
  const emerging = data?.emerging_topics || [];
  const trend = data?.trend || [];
  const maxHeat = Math.max(...hotspots.map((h: any) => h.heat), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">科学计量分析</h1>
          <p className="mt-2 text-sm text-slate-600">基于 {total} 篇真实文献 · 10个技术分类</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">年份:</span>
          {[2020, 2021, 2022, 2023, 2024].map((y) => (
            <button key={y} onClick={() => setYear(y)}
              className={`rounded px-3 py-1 text-sm font-medium transition ${year === y ? "bg-navy text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`}>{y}</button>
          ))}
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5"><div className="text-sm text-slate-500">总文献量</div><div className="mt-2 text-3xl font-semibold text-ink">{total}</div><div className="mt-2 text-xs text-slate-500">10个分类</div></Card>
        <Card className="p-5"><div className="text-sm text-slate-500">当年论文</div><div className="mt-2 text-3xl font-semibold text-ink">{hotspots.reduce((a: number, h: any) => a + h.heat, 0) || 0}</div><div className="mt-2 text-xs text-slate-500">{year}年</div></Card>
        <Card className="p-5"><div className="text-sm text-slate-500">热点主题</div><div className="mt-2 text-3xl font-semibold text-ink">{hotspots.length}</div><div className="mt-2 text-xs text-slate-500">有论文产出的分类</div></Card>
        <Card className="p-5"><div className="text-sm text-slate-500">前沿方向</div><div className="mt-2 text-3xl font-semibold text-ink">{emerging.length}</div><div className="mt-2 text-xs text-emerald-600">正增长主题</div></Card>
      </div>

      {/* 热点排名 */}
      <Card className="p-5">
        <h2 className="font-semibold text-ink mb-4">{year}年 研究热点排名</h2>
        {loading ? (
          <div className="h-48 animate-pulse rounded bg-slate-200" />
        ) : hotspots.length === 0 ? (
          <p className="text-sm text-slate-500 py-8 text-center">{year}年暂无数据</p>
        ) : (
          <div className="space-y-3">
            {hotspots.map((h: any, i: number) => (
              <div key={h.topic} className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3">
                <div className="flex items-center gap-4">
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${i < 3 ? "bg-navy text-white" : "bg-slate-100 text-slate-600"}`}>{i + 1}</span>
                  <div><div className="text-sm font-medium text-ink">{h.topic}</div><div className="text-xs text-slate-500">{h.connections} 篇累计</div></div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-32"><div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-navy" style={{ width: `${(h.heat / maxHeat) * 100}%` }} /></div></div>
                  <span className="text-sm font-semibold text-ink w-8">{int(h.heat)}</span>
                  <Badge tone={h.growth > 0 ? "green" : h.growth < 0 ? "red" : "slate"}>{h.growth > 0 ? "↑" : h.growth < 0 ? "↓" : "→"} {Math.abs(h.growth * 100).toFixed(0)}%</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 年度趋势 */}
      <div className="grid grid-cols-2 gap-6">
        <Card className="p-5">
          <h2 className="font-semibold text-ink mb-4">年度发文趋势</h2>
          {trend.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">暂无趋势数据</div>
          ) : (
            <div className="space-y-2">
              {trend.filter((t: any) => t.count > 0).slice(-12).map((t: any) => (
                <div key={t.year} className="flex items-center gap-3">
                  <span className="w-10 text-xs text-slate-500">{t.year}</span>
                  <div className="flex-1 h-4 rounded bg-slate-100 overflow-hidden">
                    <div className="h-full rounded bg-gradient-to-r from-blue-400 to-navy" style={{ width: `${(t.count / Math.max(...trend.map((x: any) => x.count))) * 100}%` }} />
                  </div>
                  <span className="w-10 text-right text-xs text-slate-600">{t.count}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-ink mb-4">前沿增长主题</h2>
          {emerging.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">{year}年无可识别的前沿主题</div>
          ) : (
            <div className="space-y-3">
              {emerging.map((e: any) => (
                <div key={e.topic} className="flex items-center justify-between rounded-md bg-emerald-50 px-4 py-3">
                  <span className="text-sm font-medium text-emerald-800">{e.topic}</span>
                  <Badge tone="green">+{(e.growth * 100).toFixed(1)}%</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function int(v: number) { return Math.round(v); }
