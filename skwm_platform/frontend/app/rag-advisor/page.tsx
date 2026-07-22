"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { skwmApi } from "@/lib/api";
import {
  Bot,
  Sparkles,
  Send,
  GraduationCap,
  BookOpen,
  BarChart3,
  TrendingUp,
} from "lucide-react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
  audit?: string;
};

const scenarios = [
  { label: "教师课题申报", value: "teacher", icon: GraduationCap },
  { label: "学生论文选题", value: "student", icon: BookOpen },
  { label: "学科服务周报", value: "librarian", icon: BarChart3 },
  { label: "科研管理分析", value: "manager", icon: TrendingUp },
];

const defaultQuestions: Record<string, string[]> = {
  teacher: [
    "分析近年中阿文化遗产旅游研究热点",
    "中阿文旅领域有哪些值得关注的前沿？",
  ],
  student: ["阿拉伯国家数字文旅传播选题建议", "文化遗产数字化方向的可做选题"],
  librarian: ["生成本周中阿文旅学科服务周报", "本周中阿文旅领域热点变化"],
  manager: [
    "分析我校中阿文旅研究优势与潜在合作机构",
    "中阿文旅研究的国际合作网络",
  ],
};

function reportToMarkdown(rep: any): string {
  if (!rep) return "（无返回内容）";
  let md = `## ${rep.title || "SKWM 分析报告"}\n\n`;
  for (const sec of rep.sections || []) {
    md += `### ${sec.name}\n\n`;
    if (typeof sec.data === "string") {
      md += `${sec.data}\n\n`;
      continue;
    }
    if (Array.isArray(sec.data)) {
      for (const it of sec.data) {
        if (!it?.name) continue;
        const bits: string[] = [];
        if (it.heat != null) bits.push(`热度 ${it.heat}`);
        if (it.growth != null) bits.push(`增速 ${it.growth}`);
        if (it.predicted_heat != null)
          bits.push(`预测热度 ${Number(it.predicted_heat).toFixed(1)}`);
        md += `- **${it.name}**${bits.length ? ` — ${bits.join(" · ")}` : ""}\n`;
      }
      md += "\n";
    }
  }
  if (rep.data_scale) md += `\n---\n*数据规模：${rep.data_scale}*\n`;
  return md;
}

export default function RagAdvisorPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeScenario, setActiveScenario] = useState("teacher");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(q?: string) {
    const text = q || question;
    if (!text.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    setQuestion("");
    try {
      // 真实调用 GraphRAG 问答引擎
      const res = await skwmApi.queryKg(text, activeScenario);
      const answer = res.answer || "（无返回）";
      const confidence = res.confidence || 0;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: answer,
          citations: res.sources || [],
          audit: confidence > 0.8 ? "✅ 高置信度" : "⚠️ 仅供参考",
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ 未能连接后端世界模型服务（${e?.message || "error"}）。\n\n请先在后端目录运行 \`uvicorn api:app --port 8000\`。`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">SKWM 智能问答顾问</h1>
        <p className="mt-2 text-sm text-slate-600">
          基于科学知识世界模型 · 真实调用报告智能体 + P 审核规则
        </p>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-6">
        <div className="space-y-4">
          <Card className="p-5">
            <h2 className="font-semibold text-ink">服务场景</h2>
            <div className="mt-4 space-y-2">
              {scenarios.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.value}
                    onClick={() => setActiveScenario(s.value)}
                    className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium transition ${activeScenario === s.value ? "bg-navy text-white" : "text-slate-600 hover:bg-slate-100"}`}
                  >
                    <Icon size={16} />
                    {s.label}
                  </button>
                );
              })}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-semibold text-ink">快捷提问</h2>
            <div className="mt-4 space-y-2">
              {(defaultQuestions[activeScenario] || []).map((q, i) => (
                <button
                  key={i}
                  onClick={() => send(q)}
                  className="w-full rounded-md bg-slate-50 px-3 py-2 text-left text-xs text-slate-600 transition hover:bg-slate-100"
                >
                  {q}
                </button>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-semibold text-ink">当前上下文</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div>
                <dt className="text-slate-500">用户类型 U</dt>
                <dd className="font-medium">
                  {scenarios.find((s) => s.value === activeScenario)?.label}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">数据源</dt>
                <dd className="font-medium">世界模型状态向量 + 知识图谱</dd>
              </div>
              <div>
                <dt className="text-slate-500">引擎</dt>
                <dd className="font-medium">SKWMController.process</dd>
              </div>
            </dl>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-navy/10 text-navy">
                <Sparkles size={16} />
              </div>
              <div className="flex-1">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  className="min-h-24 w-full rounded-md border border-slate-200 p-3 text-sm outline-none focus:border-navy"
                  placeholder={`输入${scenarios.find((s) => s.value === activeScenario)?.label}相关的问题...`}
                />
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-xs text-slate-400">⌘+Enter 发送</span>
                  <Button onClick={() => send()} disabled={loading}>
                    <Send size={16} />
                    {loading ? "生成中..." : "发送"}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {messages.length === 0 ? (
            <Card className="p-8 text-center">
              <Bot size={48} className="mx-auto text-navy/20" />
              <h3 className="mt-4 text-sm font-medium text-ink">
                开始您的智能问答
              </h3>
              <p className="mt-2 text-xs text-slate-500">
                选择左侧场景，或直接输入问题
                <br />
                系统将基于真实世界模型生成结构化回答
              </p>
            </Card>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, idx) => (
                <div key={idx}>
                  {msg.role === "user" ? (
                    <Card className="border-navy/10 bg-navy/5 p-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy/20 text-xs font-medium text-navy">
                          我
                        </div>
                        <p className="text-sm font-medium text-ink">
                          {msg.content}
                        </p>
                      </div>
                    </Card>
                  ) : (
                    <>
                      <Card className="prose max-w-none p-5">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </Card>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {msg.audit && (
                          <Badge tone="green">✓ P审核：{msg.audit}</Badge>
                        )}
                        {msg.citations?.map((c, ci) => (
                          <Badge key={ci} tone="blue">
                            📎 {c}
                          </Badge>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
