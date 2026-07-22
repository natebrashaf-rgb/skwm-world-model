"use client";

import { useEffect, useRef, useState } from "react";
import { Network } from "vis-network";
import { DataSet } from "vis-data";

export type GraphNode = {
  id: string;
  label: string;
  value: number;
  group: number;
  heat: number;
  growth: number;
  centrality: number;
  connections: number;
  entity_type?: string;
};

export type GraphEdge = {
  source: string;
  target: string;
  label: string;
  weight: number;
};

export type GraphData = {
  year: number | string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_entities: number;
    nodes_rendered: number;
    edges_rendered: number;
    year_range: [number, number];
    real_edges_in_snapshot?: number;
  };
  library_total?: number;
};

type Props = {
  data: GraphData;
  onNodeClick?: (nodeId: string) => void;
};

// 群组颜色映射
const GROUP_COLORS: Record<number, { bg: string; border: string; highlight: string }> = {
  1: { bg: "#4A90D9", border: "#2B6CB0", highlight: "#1A365D" },
  2: { bg: "#38A169", border: "#276749", highlight: "#22543D" },
  3: { bg: "#E53E3E", border: "#C53030", highlight: "#9B2C2C" },
};

const GROUP_LABELS: Record<number, string> = {
  1: "低中心度 (≤0.33)",
  2: "中中心度 (0.33~0.66)",
  3: "高中心度 (>0.66)",
};

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function GraphVisualization({ data, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data?.nodes?.length) return;

    // 以 heat 分档确定节点大小
    const maxHeat = Math.max(...data.nodes.map((n) => n.heat), 0.01);

    // ── 聚合总量泡泡（半透明大圈，展示全库累计数） ──
    const typeCounts: Record<string, { unique: number; label: string }> = {};
    for (const n of data.nodes) {
      const t = n.entity_type || "未分类";
      if (!typeCounts[t]) typeCounts[t] = { unique: 0, label: t };
      typeCounts[t].unique++;
    }

    const ghostNodes: any[] = [];
    const types = Object.keys(typeCounts);
    types.forEach((t, i) => {
      const angle = (i / types.length) * Math.PI * 2;
      const dist = 250;
      const cx = 400 + Math.cos(angle) * dist;
      const cy = 300 + Math.sin(angle) * dist;
      ghostNodes.push({
        id: `__ghost_${t}`,
        label: `${t}\n总${nf(data.library_total ?? 0)}`,
        value: 5,
        fixed: true,
        x: cx,
        y: cy,
        shape: "circle",
        size: 80,
        color: {
          background: "rgba(99, 102, 241, 0.08)",
          border: "rgba(99, 102, 241, 0.25)",
          highlight: { background: "rgba(99, 102, 241, 0.15)", border: "rgba(99, 102, 241, 0.4)" },
        },
        font: {
          color: "#6366f1",
          size: 18,
          face: "system-ui, -apple-system, sans-serif",
          strokeWidth: 0,
          multi: "md",
          align: "center",
        },
        borderWidth: 2,
        opacity: 0.6,
      });
    });

    const realNodes = new DataSet(
      data.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        value: (n.heat / maxHeat) * 60 + 10, // 节点大小 10~70
        title: `<div style="font-size:13px;line-height:1.6;padding:4px 8px;">
          <b>${n.label}</b><br/>
          热度: ${n.heat.toFixed(4)}<br/>
          增速: ${n.growth.toFixed(4)}<br/>
          中心度: ${n.centrality.toFixed(4)}<br/>
          连接数: ${n.connections}
        </div>`,
        group: n.group,
        color: {
          background: GROUP_COLORS[n.group]?.bg ?? "#718096",
          border: GROUP_COLORS[n.group]?.border ?? "#4A5568",
          highlight: {
            background: GROUP_COLORS[n.group]?.highlight ?? "#2D3748",
            border: "#1A202C",
          },
        },
        font: {
          color: "#1A202C",
          size: 12,
          face: "system-ui, -apple-system, sans-serif",
          strokeWidth: 2,
          strokeColor: "#FFFFFF",
        },
        shape: "dot",
        borderWidth: 2,
      })),
    );

    const edges = new DataSet(
      data.edges.map((e) => ({
        from: e.source,
        to: e.target,
        label: e.label,
        value: e.weight,
        color: {
          color: "#CBD5E0",
          highlight: "#4A5568",
          hover: "#718096",
          opacity: 0.6,
        },
        font: {
          size: 10,
          color: "#718096",
          strokeWidth: 2,
          strokeColor: "#FFFFFF",
        },
        width: Math.max(0.5, e.weight * 3),
        smooth: { type: "curvedCW", roundness: 0.1 },
        arrows: { to: { enabled: false } },
      })),
    );

    const options = {
      physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -80,
          centralGravity: 0.003,
          springLength: 200,
          springConstant: 0.02,
          damping: 0.4,
        },
        stabilization: {
          enabled: true,
          iterations: 50,
          updateInterval: 10,
        },
      },
      interaction: {
        dragNodes: true,
        dragView: true,
        zoomView: true,
        hover: true,
        tooltipDelay: 200,
        multiselect: false,
      },
      layout: {
        randomSeed: 42,
      },
      edges: {
        smooth: { type: "curvedCW", roundness: 0.1 },
      },
      nodes: {
        borderWidth: 2,
        size: 20,
      },
      groups: {
        1: { color: { background: "#4A90D9", border: "#2B6CB0" } },
        2: { color: { background: "#38A169", border: "#276749" } },
        3: { color: { background: "#E53E3E", border: "#C53030" } },
      },
    };

    // 销毁旧实例
    if (networkRef.current) {
      networkRef.current.destroy();
    }

    // 合并真实节点 + 聚合泡泡
    const allNodes = new DataSet([...realNodes.get(), ...ghostNodes]);

    networkRef.current = new Network(
      containerRef.current,
      { nodes: allNodes, edges },
      options,
    );

    // 节点点击回调
    networkRef.current.on("click", (params: any) => {
      if (params.nodes?.length) {
        const id = params.nodes[0];
        const node = data.nodes.find((n) => n.id === id);
        if (node) {
          setSelectedNode(node);
          onNodeClick?.(id);
        }
      } else {
        setSelectedNode(null);
      }
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [data]);

  return (
    <div className="relative">
      <div
        ref={containerRef}
        className="h-[600px] w-full rounded-lg border border-slate-200 bg-white"
        style={{ minHeight: "600px" }}
      />

      {/* 图例 */}
      <div className="absolute left-3 top-3 rounded-lg border border-slate-200 bg-white/90 p-3 text-xs shadow-sm backdrop-blur">
        <div className="mb-1.5 font-medium text-slate-700">图例</div>
        {Object.entries(GROUP_LABELS).map(([g, label]) => (
          <div key={g} className="flex items-center gap-2 py-0.5">
            <span
              className="inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: GROUP_COLORS[Number(g)]?.bg }}
            />
            <span className="text-slate-600">{label}</span>
          </div>
        ))}
        <div className="mt-2 border-t border-slate-100 pt-1.5 text-slate-400">
          {data.nodes.length} 节点 · {data.edges.length} 边 · 年份 {data.year}
        </div>
      </div>

      {/* 选中节点信息 */}
      {selectedNode && (
        <div className="absolute bottom-3 left-3 max-w-xs rounded-lg border border-slate-200 bg-white/90 p-3 text-xs shadow-sm backdrop-blur">
          <div className="mb-1 font-medium text-slate-800">
            {selectedNode.label}
          </div>
          <div className="space-y-0.5 text-slate-600">
            <div>热度: {selectedNode.heat.toFixed(4)}</div>
            <div>增速: {selectedNode.growth.toFixed(4)}</div>
            <div>中心度: {selectedNode.centrality.toFixed(4)}</div>
            <div>连接数: {selectedNode.connections}</div>
          </div>
        </div>
      )}
    </div>
  );
}
