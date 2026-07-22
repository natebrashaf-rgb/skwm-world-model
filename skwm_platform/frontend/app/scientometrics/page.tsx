"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  skwmApi,
  USER_LABELS,
  type HotItem,
  type EmergingItem,
  type Overview,
  type TimelineRow,
} from "@/lib/api";
import { TrendingUp, Network, LineChart, Download, Globe2, Users, Building2 } from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function ScientometricsPage() {
  const [view, setView] = useState<"hotspot" | "trend" | "emerging" | "sciencemap">("hotspot");
  const [user, setUser] = useState("teacher");
  const [ov, setOv] = useState<Overview | null>(null);
  const [hotspots, setHotspots] = useState<HotItem[]>([]);
  const [dims, setDims] = useState<string[]>([]);
  const [emerging, setEmerging] = useState<EmergingItem[]>([]);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // 科学地图数据
  const [entityTypes, setEntityTypes] = useState<{ type: string; count: number }[]>([]);
  const [collabStats, setCollabStats] = useState<{ total_edges: number } | null>(null);
  const [ptrends, setPtrends] = useState<{ year: number; nodes: number; edges: number }[]>([]);
  const [institutions, setInstitutions] = useState<any[]>([]);
  const [authors, setAuthors] = useState<any[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [o, f, t, et, pt, c, instRes, authRes] = await Promise.all([
          skwmApi.overview(),
          skwmApi.frontier(),
          skwmApi.timeline(),
          skwmApi.entityTypeDistribution(),
          skwmApi.publicationTrends(),
          skwmApi.collaborationNetwork(),
          skwmApi.institutionProfiles(10),
          skwmApi.authorProfiles(10),
        ]);
        setOv(o);
        setEmerging(f.emerging_topics);
        setTimeline(t.timeline);
        setEntityTypes(et.types);
        setPtrends(pt.trends);
        setCollabStats(c);
        setInstitutions(instRes.institutions);
        setAuthors(authRes.authors);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const h = await skwmApi.hotspots(user);
        setHotspots(h.hotspots);
        setDims(h.active_context_dims);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, [user]);

  const maxScore = Math.max(
    1,
    ...hotspots.map((h) => h.context_score || h.heat || 0),
  );
  const maxNodes = Math.max(1, ...timeline.map((t) => t.nodes));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">科学计量分析</h1>
          <p className="mt-2 text-sm text-slate-600">
            中阿文旅研究热点、前沿识别与演化趋势 · 已叠加 C 语境加权
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={user}
            onChange={(e) => setUser(e.target.value)}
            className="rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-navy"
          >
            {Object.entries(USER_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}视角
              </option>
            ))}
          </select>
          <Button variant="secondary">
            <Download size={16} />
            导出报告
          </Button>
        </div>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ 后端未连接（{err}），请运行{" "}
          <code className="rounded bg-amber-100 px-1">
            uvicorn api:app --port 8000
          </code>
        </div>
      )}

      {/* 真实指标 */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="text-sm text-slate-500">知识实体</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.entities)}
          </div>
          <div className="mt-2 text-xs text-slate-500">图谱节点总量</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">当年前沿</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(emerging.length)}
          </div>
          <div className="mt-2 text-xs text-emerald-600">突现主题</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">状态向量</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.state_vectors)}
          </div>
          <div className="mt-2 text-xs text-slate-500">4维知识状态</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">时间切片</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.snapshots)}
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {ov?.year_range?.[0]}–{ov?.year_range?.[1]}
          </div>
        </Card>
      </div>

      {dims.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-500">当前生效的语境维度 C：</span>
          {dims.map((d) => (
            <Badge key={d} tone="blue">
              {d}
            </Badge>
          ))}
        </div>
      )}

      <Card className="p-0 overflow-hidden">
        <div className="flex border-b border-slate-100">
          {(
            [
              ["hotspot", "研究热点", TrendingUp],
              ["emerging", "新兴前沿", Network],
              ["trend", "年度演化", LineChart],
              ["sciencemap", "科学地图", Globe2],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition ${view === v ? "border-b-2 border-navy text-navy" : "text-slate-500 hover:text-slate-700"}`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
        <div className="p-5">
          {view === "hotspot" && (
            <div className="space-y-3">
              <h2 className="font-semibold text-ink">
                语境加权后的热点排名（{USER_LABELS[user]}视角）
              </h2>
              {hotspots.length === 0 && (
                <p className="text-sm text-slate-500">暂无数据</p>
              )}
              {hotspots.map((h, i) => (
                <div
                  key={h.name}
                  className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${i < 3 ? "bg-navy text-white" : "bg-slate-100 text-slate-600"}`}
                    >
                      {i + 1}
                    </span>
                    <div>
                      <div className="text-sm font-medium text-ink">
                        {h.name}
                      </div>
                      <div className="text-xs text-slate-500">
                        热度 {h.heat} · 中心度 {h.centrality} · {h.connections}{" "}
                        条连接
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-32">
                      <div className="h-2 rounded-full bg-slate-100">
                        <div
                          className="h-2 rounded-full bg-navy"
                          style={{
                            width: `${Math.round(((h.context_score || h.heat) / maxScore) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                    <span className="w-14 text-right text-sm font-semibold text-ink">
                      {h.context_score ?? h.heat}
                    </span>
                    <Badge tone={h.context_weight > 1 ? "green" : "slate"}>
                      ×{h.context_weight}
                    </Badge>
                  </div>
                </div>
              ))}
              <p className="pt-1 text-xs text-slate-400">
                分值 = 基础热度 × C语境权重（国家政策/学校方向/区域合作/全球局势
                × 用户偏好）
              </p>
            </div>
          )}
          {view === "emerging" && (
            <div className="space-y-3">
              <h2 className="font-semibold text-ink">新兴前沿（按增速排序）</h2>
              {emerging.length === 0 && (
                <p className="text-sm text-slate-500">暂无数据</p>
              )}
              {emerging.map((e, i) => (
                <div
                  key={e.name}
                  className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400">#{i + 1}</span>
                    <span className="text-sm font-medium text-ink">
                      {e.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-slate-500">热度 {e.heat}</span>
                    <Badge tone="green">↑ 增速 {e.growth}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
          {view === "trend" && (
            <div className="space-y-3">
              <h2 className="font-semibold text-ink">
                年度知识图谱规模演化（真实 per-year 节点数）
              </h2>
              <div className="flex h-56 items-end gap-1 overflow-x-auto pt-4">
                {timeline.map((t) => (
                  <div
                    key={t.year}
                    className="flex min-w-[10px] flex-1 flex-col items-center gap-1"
                    title={`${t.year}: ${t.nodes} 节点 / ${t.edges} 边`}
                  >
                    <div
                      className="w-full rounded-t bg-navy/70 hover:bg-navy"
                      style={{
                        height: `${Math.max(2, (t.nodes / maxNodes) * 180)}px`,
                      }}
                    />
                  </div>
                ))}
              </div>
              <p className="text-xs text-slate-400">
                共 {timeline.length} 个年度切片（{timeline[0]?.year}–
                {timeline[timeline.length - 1]?.year}），悬停查看具体节点/边数。
              </p>
            </div>
          )}
          {view === "sciencemap" && (
            <div className="space-y-6">
              {/* 实体类型分布 */}
              <div>
                <h2 className="font-semibold text-ink flex items-center gap-2">
                  <Globe2 size={18} className="text-teal-500" />
                  实体类型分布（E: 9类知识实体）
                </h2>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {entityTypes.map((et) => {
                    const maxCount = Math.max(1, ...entityTypes.map((x) => x.count));
                    const pct = Math.round((et.count / maxCount) * 100);
                    return (
                      <div key={et.type} className="rounded-md border border-slate-100 bg-white p-4">
                        <div className="text-sm font-medium text-ink">{et.type}</div>
                        <div className="mt-2 flex items-baseline gap-1">
                          <span className="text-2xl font-bold text-navy">{et.count.toLocaleString()}</span>
                          <span className="text-xs text-slate-400">个实体</span>
                        </div>
                        <div className="mt-2 h-1.5 w-full rounded-full bg-slate-100">
                          <div className="h-1.5 rounded-full bg-teal-500" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 合作网络统计 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-md border border-slate-100 bg-white p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <Users size={16} className="text-blue-500" />
                    共现关系总量
                  </h3>
                  <div className="mt-2 text-3xl font-bold text-navy">
                    {collabStats?.total_edges?.toLocaleString() || "—"}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">2026年切片内边数</div>
                </div>
                <div className="rounded-md border border-slate-100 bg-white p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <LineChart size={16} className="text-emerald-500" />
                    年度发文总览
                  </h3>
                  <div className="mt-2 text-3xl font-bold text-navy">{ptrends.length}</div>
                  <div className="mt-1 text-xs text-slate-400">年度切片数（{ptrends[0]?.year}–{ptrends[ptrends.length - 1]?.year}）</div>
                </div>
              </div>

              {/* 年度发文趋势柱状图 */}
              <div>
                <h3 className="text-sm font-semibold text-ink mb-3">年度知识规模趋势</h3>
                <div className="flex h-40 items-end gap-0.5 overflow-x-auto">
                  {ptrends.map((t) => {
                    const maxV = Math.max(1, ...ptrends.map((x) => Math.max(x.nodes, x.edges)));
                    return (
                      <div key={t.year} className="flex flex-1 flex-col items-center min-w-[6px]" title={`${t.year}: ${t.nodes}节点 / ${t.edges}边`}>
                        <div className="w-full rounded-t bg-blue-400/50 hover:bg-blue-400 transition-colors"
                          style={{ height: `${Math.max(2, (t.nodes / maxV) * 140)}px` }}
                        />
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-slate-400">每年度节点数（蓝色柱），悬停查看具体值</p>
              </div>

              {/* 机构画像 + 作者画像 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-md border border-slate-100 bg-white p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-ink mb-3">
                    <Building2 size={16} className="text-amber-500" />
                    机构画像（{institutions.length}个活跃机构）
                  </h3>
                  {institutions.length === 0 && <p className="text-xs text-slate-400">暂无机构数据</p>}
                  {institutions.slice(0, 8).map((inst, i) => (
                    <div key={inst.name} className="flex items-center justify-between py-1.5 text-xs border-b border-slate-50 last:border-0">
                      <span className="text-slate-700 truncate max-w-[140px]">{inst.name}</span>
                      <span className="text-slate-500">热度 {inst.heat} · {inst.years_active}年活跃</span>
                    </div>
                  ))}
                </div>
                <div className="rounded-md border border-slate-100 bg-white p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-ink mb-3">
                    <Users size={16} className="text-blue-500" />
                    作者画像（共{authors.length}位有合作记录）
                  </h3>
                  {authors.length === 0 && <p className="text-xs text-slate-400">暂无作者数据</p>}
                  {authors.slice(0, 8).map((auth, i) => (
                    <div key={auth.name} className="flex items-center justify-between py-1.5 text-xs border-b border-slate-50 last:border-0">
                      <span className="text-slate-700">{auth.name}</span>
                      <span className="text-blue-600 font-medium">{auth.collab_count} 次合作</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
