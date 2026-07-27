"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Search, Filter, Network, ArrowRight, BookOpen, MapPin, Users, Building2 } from "lucide-react";

const entityTypes = [
  { type: "文献", count: 210, icon: BookOpen, color: "text-blue-600 bg-blue-50" },
  { type: "作者", count: 386, icon: Users, color: "text-purple-600 bg-purple-50" },
  { type: "机构", count: 124, icon: Building2, color: "text-emerald-600 bg-emerald-50" },
  { type: "地点/国家", count: 58, icon: MapPin, color: "text-amber-600 bg-amber-50" },
];

const sampleEntities = [
  { name: "中阿文明交流", type: "主题", relations: 24, badge: "blue" as const },
  { name: "文化遗产旅游", type: "主题", relations: 18, badge: "blue" as const },
  { name: "北京第二外国语学院", type: "机构", relations: 42, badge: "green" as const },
  { name: "数字文旅传播", type: "主题", relations: 15, badge: "blue" as const },
  { name: "阿拉伯语资源库", type: "资源", relations: 12, badge: "purple" as const },
  { name: "旅游目的地营销", type: "主题", relations: 9, badge: "blue" as const },
];

export default function KnowledgeGraphPage() {
  const [search, setSearch] = useState("");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">知识图谱</h1>
        <p className="mt-2 text-sm text-slate-600">
          中阿文旅知识实体、关系与知识网络的可视化浏览
        </p>
      </div>

      {/* Search Bar */}
      <Card className="p-5">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索知识实体（文献、作者、机构、主题、地点...）"
              className="w-full rounded-md border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-navy"
            />
          </div>
          <Button variant="secondary">
            <Filter size={16} />
            筛选
          </Button>
          <Button>
            <Network size={16} />
            图谱视图
          </Button>
        </div>
      </Card>

      {/* Entity Type Stats */}
      <div className="grid grid-cols-4 gap-4">
        {entityTypes.map((et) => {
          const Icon = et.icon;
          return (
            <Card key={et.type} className="flex items-center gap-4 p-5">
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${et.color}`}
              >
                <Icon size={20} />
              </div>
              <div>
                <div className="text-xl font-semibold text-ink">{et.count}</div>
                <div className="text-xs text-slate-500">{et.type}</div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Main content: Entity list + Graph preview */}
      <div className="grid grid-cols-[1fr_1.5fr] gap-6">
        {/* Entity list */}
        <Card className="p-5">
          <h2 className="font-semibold text-ink">热门知识实体</h2>
          <div className="mt-4 space-y-3">
            {sampleEntities.map((entity) => (
              <div
                key={entity.name}
                className="group flex cursor-pointer items-center justify-between rounded-md border border-slate-100 px-4 py-3 transition hover:border-navy/20 hover:bg-slate-50"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-navy/5 text-navy">
                    <Network size={15} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-ink">
                      {entity.name}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Badge tone={entity.badge as any}>{entity.type}</Badge>
                      <span>{entity.relations} 条关系</span>
                    </div>
                  </div>
                </div>
                <ArrowRight
                  size={16}
                  className="text-slate-300 transition group-hover:text-navy"
                />
              </div>
            ))}
          </div>
        </Card>

        {/* Graph preview */}
        <Card className="flex items-center justify-center p-5">
          <div className="text-center">
            <Network size={48} className="mx-auto text-navy/20" />
            <h3 className="mt-4 text-sm font-medium text-ink">知识图谱可视化</h3>
            <p className="mt-2 text-xs text-slate-500">
              选择实体后展示其关联网络
              <br />
              支持力导向图、聚类图、时间轴视图
            </p>
            <Button className="mt-4" variant="secondary">
              打开图谱浏览器
            </Button>
          </div>
        </Card>
      </div>

      {/* Relation legend */}
      <Card className="p-5">
        <h2 className="font-semibold text-ink">关系类型</h2>
        <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-600">
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded bg-blue-400" />
            <span>引用关系</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded bg-emerald-400" />
            <span>合作关系</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded bg-purple-400" />
            <span>共现关系</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded bg-amber-400" />
            <span>隶属关系</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded bg-red-400" />
            <span>演化关系</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
