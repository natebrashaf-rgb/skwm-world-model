"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { skwmApi, type Overview } from "@/lib/api";
import {
  BookOpen,
  Search,
  RefreshCw,
  FileText,
  ExternalLink,
  Upload,
} from "lucide-react";

const nf = (x?: number) => (typeof x === "number" ? x.toLocaleString() : "—");

export default function LiteraturePage() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setOv(await skwmApi.overview());
      } catch (e: any) {
        setErr(e?.message || "后端未连接");
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">文献管理</h1>
          <p className="mt-2 text-sm text-slate-600">
            中阿文旅多语种文献资源库 · 全文检索与引文管理
          </p>
        </div>
        <Button>
          <Upload size={16} />
          导入文献
        </Button>
      </div>

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
        ℹ️ 本页实体/关系数据已接入世界模型；“全文索引、PDF
        原文、按章节分类”需另行接入文献库 API，当前为本地样例列表。
      </div>

      {err && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          ⚠️ 后端未连接（{err}），请运行{" "}
          <code className="rounded bg-amber-100 px-1">
            uvicorn api:app --port 8000
          </code>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="text-sm text-slate-500">知识实体 E</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.entities)}
          </div>
          <div className="mt-2 text-xs text-slate-500">图谱节点总量</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">知识关系 R</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.relations)}
          </div>
          <div className="mt-2 text-xs text-slate-500">共现/共引/合作边</div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">时间切片 T</div>
          <div className="mt-2 text-3xl font-semibold text-ink">
            {nf(ov?.snapshots)}
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {ov?.year_range?.[0]}–{ov?.year_range?.[1]}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-sm text-slate-500">引文格式</div>
          <div className="mt-2 text-3xl font-semibold text-ink">GB/T 7714</div>
          <div className="mt-2 text-xs text-slate-500">一键导出</div>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              placeholder="搜索论文标题、关键词、作者..."
              className="w-full rounded-md border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-navy"
            />
          </div>
          <Button variant="secondary">
            <RefreshCw size={16} />
            更新索引
          </Button>
          <Button variant="secondary">
            <ExternalLink size={16} />
            OpenAlex搜索
          </Button>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-ink">
            本地文献样例（待接入文献库 API）
          </h2>
        </div>
        <div className="divide-y divide-slate-100">
          {[
            {
              title: "科学学的科学_科学计量综述",
              file: "13-科学学的科学_科学计量综述.md",
              size: "PDF/MD",
            },
            {
              title: "科学计量学工具与方法综述",
              file: "18-科学计量学工具与方法综述.pdf",
              size: "PDF",
            },
            {
              title: "生成式AI与科学计量的未来",
              file: "7-生成式AI与科学计量的未来.pdf",
              size: "PDF",
            },
            {
              title: "知识图谱与大模型融合方法2023",
              file: "20-知识图谱与大模型融合方法2023.pdf",
              size: "PDF",
            },
          ].map((doc) => (
            <div
              key={doc.file}
              className="flex items-center justify-between px-5 py-3 hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <FileText size={16} className="text-slate-400" />
                <div>
                  <div className="text-sm font-medium text-ink">
                    {doc.title}
                  </div>
                  <div className="text-xs text-slate-500">{doc.file}</div>
                </div>
              </div>
              <Badge tone="slate">{doc.size}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
