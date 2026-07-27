"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Settings, Database, RefreshCw, Globe2, Bell, Shield, Link, Server, Download } from "lucide-react";

export default function SettingsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/settings").then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-6"><div className="h-7 w-40 animate-pulse rounded bg-slate-200" /><div className="grid grid-cols-2 gap-6">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-40 animate-pulse rounded-lg bg-slate-200" />)}</div></div>;

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-semibold text-ink">系统设置</h1><p className="mt-2 text-sm text-slate-600">数据源管理 · 知识图谱维护 · 模型配置 · 真实状态</p></div>

      <div className="grid grid-cols-2 gap-6">
        <Card className="p-5">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><Database size={18} /></div><h2 className="font-semibold text-ink">数据源管理</h2></div>
          <div className="mt-4 space-y-3">
            <Row label="文献资料库" value={data?.data_source || "未知"} tone="green" />
            <Row label="文献总量" value={`${data?.total_papers || 0} 篇`} tone="green" />
            <Row label="知识分类" value={`${data?.category_count || 0} 个`} tone="green" />
            <Row label="年代跨度" value={`${data?.year_range?.[0] || "?"}-${data?.year_range?.[1] || "?"}`} tone="green" />
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600"><Link size={18} /></div><h2 className="font-semibold text-ink">知识图谱维护</h2></div>
          <div className="mt-4 space-y-3">
            <Row label="实体数量" value="待导入" tone="slate" />
            <Row label="关系数量" value="待导入" tone="slate" />
            <Row label="最后更新" value={data?.last_update || "未知"} tone="slate" />
            <Row label="人工校验通过率" value="—" tone="slate" />
            <Button className="mt-2 w-full" variant="secondary"><RefreshCw size={16} />导入实体JSON</Button>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><Server size={18} /></div><h2 className="font-semibold text-ink">模型配置</h2></div>
          <div className="mt-4 space-y-3">
            <Row label="算法模式" value="propose→simulate→revise" tone="green" />
            <Row label="RNG模式" value={data?.rng_mode || "规则"} tone="amber" />
            <Row label="GraphRAG" value={data?.graphrag_mode || "未接入"} tone="slate" />
            <Row label="算力后端" value="CPU (本地)" tone="slate" />
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Bell size={18} /></div><h2 className="font-semibold text-ink">推送与集成</h2></div>
          <div className="mt-4 space-y-3">
            <Row label="飞书机器人" value="待配置" tone="slate" />
            <Row label="Obsidian同步" value="待配置" tone="slate" />
            <Row label="文献自动监控" value="待配置" tone="slate" />
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div><h2 className="font-semibold text-ink">系统信息</h2><p className="mt-1 text-xs text-slate-500">SKWM · 科学知识世界模型 · 完整平台</p></div>
          <Button variant="secondary"><Download size={16} />导出系统报告</Button>
        </div>
      </Card>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone: "green" | "amber" | "slate" }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
      <span className="text-sm text-slate-700">{label}</span>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}
