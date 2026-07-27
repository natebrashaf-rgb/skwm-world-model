import { Card } from "@/components/ui/Card";
import { Database, Globe2, BookOpen, GraduationCap } from "lucide-react";

const stats = [
  { label: "知识实体", value: "1,284", helper: "文献·作者·机构·主题·地点", icon: Database },
  { label: "知识关系", value: "4,672", helper: "引用·合作·共现·隶属·演化", icon: Globe2 },
  { label: "文献总量", value: "210", helper: "中阿英多语种覆盖", icon: BookOpen },
  { label: "服务次数", value: "47", helper: "教师/学生/馆员/管理", icon: GraduationCap },
];

export function ModelStats() {
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-slate-100 bg-gradient-to-r from-navy/5 to-transparent px-5 py-3">
        <h2 className="font-semibold text-ink">科学知识世界模型 (SKWM) 数据概览</h2>
      </div>
      <div className="grid grid-cols-4 divide-x divide-slate-100">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="px-5 py-4 text-center">
              <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-md bg-navy/5 text-navy">
                <Icon size={16} />
              </div>
              <div className="text-2xl font-semibold text-navy">{stat.value}</div>
              <div className="mt-1 text-xs text-slate-500">{stat.label}</div>
              <div className="mt-0.5 text-[10px] text-slate-400">
                {stat.helper}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
