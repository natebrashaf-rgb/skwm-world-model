"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi, USER_LABELS, type ReportMeta } from "@/lib/api";
import {
  FileText,
  Download,
  Search,
  Eye,
  ArrowUpDown,
  Plus,
  Loader2,
} from "lucide-react";

const typeColors: Record<string, BadgeTone> = {
  教师科研: "blue",
  学生学习: "purple",
  馆员服务: "emerald",
  科研管理: "amber",
};

export default function ReportsPage() {
  const [search, setSearch] = useState("");
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [topic, setTopic] = useState("中阿文旅");
  const [user, setUser] = useState("librarian");

  async function refresh() {
    try {
      const r = await skwmApi.reports();
      setReports(r.reports);
    } catch (e: any) {
      setErr(e?.message || "后端未连接");
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function generate() {
    setGenerating(true);
    try {
      await skwmApi.report(topic, user, { sediment: true });
      await refresh();
    } catch (e: any) {
      setErr(e?.message || "生成失败");
    } finally {
      setGenerating(false);
    }
  }

  const filtered = reports.filter((r) => r.title.includes(search));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">报告中心</h1>
          <p className="mt-2 text-sm text-slate-600">
            由 P 服务规则链路生成并沉淀（审核 → 推送 → Obsidian 沉淀）
          </p>
        </div>
        <Badge tone="blue" className="text-sm px-3 py-1.5">
          共 {reports.length} 份报告
        </Badge>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ 后端未连接（{err}），请运行{" "}
          <code className="rounded bg-amber-100 px-1">
            uvicorn api:app --port 8000
          </code>
        </div>
      )}

      {/* 生成新报告（真实调用 P 链路）*/}
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="报告主题"
            className="flex-1 rounded-md border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-navy"
          />
          <select
            value={user}
            onChange={(e) => setUser(e.target.value)}
            className="rounded-md border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-navy"
          >
            {Object.entries(USER_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <Button onClick={generate} disabled={generating}>
            {generating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Plus size={16} />
            )}
            {generating ? "生成中…" : "生成报告"}
          </Button>
        </div>
      </Card>

      <Card className="p-5">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索报告标题..."
            className="w-full rounded-md border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-navy"
          />
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-5 py-3 font-medium">
                <div className="flex items-center gap-1">
                  报告名称 <ArrowUpDown size={12} />
                </div>
              </th>
              <th className="px-4 py-3 font-medium">类型</th>
              <th className="px-4 py-3 font-medium">日期</th>
              <th className="px-4 py-3 font-medium">大小</th>
              <th className="px-4 py-3 font-medium">状态</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-5 py-8 text-center text-sm text-slate-500"
                >
                  暂无报告，点击上方“生成报告”开始
                </td>
              </tr>
            )}
            {filtered.map((report) => (
              <tr key={report.id} className="hover:bg-slate-50">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <FileText size={16} className="text-slate-400" />
                    <span className="font-medium text-ink">{report.title}</span>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <Badge tone={typeColors[report.type] || "slate"}>
                    {report.type}
                  </Badge>
                </td>
                <td className="px-4 py-4 text-slate-600">
                  {report.date || "—"}
                </td>
                <td className="px-4 py-4 text-slate-600">{report.size}</td>
                <td className="px-4 py-4">
                  <Badge tone="green">{report.status}</Badge>
                </td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    <button className="rounded p-1 text-slate-400 hover:text-navy">
                      <Eye size={16} />
                    </button>
                    <button className="rounded p-1 text-slate-400 hover:text-navy">
                      <Download size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
