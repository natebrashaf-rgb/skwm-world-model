"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { BookOpen, Search, RefreshCw, FileText, ExternalLink, Upload, BarChart3 } from "lucide-react";

export default function LiteraturePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/literature")
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">文献管理</h1>
          <p className="mt-2 text-sm text-slate-600">中阿文旅多语种文献资源库 · 来自文献资料库</p>
        </div>
        <Badge tone="blue" className="text-sm px-3 py-1.5">{data?.total || 0} 篇</Badge>
      </div>

      {loading ? (
        <div className="space-y-4"><div className="h-28 animate-pulse rounded bg-slate-200" /><div className="grid grid-cols-3 gap-4"><div className="h-20 animate-pulse rounded bg-slate-200" /><div className="h-20 animate-pulse rounded bg-slate-200" /><div className="h-20 animate-pulse rounded bg-slate-200" /></div></div>
      ) : !data ? (
        <Card className="p-8 text-center text-sm text-slate-500">加载失败</Card>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4">
            <Card className="p-5"><div className="text-sm text-slate-500">论文总数</div><div className="mt-2 text-3xl font-semibold text-ink">{data.total}</div><div className="mt-2 text-xs text-slate-500">10个技术分类</div></Card>
            <Card className="p-5"><div className="text-sm text-slate-500">分类数</div><div className="mt-2 text-3xl font-semibold text-ink">{data.categories?.length || 0}</div><div className="mt-2 text-xs text-slate-500">含中阿文旅延伸</div></Card>
            <Card className="p-5"><div className="text-sm text-slate-500">时间跨度</div><div className="mt-2 text-3xl font-semibold text-ink">{data.yearly?.length || 0}年</div><div className="mt-2 text-xs text-slate-500">2000-2026</div></Card>
            <Card className="p-5"><div className="text-sm text-slate-500">最高引分类</div><div className="mt-2 text-3xl font-semibold text-ink">{data.categories?.[0]?.name?.slice(0, 6) || ""}</div><div className="mt-2 text-xs text-slate-500">{data.categories?.[0]?.total || 0}篇</div></Card>
          </div>

          {/* 分类分布 */}
          <Card className="p-5">
            <h2 className="font-semibold text-ink mb-4">分类文献分布</h2>
            <div className="space-y-3">
              {data.categories?.slice(0, 10).map((c: any) => {
                const maxT = Math.max(...data.categories.map((x: any) => x.total), 1);
                return (
                  <div key={c.id} className="flex items-center gap-4">
                    <span className="w-48 text-sm font-medium text-ink truncate">{c.name}</span>
                    <div className="flex-1 h-5 rounded bg-slate-100 overflow-hidden">
                      <div className="h-full rounded bg-navy" style={{ width: `${(c.total / maxT) * 100}%` }} />
                    </div>
                    <span className="w-16 text-right text-sm text-slate-600">{c.total}篇</span>
                    <span className="w-20 text-right text-xs text-slate-400">均引{c.avg_cites}</span>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* 年度分布 */}
          <Card className="p-5">
            <h2 className="font-semibold text-ink mb-4">年度发文分布</h2>
            <div className="grid grid-cols-10 gap-2">
              {data.yearly?.slice(-10).map((y: any) => (
                <div key={y.year} className="text-center">
                  <div className="flex items-end justify-center h-24">
                    <div className="w-full rounded-t bg-blue-500" style={{ height: `${(y.count / Math.max(...data.yearly.map((x: any) => x.count))) * 100}%`, minHeight: y.count > 0 ? 4 : 0 }} />
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{y.year}</div>
                  <div className="text-xs font-medium">{y.count}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* 最近文献 */}
          <Card className="p-5">
            <h2 className="font-semibold text-ink mb-4">最近文献</h2>
            <div className="divide-y divide-slate-100">
              {data.recent?.slice(0, 10).map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <FileText size={14} className="shrink-0 text-slate-400" />
                    <div className="min-w-0"><div className="text-sm text-ink truncate">{p.title}</div><div className="text-xs text-slate-500">{p.journal} · {p.year}</div></div>
                  </div>
                  <Badge tone="slate">{p.citations}次</Badge>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
