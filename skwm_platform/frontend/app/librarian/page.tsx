"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi, USER_LABELS, type ReportMeta, type Overview } from "@/lib/api";
import {
  ShieldCheck,
  FileSearch,
  Send,
  BookMarked,
  Search,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ExternalLink,
  RefreshCw,
  Archive,
} from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function LibrarianPage() {
  const [err, setErr] = useState<string | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [loading, setLoading] = useState(true);

  // 审核工作区
  const [auditTopic, setAuditTopic] = useState("中阿文旅");
  const [auditResult, setAuditResult] = useState<any>(null);
  const [auditing, setAuditing] = useState(false);

  // Obsidian 沉淀
  const [sedimentResult, setSedimentResult] = useState<any>(null);
  const [sedimenting, setSedimenting] = useState(false);
  const [pushResult, setPushResult] = useState<any>(null);
  const [pushing, setPushing] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [o, r] = await Promise.all([
          skwmApi.overview(),
          skwmApi.reports(),
        ]);
        setOv(o);
        setReports(r.reports);
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function runAudit() {
    setAuditing(true);
    setAuditResult(null);
    try {
      const res = await skwmApi.report(auditTopic, "librarian", {
        sediment: false,
      });
      setAuditResult(res.report || res);
    } catch (e: any) {
      setAuditResult({ error: e?.message || "审核失败" });
    } finally {
      setAuditing(false);
    }
  }

  async function runSediment() {
    setSedimenting(true);
    setSedimentResult(null);
    try {
      const res = await skwmApi.report("中阿文旅", "librarian", {
        sediment: true,
      });
      setSedimentResult(res.sediment || res);
      // 刷新报告列表
      const r = await skwmApi.reports();
      setReports(r.reports);
    } catch (e: any) {
      setSedimentResult({ error: e?.message || "沉淀失败" });
    } finally {
      setSedimenting(false);
    }
  }

  async function runPush() {
    setPushing(true);
    setPushResult(null);
    try {
      const res = await skwmApi.report("中阿文旅热点速递", "librarian", {
        push: true,
        sediment: false,
      });
      setPushResult(res.push || res);
    } catch (e: any) {
      setPushResult({ sent: false, error: e?.message || "推送失败" });
    } finally {
      setPushing(false);
    }
  }

  const unverifiableCount = auditResult?.audit?.unverifiable?.length || 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">馆员工作台</h1>
        <p className="mt-2 text-sm text-slate-600">
          P服务规则 · 审核验证 → 来源追溯 → 推送分发 → Obsidian沉淀
        </p>
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ {err}，请运行 <code className="rounded bg-amber-100 px-1">uvicorn api:app --port 8000</code>
        </div>
      )}

      {/* 概览指标 */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-500" />
            <span className="text-sm text-slate-500">知识实体 E</span>
          </div>
          <div className="mt-2 text-2xl font-semibold text-ink">{nf(ov?.entities)}</div>
          <div className="mt-1 text-xs text-slate-500">可追溯节点</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <FileSearch size={16} className="text-blue-500" />
            <span className="text-sm text-slate-500">已沉淀报告</span>
          </div>
          <div className="mt-2 text-2xl font-semibold text-ink">{reports.length}</div>
          <div className="mt-1 text-xs text-slate-500">Obsidian 归档</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <Archive size={16} className="text-amber-500" />
            <span className="text-sm text-slate-500">时间切片 T</span>
          </div>
          <div className="mt-2 text-2xl font-semibold text-ink">{nf(ov?.snapshots)}</div>
          <div className="mt-1 text-xs text-slate-500">{ov?.year_range?.[0]}–{ov?.year_range?.[1]}</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <RefreshCw size={16} className="text-purple-500" />
            <span className="text-sm text-slate-500">语境维度 C</span>
          </div>
          <div className="mt-2 text-2xl font-semibold text-ink">4</div>
          <div className="mt-1 text-xs text-slate-500">政策·合作·学科·国际</div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* ═══ P.2 审核规则 ═══ */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-ink">P.2 审核验证</h2>
              <p className="text-xs text-slate-500">来源追溯 + 幻觉检测</p>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <input
              value={auditTopic}
              onChange={(e) => setAuditTopic(e.target.value)}
              placeholder="输入审核主题..."
              className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-navy"
            />
            <Button onClick={runAudit} disabled={auditing} size="sm">
              {auditing ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              审核
            </Button>
          </div>
          {auditResult && !auditResult.error && (
            <div className="mt-4 space-y-2 rounded-md bg-slate-50 p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{auditResult.title}</span>
                {auditResult.audit?.status && (
                  <Badge tone={auditResult.audit.status.includes("✅") ? "green" : "amber"}>
                    {auditResult.audit.status}
                  </Badge>
                )}
              </div>
              {unverifiableCount > 0 ? (
                <div className="flex items-center gap-2 text-amber-700">
                  <AlertTriangle size={14} />
                  <span>{unverifiableCount} 项待馆员核验</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-emerald-700">
                  <CheckCircle2 size={14} />
                  <span>全部可追溯</span>
                </div>
              )}
              <div className="pt-2 text-xs text-slate-400">
                {auditResult.audit?.note || "每条结论已附 verifiable 标志"}
              </div>
            </div>
          )}
          {auditResult?.error && (
            <div className="mt-4 text-sm text-red-500">{auditResult.error}</div>
          )}
        </Card>

        {/* ═══ P.3 推送规则 ═══ */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Send size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-ink">P.3 推送分发</h2>
              <p className="text-xs text-slate-500">飞书机器人 · 回退到本地日志</p>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <span className="text-sm text-slate-700">中阿文旅热点速递</span>
              <Button onClick={runPush} disabled={pushing} size="sm" variant="secondary">
                {pushing ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                推送测试
              </Button>
            </div>
            {pushResult && (
              <div className="rounded-md bg-slate-50 p-3 text-xs">
                {pushResult.sent === false ? (
                  <div className="text-amber-600">
                    ⚠️ 未配飞书 webhook，已回退到本地日志: {pushResult.path || pushResult.fallback}
                  </div>
                ) : pushResult.sent ? (
                  <div className="text-emerald-600">✅ 推送成功</div>
                ) : (
                  <div className="text-red-500">❌ {pushResult.error || "推送失败"}</div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* ═══ P.4 沉淀规则 ═══ */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <BookMarked size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-ink">P.4 Obsidian 沉淀</h2>
              <p className="text-xs text-slate-500">Markdown 归档 · 双链引用</p>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            <div className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-3">
              <span className="text-sm text-slate-700">生成并沉淀最新报告</span>
              <Button onClick={runSediment} disabled={sedimenting} size="sm" variant="secondary">
                {sedimenting ? <Loader2 size={14} className="animate-spin" /> : <Archive size={14} />}
                沉淀
              </Button>
            </div>
            {sedimentResult && (
              <div className="rounded-md bg-slate-50 p-3">
                {sedimentResult.sedimented === false ? (
                  <div className="text-xs text-red-500">{sedimentResult.error || "沉淀失败"}</div>
                ) : (
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2 text-emerald-600">
                      <CheckCircle2 size={12} />
                      <span>已沉淀到 {sedimentResult.path}</span>
                    </div>
                    {sedimentResult.filename && (
                      <div className="text-slate-400">文件名：{sedimentResult.filename}</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* ═══ P.1 推荐规则 ═══ */}
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <ExternalLink size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-ink">P.1 推荐规则</h2>
              <p className="text-xs text-slate-500">U×S 用户偏好 × 知识状态</p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {["teacher", "student", "librarian", "manager"].map((ut) => (
              <div key={ut} className="flex items-center justify-between rounded-md bg-slate-50 px-4 py-2.5">
                <span className="text-sm text-slate-700">{USER_LABELS[ut]}</span>
                <Badge tone={ut === "teacher" ? "blue" : ut === "student" ? "purple" : ut === "librarian" ? "emerald" : "amber"}>
                  {ut === "teacher" ? "前沿+中心度" :
                   ut === "student" ? "热度+连接数" :
                   ut === "librarian" ? "热度+增速" : "中心度+连接数"}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
