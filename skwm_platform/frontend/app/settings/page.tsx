"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi, type Overview } from "@/lib/api";
import {
  Database,
  RefreshCw,
  Globe2,
  Bell,
  Link,
  Server,
  Download,
} from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function SettingsPage() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [health, setHealth] = useState<{ ok: boolean; llm: string } | null>(
    null,
  );
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [o, h] = await Promise.all([
          skwmApi.overview(),
          skwmApi.health(),
        ]);
        setOv(o);
        setHealth(h);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, []);

  const online = <Badge tone="green">已连接</Badge>;
  const offline = <Badge tone="slate">未连接</Badge>;
  const planned = <Badge tone="amber">规划中</Badge>;
  const needEnv = <Badge tone="blue">需配环境变量</Badge>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">系统设置</h1>
        <p className="mt-2 text-sm text-slate-600">
          数据源管理 · 知识图谱维护 · 模型配置（状态均来自后端真实探测）
        </p>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ 后端未连接（{err}），请运行{" "}
          <code className="rounded bg-amber-100 px-1">
            uvicorn api:app --port 8000
          </code>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Database size={18} />
            </div>
            <h2 className="font-semibold text-ink">数据源管理</h2>
          </div>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-2">
                <Server size={14} className="text-amber-500" />
                <span className="text-sm text-slate-700">本地世界模型数据</span>
              </div>
              {health?.ok ? online : offline}
            </div>
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-2">
                <Globe2 size={14} className="text-blue-500" />
                <span className="text-sm text-slate-700">
                  OpenAlex / arXiv 采集
                </span>
              </div>
              {planned}
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <Link size={18} />
            </div>
            <h2 className="font-semibold text-ink">知识图谱维护</h2>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">实体数量 E</span>
              <span className="font-medium text-ink">{nf(ov?.entities)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">关系数量 R</span>
              <span className="font-medium text-ink">{nf(ov?.relations)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">状态向量 S</span>
              <span className="font-medium text-ink">
                {nf(ov?.state_vectors)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">年度切片 T</span>
              <span className="font-medium text-ink">
                {nf(ov?.snapshots)}（{ov?.year_range?.[0]}–{ov?.year_range?.[1]}
                ）
              </span>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <Server size={18} />
            </div>
            <h2 className="font-semibold text-ink">模型配置</h2>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">大模型</span>
              <span className="font-medium text-ink">
                {health?.llm ? "DeepSeek" : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">调用成本</span>
              <span className="font-medium text-ink">{health?.llm || "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">预测模型 f</span>
              <Badge tone="green">XGBoost AUC≈0.94</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">GraphRAG / BGE-M3 / H20</span>
              {planned}
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Bell size={18} />
            </div>
            <h2 className="font-semibold text-ink">推送与集成（P）</h2>
          </div>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <span className="text-sm text-slate-700">飞书机器人推送</span>
              {needEnv}
            </div>
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <span className="text-sm text-slate-700">Obsidian 知识沉淀</span>
              {needEnv}
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-400">
            设置环境变量 <code>FEISHU_WEBHOOK</code> /{" "}
            <code>OBSIDIAN_VAULT</code> 后自动启用；未设置时推送回退到
            push_outbox.log。
          </p>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-ink">系统信息</h2>
            <p className="mt-1 text-xs text-slate-500">
              SKWM v1.0 · 科学知识世界模型驱动的高校图书馆智能学科服务模式
            </p>
          </div>
          <Button variant="secondary">
            <Download size={16} />
            导出系统报告
          </Button>
        </div>
      </Card>
    </div>
  );
}
