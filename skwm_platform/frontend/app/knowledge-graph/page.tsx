"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi } from "@/lib/api";
import GraphVisualization, { type GraphData } from "@/components/knowledge-graph/GraphVisualization";
import ClusterOverview from "@/components/knowledge-graph/ClusterOverview";
import {
  Search, Network, Boxes, GitBranch, Layers, TrendingUp,
  SlidersHorizontal, RotateCcw, Layers as StackIcon,
  ZoomIn, ZoomOut,
} from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

type ViewMode = "overview" | "detail";

export default function KnowledgeGraphPage() {
  const [search, setSearch] = useState("");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [nodeLimit, setNodeLimit] = useState(500);
  const [minHeat, setMinHeat] = useState(0);
  const [lang, setLang] = useState("all");
  const [showControls, setShowControls] = useState(false);
  const [selectedNodeInfo, setSelectedNodeInfo] = useState<{ neighbors: { entity: string; relation: string }[]; count: number } | null>(null);

  // 三层模式
  const [viewMode, setViewMode] = useState<ViewMode>("overview");
  const [clusters, setClusters] = useState<any[]>([]);
  const [totalEntities, setTotalEntities] = useState(0);
  const [libraryTotal, setLibraryTotal] = useState(0);
  const [libraryEdgesRaw, setLibraryEdgesRaw] = useState(0);
  const [libraryEdgesUnique, setLibraryEdgesUnique] = useState(0);
  const [libraryYears, setLibraryYears] = useState<number[]>([1895, 2026]);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<{ year: number; nodes: number; edges: number }[]>([]);
  const [selectedYear, setSelectedYear] = useState<number>(2026);

  // ── 加载聚簇总览 ──
  useEffect(() => {
    (async () => {
      try {
        const [c, t, o] = await Promise.all([
          skwmApi.graphClusters(lang),  // 当年数据
          skwmApi.timeline(),
          skwmApi.overview(),
        ]);
        setClusters(c.clusters);
        setTotalEntities(c.total_entities);
        setLibraryTotal(c.library_total);
        setLibraryEdgesRaw(c.library_edges_raw);
        setLibraryEdgesUnique(c.library_edges_unique);
        setLibraryYears(c.library_years);
        setTimeline(t.timeline);
        if (o.year_range) setSelectedYear(o.year_range[1] ?? 2026);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, []);

  // ── 加载力导向图（切换到 detail 或切换年份/类型时） ──
  const loadDetailGraph = useCallback(async (type?: string | null, year?: number) => {
    setLoading(true);
    setErr(null);
    try {
      const y = year ?? selectedYear;
      const data = await skwmApi.graphData(y, nodeLimit, minHeat, lang);
      if (type && data.nodes) {
        data.nodes = data.nodes.filter((n: any) => n.entity_type === type);
        const ids = new Set(data.nodes.map((n: any) => n.id));
        data.edges = data.edges.filter((e: any) => ids.has(e.source) && ids.has(e.target));
        data.stats.nodes_rendered = data.nodes.length;
        data.stats.edges_rendered = data.edges.length;
      }
      setGraphData(data);
    } catch (e: any) {
      setErr(e?.message || "后端未连接");
    } finally {
      setLoading(false);
    }
  }, [nodeLimit, minHeat, lang, selectedYear]);

  // ── 点击聚簇 → 切到 detail ──
  const handleClusterClick = useCallback((type: string) => {
    setFilterType(type);
    setViewMode("detail");
    loadDetailGraph(type, selectedYear);
  }, [loadDetailGraph, selectedYear]);

  // ── 返回总览 ──
  const goToOverview = useCallback(() => {
    setViewMode("overview");
    setFilterType(null);
    setGraphData(null);
  }, []);

  // ── 年份切换 ──
  const handleYearChange = useCallback((year: number) => {
    setSelectedYear(year);
    if (viewMode === "detail") {
      loadDetailGraph(filterType, year);
    }
  }, [viewMode, filterType, loadDetailGraph]);

  async function handleNodeClick(nodeId: string) {
    try {
      const g = await skwmApi.graph(nodeId);
      setSelectedNodeInfo({ neighbors: g.neighbors || [], count: g.count || 0 });
    } catch { /* quiet */ }
  }

  async function doSearch() {
    if (!search.trim()) return;
    await handleNodeClick(search.trim());
  }

  const handleRefresh = useCallback(() => {
    if (viewMode === "detail") loadDetailGraph(filterType, selectedYear);
  }, [viewMode, filterType, selectedYear, loadDetailGraph]);

  return (
    <div className="space-y-6">
      {/* 头部 + 模式切换 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">知识图谱</h1>
          <p className="mt-2 text-sm text-slate-600">
            {viewMode === "overview"
              ? "按实体类型聚簇总览 · 点击类型查看详情关系图"
              : `力导向关系图 · ${filterType ? `筛选: ${filterType}` : `年份: ${selectedYear}`} · 支持拖拽/缩放`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={viewMode === "overview" ? "default" : "outline"} onClick={goToOverview}>
            <StackIcon size={16} />
            总览
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowControls(!showControls)}
          >
            <SlidersHorizontal size={16} />
            控制
          </Button>
        </div>
      </div>

      {/* 错误提示 */}
      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ {err}
        </div>
      )}

      {/* 年份滑块 */}
      {timeline.length > 0 && (
        <Card className="p-3">
          <div className="flex items-center gap-3">
            <span className="shrink-0 text-xs font-medium text-slate-500">年份</span>
            <input
              type="range"
              min={timeline[0]?.year ?? 1895}
              max={timeline[timeline.length - 1]?.year ?? 2026}
              value={selectedYear}
              onChange={(e) => handleYearChange(Number(e.target.value))}
              className="w-full"
            />
            <span className="shrink-0 text-sm font-semibold text-navy">{selectedYear}</span>
            {viewMode === "overview" && (
              <span className="shrink-0 text-[10px] text-slate-400">（切换年份后点击类型查看）</span>
            )}
          </div>
        </Card>
      )}

      {/* 控制面板 */}
      {showControls && (
        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">最大节点数</label>
              <select value={nodeLimit} onChange={(e) => setNodeLimit(Number(e.target.value))}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-navy">
                <option value={100}>100</option>
                <option value={300}>300</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">最低热度</label>
              <input type="range" min={0} max={0.05} step={0.001} value={minHeat}
                onChange={(e) => setMinHeat(Number(e.target.value))} className="w-28" />
              <span className="ml-2 text-xs text-slate-500">{minHeat}</span>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">语言</label>
              <select value={lang} onChange={(e) => setLang(e.target.value)}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-navy">
                <option value="zh">仅中文</option>
                <option value="en">仅英文</option>
                <option value="all">全部</option>
              </select>
            </div>
            <Button onClick={handleRefresh} disabled={loading}>
              <RotateCcw size={16} /> 刷新
            </Button>
          </div>
        </Card>
      )}

      {/* ── 模式1: 总览聚簇 ── */}
      {viewMode === "overview" && (
        <ClusterOverview
          clusters={clusters}
          totalEntities={totalEntities}
          libraryTotal={libraryTotal}
          libraryEdgesRaw={libraryEdgesRaw}
          libraryEdgesUnique={libraryEdgesUnique}
          libraryYears={libraryYears}
          onClusterClick={handleClusterClick}
        />
      )}

      {/* ── 模式2: 力导向细节图 ── */}
      {viewMode === "detail" && (
        <>
          {/* 统计卡片 */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { type: "可视节点", count: graphData?.stats?.nodes_rendered, icon: Boxes, color: "text-blue-600 bg-blue-50" },
              { type: "可视边", count: graphData?.stats?.edges_rendered, icon: GitBranch, color: "text-purple-600 bg-purple-50" },
              { type: "总实体", count: graphData?.stats?.total_entities, icon: Layers, color: "text-emerald-600 bg-emerald-50" },
              { type: filterType ? `类型: ${filterType}` : "当前年份", count: selectedYear, icon: TrendingUp, color: "text-amber-600 bg-amber-50" },
            ].map((et) => {
              const Icon = et.icon;
              return (
                <Card key={et.type} className="flex items-center gap-4 p-4">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${et.color}`}>
                    <Icon size={20} />
                  </div>
                  <div>
                    <div className="text-xl font-semibold text-ink">{typeof et.count === "number" ? nf(et.count) : et.count}</div>
                    <div className="text-xs text-slate-500">{et.type}</div>
                  </div>
                </Card>
              );
            })}
          </div>

          {/* 搜索 */}
          <Card className="p-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input type="text" value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doSearch()}
                  placeholder="输入实体名查询关联"
                  className="w-full rounded-md border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-navy" />
              </div>
              <Button onClick={doSearch}><Network size={16} />查询</Button>
              {filterType && (
                <Button variant="outline" onClick={() => { setFilterType(null); loadDetailGraph(null, selectedYear); }}>
                  清除筛选
                </Button>
              )}
            </div>
          </Card>

          {/* 图 + 侧栏 */}
          <div className="grid grid-cols-[1fr_260px] gap-6">
            <Card className="overflow-hidden p-0">
              {loading ? (
                <div className="flex h-[600px] items-center justify-center text-sm text-slate-500">
                  <div className="text-center">
                    <div className="mb-3 mx-auto h-8 w-8 animate-spin rounded-full border-2 border-navy border-t-transparent" />
                    加载知识图谱数据…
                  </div>
                </div>
              ) : graphData?.nodes?.length ? (
                <GraphVisualization data={graphData} onNodeClick={handleNodeClick} />
              ) : (
                <div className="flex h-[600px] items-center justify-center text-sm text-slate-500">
                  {filterType ? `「${filterType}」类型暂无数据` : "暂无数据，请确认后端已启动"}
                </div>
              )}
            </Card>

            {/* 侧栏 */}
            <div className="space-y-4">
              <Card className="p-3">
                <h3 className="mb-2 text-xs font-semibold text-ink">类型图例</h3>
                <div className="space-y-1.5 text-[10px] text-slate-600">
                  {[
                    ["主题", "bg-blue-400"], ["机构", "bg-emerald-400"], ["地点", "bg-amber-400"],
                    ["政策", "bg-purple-400"], ["项目", "bg-rose-400"], ["事件", "bg-orange-400"],
                    ["术语", "bg-cyan-400"], ["未分类", "bg-slate-300"],
                  ].map(([label, c]) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className={`h-2 w-4 rounded ${c}`} />
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="p-3">
                <h3 className="mb-2 text-xs font-semibold text-ink">关联查询</h3>
                {selectedNodeInfo === null ? (
                  <p className="text-[10px] text-slate-500">点击节点或搜索实体名</p>
                ) : (
                  <div>
                    <p className="mb-1.5 text-[10px] text-slate-500">共 {selectedNodeInfo.count} 个关联</p>
                    <div className="flex max-h-[300px] flex-wrap gap-1 overflow-y-auto">
                      {selectedNodeInfo.neighbors.length === 0 && (
                        <p className="text-[10px] text-slate-500">未找到关联</p>
                      )}
                      {selectedNodeInfo.neighbors.map((n) => (
                        <span key={n.entity}
                          className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                          {n.entity} <span className="text-[9px] text-slate-400">· {n.relation}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
