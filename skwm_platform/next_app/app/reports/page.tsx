"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FileText, Search, Eye, Download, Trash2, ArrowUpDown } from "lucide-react";

type Report = { id: string; title: string; type: string; date: string; status: string; size: string; summary: string };

const typeColors: Record<string, "blue" | "purple" | "emerald" | "amber"> = {
  "教师课题": "blue", "学生选题": "purple", "学科周报": "emerald", "科研管理": "amber",
};

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("全部");
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/reports").then(r => r.json()).then(d => { setReports(d.reports || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const types = ["全部", "教师课题", "学生选题", "学科周报", "科研管理"];
  const filtered = reports.filter(r => (filter === "全部" || r.type === filter) && r.title.includes(search));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-semibold text-ink">报告中心</h1><p className="mt-2 text-sm text-slate-600">闭环规划生成的各场景服务报告</p></div>
        {!loading && <Badge tone="blue" className="text-sm px-3 py-1.5">{reports.length} 份</Badge>}
      </div>

      <Card className="p-5">
        <div className="flex items-center gap-4">
          <div className="relative flex-1"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索报告标题..." className="w-full rounded-md border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-navy" /></div>
          <div className="flex gap-2">{types.map(t => (
            <button key={t} onClick={() => setFilter(t)} className={`rounded-md px-3 py-2 text-sm font-medium transition ${filter === t ? "bg-navy text-white" : "bg-white text-slate-600 hover:bg-slate-100"}`}>{t}</button>
          ))}</div>
        </div>
      </Card>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-200" />)}</div>
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr><th className="px-5 py-3 font-medium"><div className="flex items-center gap-1">报告名称 <ArrowUpDown size={12} /></div></th><th className="px-4 py-3 font-medium">类型</th><th className="px-4 py-3 font-medium">日期</th><th className="px-4 py-3 font-medium">状态</th><th className="px-4 py-3 font-medium">操作</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3"><FileText size={16} className="shrink-0 text-slate-400" /><div><div className="font-medium text-ink">{r.title}</div><div className="text-xs text-slate-500 mt-0.5">{r.summary}</div></div></div>
                  </td>
                  <td className="px-4 py-4"><Badge tone={typeColors[r.type] || "slate"}>{r.type}</Badge></td>
                  <td className="px-4 py-4 text-slate-600">{r.date}</td>
                  <td className="px-4 py-4"><Badge tone={r.status === "已完成" ? "green" : "slate"}>{r.status}</Badge></td>
                  <td className="px-4 py-4"><div className="flex gap-2"><button className="rounded p-1 text-slate-400 hover:text-navy"><Eye size={16} /></button><button className="rounded p-1 text-slate-400 hover:text-navy"><Download size={16} /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <div className="py-12 text-center text-sm text-slate-500">暂无匹配报告</div>}
        </Card>
      )}
    </div>
  );
}
