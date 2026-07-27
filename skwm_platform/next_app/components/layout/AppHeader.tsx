import { GraduationCap } from "lucide-react";

export function AppHeader() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-navy text-white">
            <GraduationCap size={18} />
          </div>
          <div>
            <div className="font-semibold text-ink">SKWM 智能学科服务平台</div>
            <div className="text-xs text-slate-500">
              科学知识世界模型 · 中阿文旅知识服务
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-600">
          <span className="hidden sm:inline">北京第二外国语学院 · 图书馆</span>
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-navy/10 text-xs font-medium text-navy">
            馆
          </div>
        </div>
      </div>
    </header>
  );
}
