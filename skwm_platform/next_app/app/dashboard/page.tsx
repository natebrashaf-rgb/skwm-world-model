"use client";

import { useEffect, useState } from "react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { RecentReports } from "@/components/dashboard/RecentReports";
import { QuickEntries } from "@/components/dashboard/QuickEntries";
import { ModelStats } from "@/components/dashboard/ModelStats";
import { MetricSkeleton, CardSkeleton } from "@/components/ui/Skeleton";
import { BookOpen, FileText, Users, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const reports = [
    { id: "1", title: "近五年中阿文化遗产旅游研究热点分析", createdAt: "2026-07-12", type: "教师课题" },
    { id: "2", title: "阿拉伯国家数字文旅传播选题建议", createdAt: "2026-07-11", type: "学生选题" },
    { id: "3", title: "第28周中阿文旅学科服务周报", createdAt: "2026-07-10", type: "学科周报" },
    { id: "4", title: "中阿文旅研究优势与潜在合作机构分析", createdAt: "2026-07-09", type: "科研管理" },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <div><div className="h-7 w-72 animate-pulse rounded bg-slate-200" /><div className="mt-2 h-4 w-96 animate-pulse rounded bg-slate-200" /></div>
        <div className="grid grid-cols-4 gap-4"><MetricSkeleton /><MetricSkeleton /><MetricSkeleton /><MetricSkeleton /></div>
        <CardSkeleton /><div className="grid grid-cols-2 gap-4"><CardSkeleton /><CardSkeleton /></div>
      </div>
    );
  }

  const stats = data?.category_stats || {};
  const total = data?.total_papers || 0;
  const cats = Object.entries(stats).length;
  const topCats = Object.entries(stats).sort((a: any, b: any) => b[1].total - a[1].total).slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">中阿文旅智能学科服务 · 工作台</h1>
        <p className="mt-2 text-sm text-slate-600">基于真实文献 · 共 {total} 篇 · {cats} 个分类</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="文献总量" value={total} helper="10个分类·2000-2026" icon={<BookOpen size={24} />} />
        <MetricCard label="知识分类" value={cats} helper="SKWM·KG·GraphRAG·Agent..." icon={<Users size={24} />} />
        <MetricCard label="前沿主题" value={data?.trend?.filter((t: any) => t.count > 0).length || 0} helper="有论文产出的年份" icon={<TrendingUp size={24} />} />
        <MetricCard label="年代跨度" value={`${data?.year_range?.[0] || 2000}-${data?.year_range?.[1] || 2026}`} helper="26年文献积累" icon={<FileText size={24} />} />
      </div>

      <ModelStats />

      <QuickEntries />

      <div className="grid grid-cols-[1.3fr_1fr] gap-6">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
          <h2 className="font-semibold text-ink">热门分类 Top 5</h2>
          <div className="mt-4 space-y-3">
            {topCats.map(([name, s]: any) => (
              <div key={name} className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex justify-between text-sm"><span className="text-ink font-medium">{name}</span><span className="text-slate-500">{s.total}篇</span></div>
                  <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-navy" style={{ width: `${(s.total / Math.max(...topCats.map((c: any) => c[1].total))) * 100}%` }} /></div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <RecentReports reports={reports} />
      </div>
    </div>
  );
}
