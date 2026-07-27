"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  GraduationCap, BookOpen, BarChart3, TrendingUp,
  BrainCircuit, Target, Eye, RefreshCw,
} from "lucide-react";

const scenarios = [
  { id: "teacher", title: "教师课题申报", subtitle: "研究热点·选题建议", icon: GraduationCap, color: "text-blue-600 bg-blue-50" },
  { id: "student", title: "研究生论文选题", subtitle: "方向·关键词·文献", icon: BookOpen, color: "text-purple-600 bg-purple-50" },
  { id: "librarian", title: "学科馆员服务", subtitle: "周报·动态·推荐", icon: BarChart3, color: "text-emerald-600 bg-emerald-50" },
  { id: "manager", title: "科研管理支持", subtitle: "画像·网络·对标", icon: TrendingUp, color: "text-amber-600 bg-amber-50" },
];

type Decision = { year: number; note: string; score: number; topics: string[] };

export default function ScenariosPage() {
  const [active, setActive] = useState("teacher");
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isLive, setIsLive] = useState(true);
  // 可控参数
  const [M, setM] = useState(4);
  const [L, setL] = useState(3);
  const [B, setB] = useState(6);

  const current = scenarios.find((s) => s.id === active) || scenarios[0];

  const fetchClosedLoop = useCallback(async (user: string) => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`/api/closed-loop?user=${user}&M=${M}&L=${L}&B=${B}&t0=2020&T=2024`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setDecisions(data.decisions || []);
      setIsLive(!data.fallback);
    } catch (e: any) {
      setError(e.message);
      setDecisions([]);
    } finally {
      setLoading(false);
    }
  }, [M, L, B]);

  useEffect(() => { fetchClosedLoop(active); }, [active, fetchClosedLoop]);

  const maxScore = Math.max(...decisions.map((d) => d.score), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">应用场景 · 闭环决策引擎</h1>
          <p className="mt-2 text-sm text-slate-600">
            propose→simulate→revise · 调参即重算 · 实时响应
          </p>
        </div>
        <Badge tone={isLive ? "green" : "amber"} className="text-sm px-3 py-1.5">
          {isLive ? "● 实时计算" : "○ 降级数据"}
        </Badge>
      </div>

      {/* 场景Tab */}
      <div className="grid grid-cols-4 gap-4">
        {scenarios.map((s) => {
          const SIcon = s.icon;
          return (
            <button key={s.id} onClick={() => setActive(s.id)}
              className={`rounded-lg border p-5 text-left transition ${
                active === s.id ? "border-navy bg-navy/5 shadow-md" : "border-slate-200 bg-white hover:border-slate-300"
              }`}>
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.color}`}><SIcon size={20} /></div>
              <h3 className="mt-3 text-sm font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-xs text-slate-500">{s.subtitle}</p>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-[1fr_1.5fr] gap-6">
        {/* 左: 参数面板 */}
        <Card className="p-6">
          <div className="flex items-start gap-4">
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${current.color}`}>
              <current.icon size={24} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">{current.title}</h2>
              <p className="mt-2 text-sm text-slate-600">调整参数 → 算法实时重算</p>
            </div>
          </div>

          <div className="mt-6 space-y-6">
            {/* M: 束宽 */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-500">束宽 M <span className="text-xs">(候选策略数)</span></span>
                <span className="font-semibold text-navy">{M}</span>
              </div>
              <input type="range" min={1} max={10} value={M}
                onChange={(e) => setM(Number(e.target.value))}
                className="w-full accent-navy" />
              <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                <span>1（少探索）</span><span>10（多探索）</span>
              </div>
            </div>

            {/* L: 视野 */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-500">视野 L <span className="text-xs">(预测年数)</span></span>
                <span className="font-semibold text-navy">{L}年</span>
              </div>
              <input type="range" min={1} max={10} value={L}
                onChange={(e) => setL(Number(e.target.value))}
                className="w-full accent-navy" />
              <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                <span>1年</span><span>10年</span>
              </div>
            </div>

            {/* B: 推理预算 */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-500">推理预算 B <span className="text-xs">(rollout采样)</span></span>
                <span className="font-semibold text-navy">{B}次</span>
              </div>
              <input type="range" min={1} max={20} value={B}
                onChange={(e) => setB(Number(e.target.value))}
                className="w-full accent-navy" />
              <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                <span>1（低精度）</span><span>20（高精度）</span>
              </div>
            </div>

            <Button className="w-full" onClick={() => fetchClosedLoop(active)}>
              <RefreshCw size={16} />
              重新计算
            </Button>
          </div>
        </Card>

        {/* 右: 结果 */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-ink">闭环决策时间线</h2>
            {decisions.length > 0 && (
              <span className="text-xs text-slate-400">M={M} L={L} B={B}</span>
            )}
          </div>

          {loading ? (
            <div className="flex flex-col items-center gap-3 py-16 text-slate-400">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-navy" />
              <span className="text-sm">正在规划未来...</span>
              <span className="text-xs">propose→simulate→revise</span>
            </div>
          ) : error ? (
            <div className="py-12 text-center">
              <p className="text-sm text-red-500">{error}</p>
              <Button className="mt-4" variant="secondary" onClick={() => fetchClosedLoop(active)}>重试</Button>
            </div>
          ) : decisions.length === 0 ? (
            <div className="flex flex-col items-center py-16 text-center">
              <BrainCircuit size={48} className="text-navy/20" />
              <p className="mt-4 text-sm text-slate-500">暂无决策数据</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* 评分柱 */}
              <div className="rounded-md bg-slate-50 p-4">
                <div className="text-xs text-slate-500 mb-2">决策评分趋势</div>
                <div className="space-y-2">
                  {decisions.map((d) => (
                    <div key={d.year} className="flex items-center gap-3">
                      <span className="w-10 text-xs font-medium text-slate-600">{d.year}</span>
                      <div className="flex-1 h-5 rounded bg-white overflow-hidden">
                        <div className="h-full rounded bg-gradient-to-r from-navy to-blue-500 transition-all"
                          style={{ width: `${(d.score / maxScore) * 100}%` }} />
                      </div>
                      <span className="w-16 text-right text-xs font-semibold text-ink">{d.score.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 决策卡片 */}
              {decisions.map((d) => (
                <div key={d.year} className="rounded-lg border border-slate-100 p-4 hover:border-navy/20 transition">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-navy/10 text-xs font-bold text-navy">{d.year}</div>
                      <span className="text-sm font-medium text-ink">决策</span>
                    </div>
                    <Badge tone="blue">评分 {d.score.toFixed(1)}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{d.note}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {d.topics.map((t) => (<Badge key={t} tone="slate">{t}</Badge>))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 架构 */}
      <Card className="p-5">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy/5 text-navy"><Eye size={20} /></div>
          <div className="flex-1">
            <h2 className="font-semibold text-ink">世界模型闭环架构</h2>
            <div className="mt-3 grid grid-cols-4 gap-4 text-sm">
              {[
                { step: "① Propose", desc: "LLM/规则 生成 M 条候选策略", color: "bg-blue-100 text-blue-700" },
                { step: "② Encode", desc: "API 策略→图谱干预编码", color: "bg-purple-100 text-purple-700" },
                { step: "③ Simulate", desc: "g_θ rollout B次→平均降方差", color: "bg-emerald-100 text-emerald-700" },
                { step: "④ Revise", desc: "按用户权重评分→选最优", color: "bg-amber-100 text-amber-700" },
              ].map((s) => (
                <div key={s.step} className={`rounded-md p-3 ${s.color}`}>
                  <div className="font-semibold">{s.step}</div>
                  <div className="mt-1 text-xs opacity-80">{s.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
