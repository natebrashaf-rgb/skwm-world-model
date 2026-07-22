"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { skwmApi, type Overview, type HotItem, type TimelineRow } from "@/lib/api";
import {
  TrendingUp,
  Globe2,
  GraduationCap,
  Building2,
  Network,
  LineChart,
  Sparkles,
  BarChart3,
  GitBranch,
  Layers,
} from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function CockpitPage() {
  const [err, setErr] = useState<string | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);
  const [hotspots, setHotspots] = useState<HotItem[]>([]);
  const [dims, setDims] = useState<string[]>([]);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [predictions, setPredictions] = useState<any[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [o, h, t, p] = await Promise.all([
          skwmApi.overview(),
          skwmApi.hotspots("manager"),
          skwmApi.timeline(),
          skwmApi.predict(5),
        ]);
        setOv(o);
        setHotspots(h.hotspots);
        setDims(h.active_context_dims);
        setTimeline(t.timeline);
        setPredictions(p.predictions || []);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, []);

  const maxScore = Math.max(1, ...hotspots.map((h) => h.context_score || h.heat || 0));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">领导驾驶舱</h1>
          <p className="mt-2 text-sm text-slate-600">
            科学知识世界模型 · 学科态势总览 · 语境加权 C 实时展示
          </p>
        </div>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ {err}，请运行 <code className="rounded bg-amber-100 px-1">uvicorn api:app --port 8000</code>
        </div>
      )}

      {/* SKWM 7维度状态 */}
      <div className="grid grid-cols-7 gap-3">
        {([
          ["E", "知识实体", nf(ov?.entities), "实体总量", "bg-blue-500"],
          ["R", "知识关系", nf(ov?.relations), "关系总边数", "bg-teal-500"],
          ["S", "知识状态", nf(ov?.state_vectors), "4维状态向量", "bg-emerald-500"],
          ["T", "时间序列", `${nf(ov?.snapshots)}切片`, "89年演化", "bg-amber-500"],
          ["C", "语境变量", `${dims.length}生效`, "政策/合作/学科", "bg-purple-500"],
          ["U", "用户需求", "4类型", "差异化服务", "bg-pink-500"],
          ["P", "服务规则", "4规则", "推荐/审核/推送/沉淀", "bg-indigo-500"],
        ] as const).map(([k, label, v, desc, color]) => (
          <Card key={k} className={`p-4 text-center ${color.replace("bg-", "border-t-4 border-").replace("-500", "-500")}`}>
            <div className="text-lg font-bold text-ink">{k}</div>
            <div className="mt-2 text-2xl font-semibold text-ink">{v}</div>
            <div className="mt-1 text-xs text-slate-500">{label}</div>
            <div className="mt-0.5 text-[10px] text-slate-400">{desc}</div>
          </Card>
        ))}
      </div>

      {/* 语境变量 C 详情 */}
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
            <Globe2 size={18} />
          </div>
          <h2 className="font-semibold text-ink">语境变量 C · 当前生效维度</h2>
        </div>
        <div className="mt-4 grid grid-cols-4 gap-4">
          <div className={`rounded-md border p-4 ${dims.includes("national_policy") ? "border-purple-200 bg-purple-50" : "border-slate-100 bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${dims.includes("national_policy") ? "bg-purple-500" : "bg-slate-300"}`} />
              <span className="text-sm font-medium text-ink">国家政策</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <div>一带一路（2013~）</div>
              <div>中阿合作论坛</div>
              <div>沙特2030愿景</div>
              <div>生成式AI爆发（2024~）</div>
            </div>
          </div>
          <div className={`rounded-md border p-4 ${dims.includes("regional_coop") ? "border-purple-200 bg-purple-50" : "border-slate-100 bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${dims.includes("regional_coop") ? "bg-purple-500" : "bg-slate-300"}`} />
              <span className="text-sm font-medium text-ink">区域合作</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <div>中阿文旅中心</div>
              <div>高校联盟</div>
            </div>
          </div>
          <div className={`rounded-md border p-4 ${dims.includes("school_direction") ? "border-purple-200 bg-purple-50" : "border-slate-100 bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${dims.includes("school_direction") ? "bg-purple-500" : "bg-slate-300"}`} />
              <span className="text-sm font-medium text-ink">学校学科方向</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <div>阿拉伯语</div>
              <div>旅游管理</div>
              <div>跨文化传播</div>
              <div>区域国别</div>
            </div>
          </div>
          <div className={`rounded-md border p-4 ${dims.includes("global_situation") ? "border-purple-200 bg-purple-50" : "border-slate-100 bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${dims.includes("global_situation") ? "bg-purple-500" : "bg-slate-300"}`} />
              <span className="text-sm font-medium text-ink">国际形势</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-slate-500">
              <div>中阿文明交流互鉴</div>
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-400">
          C 维度通过对知识主题加权参与热点/前沿/预测的排序，不同角色用户看到的排序不同。
        </p>
      </Card>

      {/* 热点 + 预测双栏 */}
      <div className="grid grid-cols-2 gap-6">
        {/* 热点（管理视角） */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <BarChart3 size={18} />
            </div>
            <h2 className="font-semibold text-ink">研究热点（管理视角）</h2>
          </div>
          <div className="mt-4 space-y-2">
            {hotspots.slice(0, 8).map((h, i) => (
              <div key={h.name} className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-2.5">
                <div className="flex items-center gap-3">
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${i < 3 ? "bg-navy text-white" : "bg-slate-100 text-slate-600"}`}>
                    {i + 1}
                  </span>
                  <div>
                    <div className="text-sm font-medium text-ink">{h.name}</div>
                    <div className="text-[10px] text-slate-400">
                      热度 {h.heat} · 中心度 {h.centrality}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-20">
                    <div className="h-1.5 rounded-full bg-slate-100">
                      <div
                        className="h-1.5 rounded-full bg-amber-500"
                        style={{ width: `${((h.context_score || h.heat) / maxScore) * 100}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-xs font-medium text-ink">{h.context_score ?? h.heat}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* 趋势预测 */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <TrendingUp size={18} />
            </div>
            <h2 className="font-semibold text-ink">XGBoost 趋势预测</h2>
          </div>
          <div className="mt-4 space-y-2">
            {predictions.length === 0 && (
              <p className="text-sm text-slate-500 py-8 text-center">暂无预测数据（XGBoost模型未加载）</p>
            )}
            {predictions.slice(0, 10).map((p: any, i: number) => (
              <div key={p.name} className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-2.5">
                <div className="flex items-center gap-3">
                  <span className="w-5 text-xs text-slate-400">#{i + 1}</span>
                  <span className="text-sm font-medium text-ink">{p.name}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500">{p.current_heat?.toFixed(0) || ""}</span>
                  <Badge tone={p.predicted_growth > 0 ? "green" : "slate"}>
                    → {p.predicted_heat?.toFixed(0) || ""}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-400">
            基于 89 年时间切片 × XGBoost AUC≈0.94 的 5 年预测
          </p>
        </Card>
      </div>

      {/* 年度演化 */}
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
            <LineChart size={18} />
          </div>
          <div>
            <h2 className="font-semibold text-ink">知识图谱年度演化</h2>
            <p className="text-xs text-slate-500">
              {timeline[0]?.year}–{timeline[timeline.length - 1]?.year} · 每年度节点+边数
            </p>
          </div>
        </div>
        <div className="mt-4 flex h-48 items-end gap-0.5 overflow-x-auto">
          {timeline.map((t) => {
            const maxCount = Math.max(1, ...timeline.map((x) => Math.max(x.nodes, x.edges)));
            return (
              <div
                key={t.year}
                className="flex flex-1 flex-col items-center gap-0.5 min-w-[8px]"
                title={`${t.year}: 节点${t.nodes} / 边${t.edges}`}
              >
                <div
                  className="w-full rounded-t bg-emerald-400/60 hover:bg-emerald-400 transition-colors"
                  style={{ height: `${Math.max(2, (t.nodes / maxCount) * 160)}px` }}
                />
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
