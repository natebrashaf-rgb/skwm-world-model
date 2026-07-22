"use client";

import { useEffect, useState } from "react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { RecentReports } from "@/components/dashboard/RecentReports";
import { QuickEntries } from "@/components/dashboard/QuickEntries";
import { MetricSkeleton, CardSkeleton } from "@/components/ui/Skeleton";
import { skwmApi, type Overview, type ReportMeta } from "@/lib/api";
import { Boxes, GitBranch, Layers, TrendingUp } from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);
  const [frontier, setFrontier] = useState<number>(0);
  const [reports, setReports] = useState<ReportMeta[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [o, f, r] = await Promise.all([
          skwmApi.overview(),
          skwmApi.frontier(),
          skwmApi.reports(),
        ]);
        setOv(o);
        setFrontier(f.count);
        setReports(r.reports);
      } catch (e: any) {
        setErr(e?.message || "无法连接后端 API");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-7 w-72 animate-pulse rounded bg-slate-200" />
          <div className="mt-2 h-4 w-96 animate-pulse rounded bg-slate-200" />
        </div>
        <div className="grid grid-cols-4 gap-4">
          <MetricSkeleton />
          <MetricSkeleton />
          <MetricSkeleton />
          <MetricSkeleton />
        </div>
        <CardSkeleton />
        <div className="grid grid-cols-2 gap-4">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">
          中阿文旅智能学科服务 · 工作台
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          科学知识世界模型 (SKWM) 驱动 · 知识图谱 + GraphRAG + 大模型智能体
        </p>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ 未能连接后端世界模型服务（{err}）。请先在后端目录运行
          <code className="mx-1 rounded bg-amber-100 px-1">
            uvicorn api:app --port 8000
          </code>
          ，页面数据均来自真实世界模型。
        </div>
      )}

      {/* 真实指标（来自 /api/overview + /api/frontier）*/}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="知识实体 E"
          value={nf(ov?.entities)}
          helper="图谱节点总量（年×节点）"
          icon={<Boxes size={24} />}
        />
        <MetricCard
          label="知识关系 R"
          value={nf(ov?.relations)}
          helper="共现/共引/合作边总量"
          icon={<GitBranch size={24} />}
        />
        <MetricCard
          label="状态向量 S"
          value={nf(ov?.state_vectors)}
          helper="4维[热度/增速/中心度/连接数]"
          icon={<Layers size={24} />}
        />
        <MetricCard
          label="前沿主题 T"
          value={nf(frontier)}
          helper="当年突现（增速>0）主题"
          icon={<TrendingUp size={24} />}
        />
      </div>

      {/* SKWM 世界模型状态（内联，替代原 ModelStats 写死数据）*/}
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-ink">SKWM 世界模型状态</h2>
          <span className="text-xs text-slate-500">
            时间跨度 {ov?.year_range?.[0]}–{ov?.year_range?.[1]} ·{" "}
            {nf(ov?.snapshots)} 个年度切片
          </span>
        </div>
        <div className="mt-4 grid grid-cols-4 gap-4 text-center">
          {[
            { k: "E 实体", v: nf(ov?.entities) },
            { k: "R 关系", v: nf(ov?.relations) },
            { k: "S 状态向量", v: nf(ov?.state_vectors) },
            { k: "T 时间切片", v: nf(ov?.snapshots) },
          ].map((x) => (
            <div key={x.k} className="rounded-md bg-slate-50 py-4">
              <div className="text-2xl font-semibold text-navy">{x.v}</div>
              <div className="mt-1 text-xs text-slate-500">{x.k}</div>
            </div>
          ))}
        </div>
      </div>

      <QuickEntries />

      <div className="grid grid-cols-[1.3fr_1fr] gap-6">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
          <h2 className="font-semibold text-ink">系统架构总览</h2>
          <div className="mt-4 space-y-2">
            {[
              {
                layer: "应用服务层",
                desc: "飞书机器人 · Web门户 · 馆员工作台 · Obsidian",
                color: "bg-blue-500",
              },
              {
                layer: "智能体服务层",
                desc: "总控 · 文献 · 计量 · 图谱 · 报告智能体（已接 api.py）",
                color: "bg-teal-500",
              },
              {
                layer: "智能分析层",
                desc: "科学计量 · 前沿识别 · 主题演化 · XGBoost预测",
                color: "bg-emerald-500",
              },
              {
                layer: "知识组织层",
                desc: "术语库 · 本体 · 实体关系 · 知识图谱 · 引文网络",
                color: "bg-amber-500",
              },
              {
                layer: "数据资源层",
                desc: "中文 · 阿文 · 英文文献 · 政策 · 馆藏",
                color: "bg-slate-500",
              },
            ].map((l) => (
              <div key={l.layer} className="flex items-start gap-3">
                <div
                  className={`mt-1 h-3 w-3 shrink-0 rounded-full ${l.color}`}
                />
                <div>
                  <div className="text-sm font-medium text-ink">{l.layer}</div>
                  <div className="text-xs text-slate-500">{l.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <RecentReports
          reports={reports.map((r) => ({
            id: r.id,
            title: r.title,
            createdAt: r.date || "已沉淀",
            type: r.type,
          }))}
        />
      </div>
    </div>
  );
}
