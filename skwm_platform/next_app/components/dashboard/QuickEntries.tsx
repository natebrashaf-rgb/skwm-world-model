import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Bot, Network, BarChart3, Compass, ArrowRight } from "lucide-react";

const quickEntries = [
  {
    title: "智能问答",
    description: "基于 GraphRAG 的知识问答与报告生成",
    icon: Bot,
    href: "/rag-advisor",
    color: "text-blue-600 bg-blue-50",
  },
  {
    title: "知识图谱",
    description: "中阿文旅知识实体与关系可视化浏览",
    icon: Network,
    href: "/knowledge-graph",
    color: "text-purple-600 bg-purple-50",
  },
  {
    title: "科学计量",
    description: "研究热点、前沿识别与演化分析",
    icon: BarChart3,
    href: "/scientometrics",
    color: "text-emerald-600 bg-emerald-50",
  },
  {
    title: "应用场景",
    description: "教师课题、学生选题、学科周报、科研管理",
    icon: Compass,
    href: "/scenarios",
    color: "text-amber-600 bg-amber-50",
  },
];

export function QuickEntries() {
  return (
    <div className="grid grid-cols-2 gap-4">
      {quickEntries.map((entry) => {
        const Icon = entry.icon;
        return (
          <Link key={entry.href} href={entry.href}>
            <Card className="group cursor-pointer p-5 transition hover:shadow-md">
              <div className="flex items-start gap-4">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${entry.color}`}
                >
                  <Icon size={20} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-ink">{entry.title}</h3>
                    <ArrowRight
                      size={16}
                      className="text-slate-300 transition group-hover:text-navy"
                    />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {entry.description}
                  </p>
                </div>
              </div>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
