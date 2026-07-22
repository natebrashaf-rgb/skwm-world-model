"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi, type HotItem } from "@/lib/api";
import {
  GraduationCap,
  BookOpen,
  BarChart3,
  TrendingUp,
  ArrowRight,
  FileText,
  Sparkles,
} from "lucide-react";

const scenarios = [
  {
    id: "teacher",
    user: "teacher",
    title: "教师课题申报支持",
    subtitle: "研究热点 · 选题建议 · 文献支撑",
    icon: GraduationCap,
    color: "text-blue-600 bg-blue-50",
    description:
      "为教师提供中阿文旅领域的研究热点分析、前沿识别、国家社科/教育部课题选题建议，以及核心文献支撑。",
    example: "「分析近五年中阿文化遗产旅游研究热点，并推荐国家社科选题」",
    steps: [
      "分析近五年研究热点与前沿趋势",
      "识别核心作者、机构和代表性文献",
      "生成主题演化图和关键词共现图",
      "推荐课题选题方向和参考文献清单",
    ],
  },
  {
    id: "student",
    user: "student",
    title: "研究生论文选题支持",
    subtitle: "选题方向 · 关键词 · 理论框架",
    icon: BookOpen,
    color: "text-purple-600 bg-purple-50",
    description:
      "为研究生提供论文选题建议、中阿英关键词提取、核心文献推荐和理论框架匹配。",
    example: "「我想写阿拉伯国家数字文旅传播，请推荐选题和文献」",
    steps: [
      "推荐选题方向和细化路径",
      "生成中阿英文关键词",
      "推荐核心文献和理论框架",
      "提供数据来源和研究方法建议",
    ],
  },
  {
    id: "weekly",
    user: "librarian",
    title: "学科馆员智能服务",
    subtitle: "周报生成 · 动态跟踪 · 资源推荐",
    icon: BarChart3,
    color: "text-emerald-600 bg-emerald-50",
    description:
      "自动生成学科服务周报，包括新发论文、新政策、重要会议、热点主题和馆藏资源推荐。",
    example: "「生成本周中阿文旅学科服务周报」",
    steps: [
      "检索本周新增的中阿文旅相关文献",
      "扫描最新政策文件和会议信息",
      "分析本周热点主题变化",
      "生成结构化周报并推送至飞书",
    ],
  },
  {
    id: "management",
    user: "manager",
    title: "科研管理支持",
    subtitle: "成果画像 · 合作网络 · 机构对标",
    icon: TrendingUp,
    color: "text-amber-600 bg-amber-50",
    description:
      "为科研管理人员提供本校研究成果画像、合作机构网络分析、优势主题识别和发展建议。",
    example: "「分析我校中阿文旅研究优势和潜在合作机构」",
    steps: [
      "生成本校中阿文旅成果画像",
      "分析合作机构网络",
      "识别优势主题和短板方向",
      "提供平台建设和发展建议",
    ],
  },
];

export default function ScenariosPage() {
  const [active, setActive] = useState("teacher");
  const current = scenarios.find((s) => s.id === active) || scenarios[0];
  const Icon = current.icon;
  const [hot, setHot] = useState<HotItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const h = await skwmApi.hotspots(current.user);
        setHot(h.hotspots.slice(0, 5));
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
        setHot([]);
      }
    })();
  }, [active, current.user]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">应用场景</h1>
        <p className="mt-2 text-sm text-slate-600">
          四大核心服务场景 · 右侧实时热点来自世界模型（按 U 用户类型加权）
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {scenarios.map((s) => {
          const SIcon = s.icon;
          return (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              className={`rounded-lg border p-5 text-left transition ${active === s.id ? "border-navy bg-navy/5 shadow-md" : "border-slate-200 bg-white hover:border-slate-300"}`}
            >
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.color}`}
              >
                <SIcon size={20} />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-xs text-slate-500">{s.subtitle}</p>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-[1fr_1.2fr] gap-6">
        <Card className="p-6">
          <div className="flex items-start gap-4">
            <div
              className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${current.color}`}
            >
              <Icon size={24} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">
                {current.title}
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                {current.description}
              </p>
            </div>
          </div>
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-ink">服务流程</h3>
            <div className="mt-4 space-y-3">
              {current.steps.map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy/10 text-xs font-medium text-navy">
                    {i + 1}
                  </div>
                  <span className="text-sm text-slate-600">{step}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-6 rounded-md bg-mist p-4">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Sparkles size={12} />
              示例输入
            </div>
            <p className="mt-2 text-sm italic text-slate-700">
              {current.example}
            </p>
          </div>
          <a href="/rag-advisor">
            <Button className="mt-6 w-full">
              <FileText size={16} />
              进入{current.title}
              <ArrowRight size={16} />
            </Button>
          </a>
        </Card>

        <Card className="p-6">
          <h2 className="font-semibold text-ink">
            实时热点预览（{current.title}）
          </h2>
          {err && (
            <p className="mt-4 text-sm text-amber-700">
              ⚠️ 后端未连接，请运行 uvicorn api:app --port 8000
            </p>
          )}
          <div className="mt-4 space-y-3">
            {!err && hot.length === 0 && (
              <p className="text-sm text-slate-500">加载中…</p>
            )}
            {hot.map((h, i) => (
              <div
                key={h.name}
                className="flex items-center justify-between rounded-md border border-slate-100 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${i < 3 ? "bg-navy text-white" : "bg-slate-100 text-slate-600"}`}
                  >
                    {i + 1}
                  </span>
                  <span className="text-sm font-medium text-ink">{h.name}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500">热度 {h.heat}</span>
                  <Badge tone={h.context_weight > 1 ? "green" : "slate"}>
                    ×{h.context_weight}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-400">
            切换左侧场景，右侧按对应用户类型重新拉取并加权。
          </p>
        </Card>
      </div>
    </div>
  );
}
