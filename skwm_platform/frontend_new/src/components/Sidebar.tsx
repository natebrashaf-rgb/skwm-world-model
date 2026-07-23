import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Menu, X, BarChart3, Network, Flame, TrendingUp, LineChart, Map, MessageSquare, FileText, BookOpen, Clock, Database } from 'lucide-react'

interface NavItem { label: string; path: string; icon: typeof BarChart3 }
interface NavGroup { label: string; items: NavItem[] }

const groups: NavGroup[] = [
  { label: '数据资源层', items: [{ label: '数据总览', path: '/overview', icon: BarChart3 }] },
  { label: '知识组织层', items: [{ label: '知识图谱', path: '/graph', icon: Network }] },
  { label: '智能分析层', items: [
    { label: '热点分析', path: '/hotspot', icon: Flame },
    { label: '前沿识别', path: '/frontier', icon: TrendingUp },
    { label: '趋势预测', path: '/trend', icon: LineChart },
    { label: '科学地图', path: '/sciencemap', icon: Map },
  ]},
  { label: '智能服务层', items: [
    { label: '智能问答', path: '/qa', icon: MessageSquare },
    { label: '报告生成', path: '/report', icon: FileText },
  ]},
  { label: '理论模型', items: [{ label: 'SKWM 模型', path: '/model', icon: BookOpen }] },
  { label: '系统', items: [
    { label: '时间回溯', path: '/timeline', icon: Clock },
    { label: '数据概览', path: '/data', icon: Database },
  ]},
]

export function Sidebar() {
  const location = useLocation(); const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const nav = (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="px-4 pt-5 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-lg font-extrabold tracking-tight text-gray-900">SKWM</span>
          <span className="text-[10px] font-semibold bg-primary text-white px-1.5 py-0.5 rounded">v4</span>
        </div>
        <div className="text-xs text-gray-400 mt-0.5">中阿文旅世界模型</div>
      </div>
      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar px-2 py-3 space-y-4">
        {groups.map(g => (
          <div key={g.label}>
            <div className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">{g.label}</div>
            {g.items.map(item => {
              const active = location.pathname === item.path
              const Icon = item.icon
              return (
                <button key={item.path}
                  onClick={() => { navigate(item.path); setOpen(false) }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors
                    ${active ? 'bg-primary-50 text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                  <Icon size={16} strokeWidth={1.5} />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </div>
        ))}
      </nav>
      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-100 text-[10px] text-gray-400 leading-relaxed">
        北京第二外国语学院<br />挑战杯 · SKWM v4.0
      </div>
    </div>
  )

  return (
    <>
      {/* Mobile hamburger */}
      <button onClick={() => setOpen(true)} className="lg:hidden fixed top-3 left-3 z-50 p-2 bg-white border border-gray-200 rounded-lg shadow-sm">
        <Menu size={18} />
      </button>
      {/* Mobile drawer */}
      {open && <div className="fixed inset-0 z-40 lg:hidden">
        <div className="absolute inset-0 bg-black/20" onClick={() => setOpen(false)} />
        <div className="absolute left-0 top-0 bottom-0 w-60 bg-white shadow-xl">{nav}</div>
      </div>}
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-56 border-r border-gray-100 bg-white flex-shrink-0">{nav}</aside>
    </>
  )
}
