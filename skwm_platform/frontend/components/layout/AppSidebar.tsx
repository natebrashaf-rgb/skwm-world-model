"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Network,
  Bot,
  BarChart3,
  BookOpen,
  Compass,
  FileText,
  Settings,
  Menu,
  X,
  Globe2,
  ShieldCheck,
  Eye,
} from "lucide-react";

const nav = [
  { href: "/dashboard", label: "工作台", icon: LayoutDashboard },
  { href: "/cockpit", label: "领导驾驶舱", icon: Eye },
  { href: "/knowledge-graph", label: "知识图谱", icon: Network },
  { href: "/rag-advisor", label: "智能问答", icon: Bot },
  { href: "/scientometrics", label: "科学计量", icon: BarChart3 },
  { href: "/librarian", label: "馆员工作台", icon: ShieldCheck },
  { href: "/literature", label: "文献管理", icon: BookOpen },
  { href: "/scenarios", label: "应用场景", icon: Compass },
  { href: "/reports", label: "报告中心", icon: FileText },
  { href: "/settings", label: "系统设置", icon: Settings },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="h-fit w-56 rounded-lg border border-slate-200 bg-white p-3 shadow-panel">
      <nav className="space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-navy text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-ink"
              }`}
            >
              <Icon size={17} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-4 border-t border-slate-100 pt-3">
        <div className="rounded-md bg-mist px-3 py-2 text-xs text-slate-500">
          <div className="flex items-center gap-1.5 font-medium text-navy">
            <Globe2 size={12} />
            SKWM v1.0
          </div>
          <div className="mt-1">E+R+S+T+C+U+P</div>
        </div>
      </div>
    </aside>
  );
}

export function AppSidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="fixed top-4 left-4 z-50 rounded-md bg-white p-2 shadow-lg lg:hidden"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={mobileOpen ? "关闭导航" : "打开导航"}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 lg:hidden"
          onClick={() => setMobileOpen(false)}
        >
          <div className="w-56 p-4" onClick={(e) => e.stopPropagation()}>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Desktop */}
      <div className="hidden lg:block">
        <SidebarContent />
      </div>
    </>
  );
}
