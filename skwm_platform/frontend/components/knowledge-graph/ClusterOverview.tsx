"use client";

import { Card } from "@/components/ui/Card";

type Cluster = {
  type: string;
  count: number;
  avg_heat: number;
  top_entities: string[];
  year: string;
};

type Props = {
  clusters: Cluster[];
  totalEntities: number;
  libraryTotal: number;
  libraryEdgesRaw: number;
  libraryEdgesUnique: number;
  libraryYears: number[];
  onClusterClick: (clusterType: string) => void;
};

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  "主题": { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700" },
  "机构": { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700" },
  "地点": { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700" },
  "政策": { bg: "bg-purple-50", border: "border-purple-200", text: "text-purple-700" },
  "项目": { bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-700" },
  "事件": { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-700" },
  "术语": { bg: "bg-cyan-50", border: "border-cyan-200", text: "text-cyan-700" },
  "作者": { bg: "bg-pink-50", border: "border-pink-200", text: "text-pink-700" },
  "文献": { bg: "bg-indigo-50", border: "border-indigo-200", text: "text-indigo-700" },
  "未分类": { bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-500" },
};

const TYPE_ICONS: Record<string, string> = {
  "主题": "📚", "机构": "🏛️", "地点": "📍", "政策": "📋",
  "项目": "📐", "事件": "🗓️", "术语": "🏷️", "作者": "👤",
  "文献": "📄", "未分类": "❓",
};

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function ClusterOverview({ clusters, totalEntities, libraryTotal, libraryEdgesRaw, libraryEdgesUnique, libraryYears, onClusterClick }: Props) {
  const maxCount = Math.max(...clusters.map((c) => c.count), 1);

  return (
    <div>
      {/* 全库大数字 Hero */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <Card className="flex flex-col items-center justify-center p-6 text-center">
          <div className="text-3xl font-bold text-navy">{nf(libraryTotal)}</div>
          <div className="mt-1 text-xs text-slate-500">状态向量 (89年累计·含跨年重复)</div>
          <div className="mt-0.5 text-[10px] text-slate-400">唯一实体: {nf(totalEntities)}</div>
        </Card>
        <Card className="flex flex-col items-center justify-center p-6 text-center">
          <div className="text-3xl font-bold text-purple-700">{nf(libraryEdgesRaw)}</div>
          <div className="mt-1 text-xs text-slate-500">边总次数 (89年累计)</div>
          <div className="mt-0.5 text-[10px] text-slate-400">唯一边: {nf(libraryEdgesUnique)}</div>
        </Card>
        <Card className="flex flex-col items-center justify-center p-6 text-center">
          <div className="text-3xl font-bold text-emerald-700">{libraryYears[0]}~{libraryYears[1]}</div>
          <div className="mt-1 text-xs text-slate-500">时间跨度 (年度切片)</div>
        </Card>
      </div>

      <div className="mb-4 flex items-baseline gap-3">
        <h2 className="text-lg font-semibold text-ink">实体类型分布</h2>
        <span className="text-sm text-slate-500">
          {totalEntities} 实体 · {clusters.length} 种类型 · 点击类型查看关系图
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {clusters.map((cluster) => {
          const colors = TYPE_COLORS[cluster.type] ?? TYPE_COLORS["未分类"];
          const icon = TYPE_ICONS[cluster.type] ?? "❓";
          const scale = cluster.count / maxCount;

          return (
            <button
              key={cluster.type}
              onClick={() => onClusterClick(cluster.type)}
              className={`group relative overflow-hidden rounded-xl border-2 p-4 text-left transition-all hover:shadow-md hover:-translate-y-0.5 ${colors.bg} ${colors.border}`}
            >
              <div
                className="absolute -right-4 -top-4 rounded-full opacity-10 transition-all group-hover:opacity-20"
                style={{
                  width: `${40 + scale * 80}px`,
                  height: `${40 + scale * 80}px`,
                  backgroundColor: colors.text.replace("text-", ""),
                }}
              />
              <div className="relative">
                <div className="mb-1 text-lg">{icon}</div>
                <div className="text-sm font-medium text-ink">{cluster.type}</div>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="text-2xl font-bold text-ink">{cluster.count}</span>
                  <span className="text-xs text-slate-500">唯一</span>
                </div>
                {/* 累计总量条 */}
                <div className="mt-1.5 flex items-center gap-1.5">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, (cluster.count / libraryTotal) * 10000)}%`,
                        backgroundColor: colors.text.replace("text-", ""),
                      }}
                    />
                  </div>
                  <span className="text-[9px] text-slate-400">总{nf(libraryTotal)}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {cluster.top_entities.slice(0, 3).map((e) => (
                    <span key={e} className="truncate rounded bg-white/60 px-1.5 py-0.5 text-[10px] text-slate-600">{e}</span>
                  ))}
                </div>
                <div className="mt-1.5 text-[10px] text-slate-400">均热度 {cluster.avg_heat.toFixed(1)}</div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
