"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  Bot,
  Sparkles,
  Send,
  BookOpen,
  Globe2,
  GraduationCap,
  BarChart3,
  TrendingUp,
} from "lucide-react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: { title: string; source: string }[];
};

const scenarios = [
  { label: "教师课题申报", value: "teacher", icon: GraduationCap },
  { label: "学生论文选题", value: "student", icon: BookOpen },
  { label: "学科服务周报", value: "weekly", icon: BarChart3 },
  { label: "科研管理分析", value: "management", icon: TrendingUp },
];

const defaultQuestions: Record<string, string[]> = {
  teacher: [
    "分析近五年中阿文化遗产旅游研究热点，推荐国家社科选题",
    "中阿文旅领域有哪些值得关注的研究空白？",
    "近三年中阿文旅方向的高被引论文有哪些？",
  ],
  student: [
    "我想写阿拉伯国家数字文旅传播，请推荐选题和文献",
    "文化遗产数字化方向有哪些可做的论文题目？",
    "中阿文旅研究常用的理论框架有哪些？",
  ],
  weekly: [
    "生成本周中阿文旅学科服务周报",
    "本周有哪些重要的中阿文旅会议和活动？",
    "最近中阿文旅领域有哪些新政策发布？",
  ],
  management: [
    "分析我校中阿文旅研究优势和潜在合作机构",
    "中阿文旅研究的国际合作网络是怎样的？",
    "我校在中阿文旅方向的成果产出趋势如何？",
  ],
};

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

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setQuestion("");

    // Simulate streaming response
    const demoResponses: Record<string, string> = {
      teacher:
        "## 中阿文化遗产旅游研究热点分析\n\n### 近五年研究热点\n\n1. **数字文化遗产保护** — 3D扫描、虚拟重建技术在阿拉伯国家文化遗产中的应用\n2. **文化旅游品牌建设** — 沙特、阿联酋的文化旅游目的地营销策略\n3. **跨文化游客行为** — 中国游客赴阿拉伯国家的旅游动机与满意度\n\n### 推荐选题方向\n\n- **国家社科基金建议**：基于数字孪生的中阿文化遗产旅游沉浸式体验研究\n- **教育部人文社科**：中阿文旅融合的跨文化传播机制与路径研究\n\n### 核心文献\n\n1. Al-Said (2023) — Digital Heritage Tourism in GCC Countries\n2. Li & Zhang (2024) — Chinese Tourists' Cultural Adaptation in Arab Destinations",
      student:
        "## 阿拉伯国家数字文旅传播选题建议\n\n### 推荐选题\n\n**方向一**：阿拉伯国家数字文旅传播的社交媒体策略研究\n- 核心问题：TikTok、Instagram 等平台如何影响阿拉伯国家旅游形象？\n- 理论框架：目的地形象理论 + 媒介丰富度理论\n\n**方向二**：中阿数字文旅平台用户体验研究\n- 核心问题：中文用户对阿拉伯文旅数字平台的接受度如何？\n- 研究方法：问卷调查 + 可用性测试\n\n### 推荐文献\n\n- 陈等 (2024) — 数字文旅平台用户持续使用意愿研究\n- Al-Abdulkarim (2023) — Social Media and Tourism in Saudi Arabia",
      weekly:
        "## 中阿文旅学科服务周报 (第28周)\n\n### 📌 本周热点\n\n1. **新发论文**：本周新增 3 篇中阿文旅相关论文\n   - 沙特红海旅游项目可持续发展研究\n   - 阿联酋元宇宙文旅体验设计\n2. **新政策**：沙特启动\"2030旅游愿景\"中期评估\n3. **重要会议**：下周将举办中阿数字文旅论坛\n\n### 📊 主题热度变化\n\n- 数字文旅：↑ 12%\n- 文化遗产保护：↑ 8%\n- 旅游目的地营销：→ 稳定",
      management:
        "## 中阿文旅研究优势与潜在合作机构分析\n\n### 本校优势画像\n\n| 维度 | 内容 |\n|------|------|\n| 核心优势 | 阿拉伯语研究、旅游管理、跨文化传播 |\n| 代表性成果 | 中阿文旅知识服务平台（SKWM驱动） |\n| 特色资源 | 阿语文献资源库、中阿文旅中心 |\n\n### 合作机构推荐\n\n1. **北京外国语大学** — 阿拉伯学院\n2. **上海外国语大学** — 中东研究所\n3. **开罗大学** — 旅游与酒店管理学院\n\n### 建议\n\n加速知识图谱构建，开展跨机构合作研究",
    };

    const resp =
      demoResponses[activeScenario] ||
      "基于科学知识世界模型(SKWM)的分析正在进行中...\n\n根据知识图谱和GraphRAG检索，已为您找到相关的中阿文旅资源。\n\n请提供更详细的需求以便生成定制化报告。";

    const citations = [
      { title: "SKWM 知识图谱查询结果", source: "本地知识图谱 · 2026-07" },
      { title: "OpenAlex 学术检索", source: "OpenAlex API · 2026-07" },
    ];

    // Simulate delay
    await new Promise((r) => setTimeout(r, 1500));

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: resp, citations },
    ]);
    setLoading(false);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">
          SKWM 智能问答顾问
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          基于科学知识世界模型 · 知识图谱 + GraphRAG + 大模型智能体
        </p>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-6">
        {/* Left panel: scenario selection and context */}
        <div className="space-y-4">
          {/* Scenario selection */}
          <Card className="p-5">
            <h2 className="font-semibold text-ink">服务场景</h2>
            <div className="mt-4 space-y-2">
              {scenarios.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.value}
                    onClick={() => setActiveScenario(s.value)}
                    className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium transition ${
                      activeScenario === s.value
                        ? "bg-navy text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <Icon size={16} />
                    {s.label}
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Quick questions */}
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

          {/* Context info */}
          <Card className="p-5">
            <h2 className="font-semibold text-ink">当前上下文</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div>
                <dt className="text-slate-500">场景</dt>
                <dd className="font-medium">
                  {scenarios.find((s) => s.value === activeScenario)?.label}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">数据源</dt>
                <dd className="font-medium">知识图谱 + OpenAlex</dd>
              </div>
              <div>
                <dt className="text-slate-500">模型</dt>
                <dd className="font-medium">SKWM GraphRAG</dd>
              </div>
            </dl>
          </Card>
        </div>

        {/* Right panel: chat */}
        <div className="space-y-4">
          {/* Input */}
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
                  <span className="text-xs text-slate-400">
                    ⌘+Enter 发送
                  </span>
                  <Button onClick={() => send()} disabled={loading}>
                    <Send size={16} />
                    {loading ? "生成中..." : "发送"}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* Messages */}
          {messages.length === 0 ? (
            <Card className="p-8 text-center">
              <Bot size={48} className="mx-auto text-navy/20" />
              <h3 className="mt-4 text-sm font-medium text-ink">
                开始您的智能问答
              </h3>
              <p className="mt-2 text-xs text-slate-500">
                选择左侧场景，或直接输入问题
                <br />
                系统将基于知识图谱和 GraphRAG 生成结构化回答
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
                        {msg.content ? (
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        ) : (
                          <div className="flex items-center gap-2 text-sm text-slate-400">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-navy" />
                            正在生成...
                          </div>
                        )}
                      </Card>
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {msg.citations.map((cit, ci) => (
                            <Badge key={ci} tone="blue">
                              📎 {cit.title}
                            </Badge>
                          ))}
                        </div>
                      )}
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
