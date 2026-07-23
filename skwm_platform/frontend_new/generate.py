#!/usr/bin/env python3
"""Generate SKWM React frontend — all files in one shot"""
import os

BASE = r"E:\大挑\rail_deploy\skwm_platform\frontend_new"

def w(rel, content):
    path = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  {rel}")

# ═══════════════════════════════════════════
# 1. Config files
# ═══════════════════════════════════════════

w("package.json", r"""{
  "name": "skwm-frontend",
  "private": true,
  "version": "4.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "recharts": "^2.13.3",
    "d3-force": "^3.0.0",
    "@types/d3-force": "^3.0.10"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3",
    "vite": "^6.0.3"
  }
}
""")

w("vite.config.ts", """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  server: { port: 3000 }
})
""")

w("tsconfig.json", """{
  "compilerOptions": {
    "target": "ES2020", "useDefineForClassFields": true, "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext", "skipLibCheck": true,
    "moduleResolution": "bundler", "allowImportingTsExtensions": true, "isolatedModules": true,
    "moduleDetection": "force", "noEmit": true, "jsx": "react-jsx",
    "strict": true, "noUnusedLocals": false, "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true, "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true, "esModuleInterop": true
  },
  "include": ["src"]
}
""")

w("tsconfig.node.json", """{ "compilerOptions": { "target": "ES2022", "lib": ["ES2023"], "module": "ESNext", "skipLibCheck": true, "moduleResolution": "bundler", "allowImportingTsExtensions": true, "isolatedModules": true, "moduleDetection": "force", "noEmit": true }, "include": ["vite.config.ts"] }
""")

w("postcss.config.js", """export default { plugins: { tailwindcss: {}, autoprefixer: {} } }
""")

w("tailwind.config.js", """/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: { primary: { DEFAULT: '#2563eb', 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 600: '#2563eb', 700: '#1d4ed8' } },
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'] }
    }
  },
  plugins: []
}
""")

w("index.html", """<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SKWM · 中阿文旅世界模型</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head><body class="bg-[#F7F8FA] text-gray-900 antialiased"><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>
""")

# ═══════════════════════════════════════════
# 2. Source entry + app + router
# ═══════════════════════════════════════════

w("src/main.tsx", """import React from 'react'; import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'; import App from './App'
import './index.css'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>
)
""")

w("src/index.css", """@tailwind base; @tailwind components; @tailwind utilities;
body { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }
""")

w("src/App.tsx", """import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import OverviewPage from './pages/OverviewPage'
import GraphPage from './pages/GraphPage'
import HotspotPage from './pages/HotspotPage'
import FrontierPage from './pages/FrontierPage'
import TrendPage from './pages/TrendPage'
import ScienceMapPage from './pages/ScienceMapPage'
import QaPage from './pages/QaPage'
import ReportPage from './pages/ReportPage'
import ModelPage from './pages/ModelPage'
import TimelinePage from './pages/TimelinePage'
import DataPage from './pages/DataPage'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/hotspot" element={<HotspotPage />} />
        <Route path="/frontier" element={<FrontierPage />} />
        <Route path="/trend" element={<TrendPage />} />
        <Route path="/sciencemap" element={<ScienceMapPage />} />
        <Route path="/qa" element={<QaPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route path="/model" element={<ModelPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/data" element={<DataPage />} />
      </Routes>
    </AppLayout>
  )
}
""")

# ═══════════════════════════════════════════
# 3. Shared components
# ═══════════════════════════════════════════

w("src/components/AppLayout.tsx", """import { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { DraggableChatBot } from './DraggableChatBot'

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F8FA]">
      <Sidebar />
      <main id="main-content" className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-6xl mx-auto px-6 py-8 pb-24">
          {children}
        </div>
      </main>
      <DraggableChatBot />
    </div>
  )
}
""")

w("src/components/Sidebar.tsx", """import { useLocation, useNavigate } from 'react-router-dom'
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
""")

w("src/components/DraggableChatBot.tsx", """import { useState, useRef, useCallback, useEffect } from 'react'
import { MessageSquare, X, Send } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; sources?: { type: string; id: string; year: number; confidence: number }[] }

export function DraggableChatBot() {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Message[]>([
    { role: 'assistant', content: '您好，我是 SKWM 智能助手。可以问我关于中阿文旅研究的问题。' }
  ])
  const [input, setInput] = useState('')
  const [dragging, setDragging] = useState(false)
  const [pos, setPos] = useState({ x: window.innerWidth - 80, y: window.innerHeight - 80 })
  const dragRef = useRef({ startX: 0, startY: 0, elX: 0, elY: 0, moved: false })
  const chatRef = useRef<HTMLDivElement>(null)

  const onSend = useCallback((text: string) => {
    if (!text.trim()) return
    setMsgs(prev => [...prev, { role: 'user', content: text },
      { role: 'assistant', content: `已收到您的问题：「${text}」。知识图谱检索到 5 篇相关文献，正在生成回答…（此为占位响应，待接入 GraphRAG 后端）`,
        sources: [{ type: '文献', id: 'SKWM-2024-001', year: 2024, confidence: 0.92 }] }])
    setInput('')
  }, [])

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if (open) return
    setDragging(true); dragRef.current = { startX: e.clientX, startY: e.clientY, elX: pos.x, elY: pos.y, moved: false }
  }, [open, pos])

  const onPointerMove = useCallback((e: PointerEvent) => {
    if (!dragging) return
    const dx = e.clientX - dragRef.current.startX, dy = e.clientY - dragRef.current.startY
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) dragRef.current.moved = true
    setPos({ x: dragRef.current.elX + dx, y: dragRef.current.elY + dy })
  }, [dragging])

  const onPointerUp = useCallback(() => {
    setDragging(false)
    if (!dragRef.current.moved && !open) setOpen(true)
  }, [open])

  useEffect(() => {
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    return () => { window.removeEventListener('pointermove', onPointerMove); window.removeEventListener('pointerup', onPointerUp) }
  }, [onPointerMove, onPointerUp])

  useEffect(() => { if (open && chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight }, [msgs, open])

  return (
    <>
      {/* Chat panel */}
      {open && <div className="fixed bottom-4 right-4 z-50 w-80 sm:w-96 bg-white border border-gray-200 rounded-xl shadow-xl flex flex-col overflow-hidden" style={{ maxHeight: '70vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <span className="text-sm font-semibold text-gray-800">SKWM 智能问答</span>
          <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={16} /></button>
        </div>
        <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar" style={{ minHeight: 200 }}>
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'bg-primary text-white' : 'bg-gray-50 text-gray-700 border border-gray-100'}`}>
                {m.content}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {m.sources.map((s, j) => (
                      <div key={j} className="text-[11px] text-gray-400 flex gap-2">
                        <span className="font-medium">{s.type}</span>
                        <span>{s.id}</span>
                        <span>{s.year}</span>
                        <span>{Math.round(s.confidence * 100)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSend(input)}
            placeholder="输入问题..." className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary-200" />
          <button onClick={() => onSend(input)} className="p-2 text-primary hover:bg-primary-50 rounded-lg"><Send size={16} /></button>
        </div>
      </div>}

      {/* Floating button */}
      <button
        onPointerDown={onPointerDown}
        onClick={() => { if (!dragRef.current.moved) setOpen(v => !v) }}
        className="fixed z-50 w-12 h-12 bg-primary text-white rounded-full shadow-lg flex items-center justify-center hover:bg-primary-700 transition-colors cursor-grab active:cursor-grabbing select-none"
        style={{ left: pos.x, top: pos.y, transform: 'translate(-50%, -50%)' }}
      >
        <MessageSquare size={20} />
      </button>
    </>
  )
}
""")

w("src/components/StatCard.tsx", """import { LucideIcon } from 'lucide-react'

export function StatCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <Icon size={18} strokeWidth={1.5} className="text-gray-400 mb-2" />
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}
""")

w("src/components/Breadcrumb.tsx", """export function Breadcrumb({ items }: { items: string[] }) {
  return (
    <div className="text-[11px] font-semibold tracking-wider text-primary uppercase mb-2">
      {items.join(' / ')}
    </div>
  )
}
""")

w("src/components/HotspotBarList.tsx", """interface HotspotItem { rank: number; name: string; value: number }
export function HotspotBarList({ data, max }: { data: HotspotItem[]; max?: number }) {
  const mx = max || Math.max(...data.map(d => d.value), 1)
  return (
    <div className="space-y-1.5">
      {data.map(d => (
        <div key={d.rank} className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-4 text-right shrink-0">{d.rank}</span>
          <span className="text-xs text-gray-700 w-28 truncate shrink-0">{d.name}</span>
          <div className="h-3.5 rounded bg-primary-100 flex-shrink-0" style={{ width: `${(d.value / mx) * 100}%`, maxWidth: 200 }} />
          <span className="text-xs text-gray-500 font-medium">{d.value}</span>
        </div>
      ))}
    </div>
  )
}
""")

# ═══════════════════════════════════════════
# 4. Mock data
# ═══════════════════════════════════════════

w("src/data/overview.ts", """export interface OverviewStats {
  stateVectors: number; relations: number; snapshots: number; totalDocs: number
}
export const overviewStats: OverviewStats = { stateVectors: 43537, relations: 586912, snapshots: 89, totalDocs: 15478 }

export interface HotspotItem { rank: number; name: string; value: number }
export const topHotspots: HotspotItem[] = [
  { rank: 1, name: 'tourism', value: 50 }, { rank: 2, name: 'system', value: 10 },
  { rank: 3, name: 'model', value: 9 }, { rank: 4, name: 'network', value: 6 },
  { rank: 5, name: 'learning', value: 3 }, { rank: 6, name: 'knowledge', value: 2 },
  { rank: 7, name: 'data', value: 1 }, { rank: 8, name: 'heritage', value: 1 },
  { rank: 9, name: 'digital', value: 1 }, { rank: 10, name: 'travel', value: 1 },
]

export interface FrontierItem { rank: number; name: string; growth: number }
export const topFrontiers: FrontierItem[] = [
  { rank: 1, name: 'tourism', growth: 8760 }, { rank: 2, name: 'heritage', growth: 4760 },
  { rank: 3, name: 'model', growth: 4680 }, { rank: 4, name: 'arab', growth: 3860 },
  { rank: 5, name: 'language', growth: 3500 },
]

export interface TimelineYear { year: number; nodes: number }
export const timelineData: TimelineYear[] = Array.from({ length: 89 }, (_, i) => ({
  year: 1937 + i, nodes: Math.round(3 * Math.exp(0.05 * i) * (1 + Math.random() * 0.2))
}))
""")

w("src/data/graph-data.ts", """export interface GraphNode {
  id: string; label_zh: string; label_en: string; label_ar: string
  type: string; degree: number; group: string
}
export interface GraphLink { source: string; target: string; relation: string }

const types = ['文献','作者','机构','主题','地点','政策','项目','事件','术语']

export const graphNodes: GraphNode[] = [
  { id: 'n1', label_zh: '文化遗产旅游', label_en: 'Cultural Heritage Tourism', label_ar: 'سياحة التراث الثقافي', type: '主题', degree: 8, group: '主题' },
  { id: 'n2', label_zh: '阿拉伯国家旅游传播', label_en: 'Arab Tourism Communication', label_ar: 'الاتصال السياحي العربي', type: '主题', degree: 6, group: '主题' },
  { id: 'n3', label_zh: '北京第二外国语学院', label_en: 'Beijing International Studies University', label_ar: 'جامعة بكين للدراسات الدولية', type: '机构', degree: 7, group: '机构' },
  { id: 'n4', label_zh: '中阿文旅知识图谱', label_en: 'Sino-Arab Cultural Tourism KG', label_ar: 'المعرفة السياحية الثقافية الصينية العربية', type: '主题', degree: 5, group: '主题' },
  { id: 'n5', label_zh: 'GraphRAG', label_en: 'GraphRAG', label_ar: 'غراف آر إيه جي', type: '术语', degree: 6, group: '术语' },
  { id: 'n6', label_zh: '非物质文化遗产', label_en: 'Intangible Cultural Heritage', label_ar: 'التراث الثقافي غير المادي', type: '主题', degree: 4, group: '主题' },
  { id: 'n7', label_zh: '一带一路', label_en: 'Belt and Road Initiative', label_ar: 'مبادرة الحزام والطريق', type: '政策', degree: 5, group: '政策' },
  { id: 'n8', label_zh: '中阿合作论坛', label_en: 'China-Arab Cooperation Forum', label_ar: 'منتدى التعاون الصيني العربي', type: '政策', degree: 3, group: '政策' },
  { id: 'n9', label_zh: '沙特阿拉伯', label_en: 'Saudi Arabia', label_ar: 'المملكة العربية السعودية', type: '地点', degree: 4, group: '地点' },
  { id: 'n10', label_zh: '阿联酋', label_en: 'United Arab Emirates', label_ar: 'الإمارات العربية المتحدة', type: '地点', degree: 3, group: '地点' },
  { id: 'n11', label_zh: '图书馆学科服务', label_en: 'Library Subject Services', label_ar: 'خدمات المكتبات الموضوعية', type: '主题', degree: 5, group: '主题' },
  { id: 'n12', label_zh: '大语言模型', label_en: 'Large Language Model', label_ar: 'نموذج اللغة الكبير', type: '术语', degree: 4, group: '术语' },
  { id: 'n13', label_zh: '科学计量学', label_en: 'Scientometrics', label_ar: 'القياسات العلمية', type: '术语', degree: 3, group: '术语' },
  { id: 'n14', label_zh: '阿拉伯语自然语言处理', label_en: 'Arabic NLP', label_ar: 'معالجة اللغة العربية الطبيعية', type: '术语', degree: 3, group: '术语' },
  { id: 'n15', label_zh: '数字文旅', label_en: 'Digital Cultural Tourism', label_ar: 'السياحة الثقافية الرقمية', type: '主题', degree: 4, group: '主题' },
  { id: 'n16', label_zh: '中国', label_en: 'China', label_ar: 'الصين', type: '地点', degree: 5, group: '地点' },
  { id: 'n17', label_zh: '埃及', label_en: 'Egypt', label_ar: 'مصر', type: '地点', degree: 2, group: '地点' },
  { id: 'n18', label_zh: '跨文化传播', label_en: 'Cross-cultural Communication', label_ar: 'التواصل بين الثقافات', type: '主题', degree: 3, group: '主题' },
  { id: 'n19', label_zh: '张教授', label_en: 'Prof. Zhang', label_ar: 'البروفيسور تشانغ', type: '作者', degree: 3, group: '作者' },
  { id: 'n20', label_zh: '李教授', label_en: 'Prof. Li', label_ar: 'البروفيسور لي', type: '作者', degree: 2, group: '作者' },
  { id: 'n21', label_zh: '中阿文明交流', label_en: 'Sino-Arab Civilization Exchange', label_ar: 'التبادل الحضاري الصيني العربي', type: '项目', degree: 3, group: '项目' },
  { id: 'n22', label_zh: '世界模型理论', label_en: 'World Model Theory', label_ar: 'نظرية النموذج العالمي', type: '文献', degree: 4, group: '文献' },
  { id: 'n23', label_zh: '2024文旅融合研讨会', label_en: '2024 Culture-Tourism Symposium', label_ar: 'ندوة دمج الثقافة والسياحة 2024', type: '事件', degree: 2, group: '事件' },
  { id: 'n24', label_zh: '知识蒸馏', label_en: 'Knowledge Distillation', label_ar: 'تقطير المعرفة', type: '术语', degree: 2, group: '术语' },
  { id: 'n25', label_zh: '智能问答系统', label_en: 'Intelligent QA System', label_ar: 'نظام الإجابة الذكي', type: '主题', degree: 3, group: '主题' },
]

export const graphLinks: GraphLink[] = [
  { source: 'n1', target: 'n2', relation: '共现' }, { source: 'n1', target: 'n3', relation: '隶属' },
  { source: 'n1', target: 'n4', relation: '对应' }, { source: 'n1', target: 'n6', relation: '共现' },
  { source: 'n2', target: 'n3', relation: '合作' }, { source: 'n2', target: 'n9', relation: '对应' },
  { source: 'n2', target: 'n10', relation: '对应' }, { source: 'n3', target: 'n19', relation: '隶属' },
  { source: 'n3', target: 'n20', relation: '隶属' }, { source: 'n4', target: 'n5', relation: '对应' },
  { source: 'n4', target: 'n11', relation: '影响' }, { source: 'n4', target: 'n15', relation: '共现' },
  { source: 'n5', target: 'n12', relation: '引用' }, { source: 'n5', target: 'n22', relation: '引用' },
  { source: 'n6', target: 'n15', relation: '演化' }, { source: 'n7', target: 'n8', relation: '共现' },
  { source: 'n7', target: 'n16', relation: '对应' }, { source: 'n7', target: 'n21', relation: '影响' },
  { source: 'n8', target: 'n21', relation: '隶属' }, { source: 'n9', target: 'n16', relation: '合作' },
  { source: 'n10', target: 'n16', relation: '合作' }, { source: 'n11', target: 'n22', relation: '影响' },
  { source: 'n12', target: 'n24', relation: '引用' }, { source: 'n13', target: 'n4', relation: '引用' },
  { source: 'n14', target: 'n2', relation: '对应' }, { source: 'n15', target: 'n18', relation: '共现' },
  { source: 'n18', target: 'n21', relation: '影响' }, { source: 'n19', target: 'n20', relation: '合作' },
  { source: 'n22', target: 'n5', relation: '引用' }, { source: 'n23', target: 'n1', relation: '共现' },
  { source: 'n23', target: 'n15', relation: '共现' }, { source: 'n25', target: 'n5', relation: '引用' },
  { source: 'n25', target: 'n11', relation: '对应' },
]

export const typeColors: Record<string, string> = {
  '文献': '#e0e7ff', '作者': '#ccfbf1', '机构': '#fef3c7', '主题': '#dbeafe',
  '地点': '#d1fae5', '政策': '#fce7f3', '项目': '#ede9fe', '事件': '#fff7ed', '术语': '#f5f5f4',
}
""")

w("src/data/model-data.ts", """export interface SkwmDimension {
  letter: string; nameZh: string; nameEn: string; definition: string; elements: string[]
}
export const skwmDimensions: SkwmDimension[] = [
  { letter: 'E', nameZh: '知识实体', nameEn: 'Entity', definition: '文献、作者、机构、主题、地点、政策、项目、事件、术语',
    elements: ['文献','作者','机构','主题','地点','政策','项目','事件','术语'] },
  { letter: 'R', nameZh: '知识关系', nameEn: 'Relation', definition: '引用、合作、共现、对应、影响、演化、隶属',
    elements: ['引用','合作','共现','对应','影响','演化','隶属'] },
  { letter: 'S', nameZh: '知识状态', nameEn: 'State', definition: '主题热度、合作强度、前沿程度、语言分布、传播范围',
    elements: ['主题热度','合作强度','前沿程度','语言分布','传播范围'] },
  { letter: 'T', nameZh: '时间序列', nameEn: 'Time', definition: '年度演化、阶段变化、突现主题',
    elements: ['年度演化','阶段变化','突现主题'] },
  { letter: 'C', nameZh: '语境变量', nameEn: 'Context', definition: '国家政策、区域合作、学科方向、国际形势',
    elements: ['国家政策','区域合作','学科方向','国际形势'] },
  { letter: 'U', nameZh: '用户需求', nameEn: 'User', definition: '教师科研、学生学习、馆员服务、科研管理',
    elements: ['教师科研','学生学习','馆员服务','科研管理'] },
  { letter: 'P', nameZh: '服务规则', nameEn: 'Policy', definition: '推荐规则、审核规则、推送规则、沉淀规则',
    elements: ['推荐规则','审核规则','推送规则','沉淀规则'] },
]
""")

w("src/data/data-sources.ts", """export interface DataSource {
  name: string; language: string; count: number; updated: string
}
export const dataSources: DataSource[] = [
  { name: '中文文献', language: '中文', count: 6284, updated: '2026-07' },
  { name: '阿文文献', language: '阿拉伯语', count: 4193, updated: '2026-07' },
  { name: '英文文献', language: '英语', count: 5001, updated: '2026-07' },
  { name: '政策文本', language: '中/阿/英', count: 156, updated: '2026-06' },
  { name: '馆藏书目', language: '中文', count: 892, updated: '2026-05' },
  { name: '新闻会议', language: '中/阿/英', count: 423, updated: '2026-07' },
  { name: '文旅项目', language: '中文', count: 215, updated: '2026-04' },
  { name: '服务日志', language: '中文', count: 1204, updated: '2026-07' },
]
""")

# ═══════════════════════════════════════════
# 5. All page components
# ═══════════════════════════════════════════

w("src/pages/OverviewPage.tsx", """import { Breadcrumb } from '../components/Breadcrumb'
import { StatCard } from '../components/StatCard'
import { HotspotBarList } from '../components/HotspotBarList'
import { BarChart, Bar, XAxis, ResponsiveContainer } from 'recharts'
import { Database, Share2, Layers, BookOpen } from 'lucide-react'
import { overviewStats, topHotspots, topFrontiers, timelineData } from '../data/overview'

export default function OverviewPage() {
  return (
    <div>
      <Breadcrumb items={['OVERVIEW']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">中阿文旅世界模型</h1>
      <p className="text-sm text-gray-400 mb-6">89 年时间序列 · {overviewStats.stateVectors.toLocaleString()} 条状态向量 · XGBoost AUC=0.94</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon={Database} label="状态向量" value={overviewStats.stateVectors.toLocaleString()} />
        <StatCard icon={Share2} label="知识关系" value={overviewStats.relations.toLocaleString()} />
        <StatCard icon={Layers} label="年切片" value={String(overviewStats.snapshots)} />
        <StatCard icon={BookOpen} label="文献总数" value={overviewStats.totalDocs.toLocaleString()} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">热点 TOP 10</h3>
          <HotspotBarList data={topHotspots} />
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">前沿 TOP 5</h3>
          <div className="space-y-2">
            {topFrontiers.map(f => (
              <div key={f.rank} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-4">{f.rank}</span>
                  <span className="text-sm text-gray-700">{f.name}</span>
                </div>
                <span className="text-xs font-medium text-green-600">+{f.growth.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">89 年时间线</h3>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={timelineData.slice(-60)}>
            <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#9ca3af' }} tickFormatter={y => String(y)} interval={9} />
            <Bar dataKey="nodes" fill="#dbeafe" radius={[2,2,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
""")

w("src/pages/GraphPage.tsx", """import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3-force'
import { Breadcrumb } from '../components/Breadcrumb'
import { graphNodes, graphLinks, typeColors } from '../data/graph-data'

const TYPE_LIST = ['文献','作者','机构','主题','地点','政策','项目','事件','术语']
const RELATION_LIST = ['引用','合作','共现','对应','影响','演化','隶属']

export default function GraphPage() {
  const [selected, setSelected] = useState<string | null>(null)
  const [filterTypes, setFilterTypes] = useState<string[]>(TYPE_LIST)
  const [search, setSearch] = useState('')
  const svgRef = useRef<SVGSVGElement>(null)
  const [dim, setDim] = useState({ w: 700, h: 500 })

  const filtered = graphNodes.filter(n => filterTypes.includes(n.type) && (!search || n.label_zh.includes(search) || n.label_en.toLowerCase().includes(search.toLowerCase())))
  const nodeIds = new Set(filtered.map(n => n.id))
  const flinks = graphLinks.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target))

  const simRef = useRef<any>(null)

  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    const w = dim.w, h = dim.h

    const nodes = filtered.map(n => ({ ...n, x: w/2 + (Math.random()-0.5)*200, y: h/2 + (Math.random()-0.5)*200 }))
    const links = flinks.map(l => ({ source: l.source, target: l.target, relation: l.relation }))

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(w/2, h/2))
    simRef.current = sim

    const linkGrp = svg.append('g')
    const linkEls = linkGrp.selectAll('line').data(links).join('line')
      .attr('stroke', '#e5e7eb').attr('stroke-width', 1).attr('stroke-opacity', 0.6)

    const nodeGrp = svg.append('g')
    const nodeEls = nodeGrp.selectAll('g').data(nodes).join('g')
      .call(d3.drag<any, any>()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      ) as any

    nodeEls.append('circle')
      .attr('r', d => Math.max(5, Math.sqrt((d as any).degree) * 4))
      .attr('fill', d => typeColors[d.type] || '#f5f5f4')
      .attr('stroke', '#cbd5e1').attr('stroke-width', 1)
      .attr('cursor', 'pointer')
      .on('click', (e: any, d: any) => { e.stopPropagation(); setSelected(d.id) })

    nodeEls.append('text')
      .text(d => d.label_zh.length > 6 ? d.label_zh.slice(0,6)+'..' : d.label_zh)
      .attr('dx', 0).attr('dy', d => Math.max(5, Math.sqrt(d.degree)*4) + 12)
      .attr('text-anchor', 'middle').attr('font-size', 9).attr('fill', '#6b7280')

    // Highlight on hover
    nodeEls.on('mouseenter', function(e: any, d: any) {
      const neighbors = new Set(links.filter(l => l.source.id === d.id || l.target.id === d.id).flatMap(l => [l.source.id, l.target.id]))
      neighbors.add(d.id)
      nodeEls.attr('opacity', n => neighbors.has(n.id) ? 1 : 0.15)
      linkEls.attr('stroke-opacity', l => l.source.id === d.id || l.target.id === d.id ? 0.8 : 0.05)
    }).on('mouseleave', () => { nodeEls.attr('opacity', 1); linkEls.attr('stroke-opacity', 0.6) })

    sim.on('tick', () => {
      linkEls.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any => d.target.y))
      nodeEls.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    svg.on('click', () => setSelected(null))

    return () => { sim.stop() }
  }, [filterTypes, search, dim])

  useEffect(() => {
    const resize = () => setDim({ w: Math.max(400, (document.getElementById('graph-area')?.clientWidth || 700) - 20), h: 500 })
    resize(); window.addEventListener('resize', resize); return () => window.removeEventListener('resize', resize)
  }, [])

  const selNode = graphNodes.find(n => n.id === selected)
  const selLinks = selNode ? graphLinks.filter(l => l.source === selNode.id || l.target === selNode.id) : []

  return (
    <div>
      <Breadcrumb items={['KNOWLEDGE GRAPH']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">知识图谱</h1>

      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Left: Filter */}
        <div className="w-full lg:w-44 shrink-0 space-y-3">
          <div>
            <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">实体类型</div>
            <div className="flex flex-wrap gap-1.5">
              {TYPE_LIST.map(t => (
                <button key={t} onClick={() => setFilterTypes(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t])}
                  className={`px-2 py-0.5 text-[11px] rounded border transition-colors ${filterTypes.includes(t) ? 'bg-primary-50 border-primary-200 text-primary' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>{t}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">搜索</div>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="名称..." className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:outline-none focus:border-primary-200" />
          </div>
          {/* Legend */}
          <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">图例</div>
          {TYPE_LIST.map(t => (
            <div key={t} className="flex items-center gap-2 text-xs text-gray-500 mb-1">
              <span className="w-3 h-3 rounded-full inline-block" style={{ background: typeColors[t] || '#f5f5f4', border: '1px solid #cbd5e1' }} />
              {t}
            </div>
          ))}
        </div>

        {/* Center: Graph */}
        <div id="graph-area" className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <svg ref={svgRef} width={dim.w} height={dim.h} className="w-full" />
        </div>

        {/* Right: Detail */}
        <div className="w-full lg:w-56 shrink-0">
          {selNode ? (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-800 mb-2">{selNode.label_zh}</h3>
              <div className="space-y-1 text-xs text-gray-500">
                <div><span className="text-gray-400">类型：</span>{selNode.type}</div>
                <div><span className="text-gray-400">英文：</span>{selNode.label_en}</div>
                <div><span className="text-gray-400">阿文：</span>{selNode.label_ar}</div>
                <div><span className="text-gray-400">关系数：</span>{selLinks.length}</div>
                <div className="pt-2 border-t border-gray-100 mt-2">
                  <div className="text-gray-400 mb-1">相邻节点：</div>
                  {selLinks.map(l => {
                    const other = graphNodes.find(n => n.id === (l.source === selNode.id ? l.target : l.source))
                    return other ? <div key={l.source+l.target} className="flex justify-between"><span>{other.label_zh}</span><span className="text-gray-400">{l.relation}</span></div> : null
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm text-xs text-gray-400 space-y-1">
              <div>节点：{graphNodes.length}</div>
              <div>关系：{graphLinks.length}</div>
              <div className="pt-2 border-t border-gray-100 mt-2">
                {TYPE_LIST.map(t => {
                  const cnt = graphNodes.filter(n => n.type === t).length
                  return cnt > 0 ? <div key={t} className="flex justify-between"><span>{t}</span><span>{cnt}</span></div> : null
                })}
              </div>
              <p className="pt-2 text-[10px]">点击节点查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
""")

w("src/pages/HotspotPage.tsx", """import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { HotspotBarList } from '../components/HotspotBarList'
import { topHotspots } from '../data/overview'

export default function HotspotPage() {
  const [range, setRange] = useState('all')
  const data = topHotspots
  return (
    <div>
      <Breadcrumb items={['HOTSPOTS']} />
      <div className="flex items-center justify-between mb-4">
        <div><h1 className="text-2xl font-bold text-gray-900">热点分析</h1><p className="text-sm text-gray-400">关键词热度排行</p></div>
        <select value={range} onChange={e => setRange(e.target.value)} className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-white">
          <option value="all">全部</option><option value="10">近 10 年</option><option value="5">近 5 年</option>
        </select>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">关键词热度 TOP 20</h3>
        <HotspotBarList data={data} />
      </div>
    </div>
  )
}
""")

w("src/pages/FrontierPage.tsx", """import { Breadcrumb } from '../components/Breadcrumb'
import { topFrontiers } from '../data/overview'

export default function FrontierPage() {
  return (
    <div>
      <Breadcrumb items={['FRONTIER']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">前沿识别</h1>
      <p className="text-sm text-gray-400 mb-6">基于科学计量的前沿与突现主题检测</p>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">前沿主题 TOP 5</h3>
        <div className="space-y-3">
          {topFrontiers.map(f => (
            <div key={f.rank} className="flex items-center justify-between py-2 border-b border-gray-50">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-5">{f.rank}</span>
                <span className="text-sm font-medium text-gray-800">{f.name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs font-semibold text-green-600">+{f.growth.toLocaleString()}</span>
                <svg width="60" height="20" className="text-green-300"><polyline fill="none" stroke="currentColor" strokeWidth="1.5" points="0,15 10,12 20,16 30,8 40,10 50,4 60,2" /></svg>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">突现主题检测</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-100"><th className="text-left py-2 font-medium">主题</th><th className="text-left py-2 font-medium">突现年份</th><th className="text-left py-2 font-medium">强度</th><th className="text-left py-2 font-medium">状态</th></tr></thead>
          <tbody>
            {[['generative ai','2024','8.42','上升'],['GraphRAG','2024','6.71','上升'],['大语言模型','2023','5.83','成熟'],['数字文旅','2021','4.25','成熟'],['文化遗产数字化','2022','3.96','稳定']].map((r,i) => (
              <tr key={i} className="border-b border-gray-50"><td className="py-2 text-gray-700">{r[0]}</td><td className="py-2 text-gray-500">{r[1]}</td><td className="py-2 text-gray-500">{r[2]}</td><td className="py-2"><span className={`px-1.5 py-0.5 rounded text-[10px] ${r[3]==='上升'?'bg-green-50 text-green-600':r[3]==='成熟'?'bg-blue-50 text-blue-600':'bg-gray-50 text-gray-500'}`}>{r[3]}</span></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
""")

w("src/pages/TrendPage.tsx", """import { Breadcrumb } from '../components/Breadcrumb'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Legend } from 'recharts'

const data = Array.from({length:20},(_,i)=>({year:2007+i, tourism:20+Math.random()*80+i*5, heritage:15+Math.random()*60+i*3, model:5+Math.random()*40+i*2, tourism_pred:20+Math.random()*80+i*5+20+Math.random()*30, heritage_pred:15+Math.random()*60+i*3+10+Math.random()*20}))

export default function TrendPage() {
  return (
    <div>
      <Breadcrumb items={['TREND']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">趋势预测</h1>
      <p className="text-sm text-gray-400 mb-6">XGBoost 模型 · AUC=0.94</p>
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={data}>
            <XAxis dataKey="year" tick={{fontSize:11,fill:'#9ca3af'}} />
            <YAxis tick={{fontSize:11,fill:'#9ca3af'}} />
            <Line type="monotone" dataKey="tourism" stroke="#2563eb" strokeWidth={2} dot={false} name="tourism (实际)" />
            <Line type="monotone" dataKey="heritage" stroke="#16a34a" strokeWidth={2} dot={false} name="heritage (实际)" />
            <Line type="monotone" dataKey="model" stroke="#d97706" strokeWidth={2} dot={false} name="model (实际)" />
            <Line type="monotone" dataKey="tourism_pred" stroke="#2563eb" strokeWidth={2} strokeDasharray="4 4" dot={false} name="tourism (预测)" />
            <Line type="monotone" dataKey="heritage_pred" stroke="#16a34a" strokeWidth={2} strokeDasharray="4 4" dot={false} name="heritage (预测)" />
            <Legend wrapperStyle={{fontSize:11}} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
""")

w("src/pages/ScienceMapPage.tsx", """import { Breadcrumb } from '../components/Breadcrumb'
import { ScatterChart, Scatter, XAxis, YAxis, ResponsiveContainer, Legend } from 'recharts'

const clusters = [
  { name: '文旅融合', data: Array.from({length:12},()=>({x:Math.random()*30,y:Math.random()*30})) },
  { name: '阿拉伯语NLP', data: Array.from({length:10},()=>({x:50+Math.random()*30,y:20+Math.random()*30})) },
  { name: '知识图谱', data: Array.from({length:8},()=>({x:30+Math.random()*20,y:50+Math.random()*30})) },
  { name: '科学计量', data: Array.from({length:6},()=>({x:60+Math.random()*30,y:60+Math.random()*30})) },
]

export default function ScienceMapPage() {
  return (
    <div>
      <Breadcrumb items={['SCIENCE MAP']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">科学地图</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart>
              <XAxis type="number" dataKey="x" tick={false} /><YAxis type="number" dataKey="y" tick={false} />
              {clusters.map((c,i) => <Scatter key={c.name} name={c.name} data={c.data} fill={['#2563eb','#16a34a','#d97706','#8b5cf6'][i]} opacity={0.5} />)}
              <Legend wrapperStyle={{fontSize:11}} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2">
          {clusters.map(c => <div key={c.name} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm text-xs"><span className="font-medium text-gray-700">{c.name}</span><div className="text-gray-400 mt-1">主题数：{c.data.length}</div></div>)}
        </div>
      </div>
    </div>
  )
}
""")

w("src/pages/QaPage.tsx", """import { useState, useRef, useEffect } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { Send, Plus } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; sources?: { type: string; id: string; year: number; confidence: number }[] }
interface Session { id: string; title: string; messages: Message[] }

export default function QaPage() {
  const [sessions, setSessions] = useState<Session[]>([{ id: 's1', title: '中阿文旅热点', messages: [] }])
  const [activeId, setActiveId] = useState('s1')
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const active = sessions.find(s => s.id === activeId)!

  const onSend = (text: string) => {
    if (!text.trim()) return
    const newMsgs: Message[] = [...active.messages, { role: 'user', content: text },
      { role: 'assistant', content: `关于「${text}」的查询结果：知识图谱检索到 5 篇相关文献。基于 GraphRAG 的多跳推理生成以下回答…（待接入后端）`,
        sources: [{ type: '文献', id: 'SKWM-2024-001', year: 2024, confidence: 0.92 }, { type: '图谱子图', id: '文旅融合', year: 2024, confidence: 0.87 }] }]
    setSessions(prev => prev.map(s => s.id === activeId ? { ...s, messages: newMsgs, title: s.messages.length === 0 ? text.slice(0, 20) : s.title } : s))
    setInput('')
  }

  useEffect(() => { endRef.current?.scrollIntoView() }, [active.messages])

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Session list */}
      <div className="w-44 shrink-0 space-y-1">
        <button onClick={() => { const id = 's' + Date.now(); setSessions(p => [...p, { id, title: '新会话', messages: [] }]); setActiveId(id) }}
          className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 mb-2"><Plus size={14} />新会话</button>
        {sessions.map(s => (
          <button key={s.id} onClick={() => setActiveId(s.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs ${s.id === activeId ? 'bg-primary-50 text-primary font-medium' : 'text-gray-600 hover:bg-gray-50'}`}>{s.title}</button>
        ))}
      </div>
      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          {active.messages.length === 0 && <div className="text-center text-gray-400 text-sm py-12">输入问题开始智能问答</div>}
          {active.messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[70%] rounded-lg px-3 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'bg-primary text-white' : 'bg-gray-50 text-gray-700 border border-gray-100'}`}>
                {m.content}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {m.sources.map((s, j) => (
                      <div key={j} className="bg-white border border-gray-100 rounded px-2 py-1 flex gap-2 text-[10px] text-gray-400">
                        <span className="font-medium text-gray-500">{s.type}</span>
                        <span>{s.id}</span>
                        <span>{s.year}</span>
                        <span>{Math.round(s.confidence * 100)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && onSend(input)}
            placeholder="输入问题..." className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary-200" />
          <button onClick={() => onSend(input)} className="p-2 text-primary hover:bg-primary-50 rounded-lg"><Send size={16} /></button>
        </div>
      </div>
    </div>
  )
}
""")

w("src/pages/ReportPage.tsx", """import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'

const TEMPLATES = ['研究热点分析报告', '需求调研报告', '学科服务案例']

export default function ReportPage() {
  const [tpl, setTpl] = useState(TEMPLATES[0])
  const [topic, setTopic] = useState('中阿文旅')
  const [preview, setPreview] = useState('')

  const generate = () => {
    setPreview(`# ${tpl}\n\n**主题**: ${topic}\n**生成时间**: 2026-07\n\n## 概述\n基于 SKWM 世界模型（89 年 × 43,537 条状态向量）的分析报告。\n\n## 研究发现\n- 核心热点：tourism (50), system (10), model (9)\n- 新兴前沿：tourism (+8,760), heritage (+4,760)\n- 数据来源：1,548 篇文献 · 8 个数据源\n\n## 方法说明\n本报告基于科学计量分析、知识图谱查询与 GraphRAG 智能问答生成。\n待接入后端后将提供完整可交互版本。`)
  }

  return (
    <div>
      <Breadcrumb items={['REPORT']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">报告生成</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-xs font-semibold text-gray-400 uppercase mb-3">报告模板</div>
            <div className="space-y-1">
              {TEMPLATES.map(t => (
                <button key={t} onClick={() => setTpl(t)}
                  className={`w-full text-left px-3 py-2 text-sm rounded-lg ${tpl === t ? 'bg-primary-50 text-primary font-medium' : 'text-gray-600 hover:bg-gray-50'}`}>{t}</button>
              ))}
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-xs font-semibold text-gray-400 uppercase mb-3">参数</div>
            <div className="space-y-2">
              <div><label className="text-xs text-gray-500">主题</label><input value={topic} onChange={e => setTopic(e.target.value)} className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded-lg mt-1" /></div>
              <div><label className="text-xs text-gray-500">时间范围</label><select className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded-lg mt-1"><option>近 5 年</option><option>近 10 年</option><option>全部</option></select></div>
              <button onClick={generate} className="w-full px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-700">生成报告</button>
            </div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-400 uppercase mb-3">预览</div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{preview || '选择模板和参数后点击生成'}</div>
        </div>
      </div>
    </div>
  )
}
""")

w("src/pages/ModelPage.tsx", """import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { skwmDimensions } from '../data/model-data'

export default function ModelPage() {
  const [view, setView] = useState<'grid' | 'ring'>('grid')
  const [active, setActive] = useState<string | null>(null)

  return (
    <div>
      <Breadcrumb items={['SKWM MODEL']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">科学知识世界模型</h1>
      <p className="text-sm text-gray-400 mb-6">SKWM = {E, R, S, T, C, U, P}</p>

      <div className="flex gap-2 mb-4">
        <button onClick={() => setView('grid')} className={`px-3 py-1.5 text-xs rounded-lg ${view==='grid'?'bg-primary text-white':'bg-white border border-gray-200 text-gray-600'}`}>集合视图</button>
        <button onClick={() => setView('ring')} className={`px-3 py-1.5 text-xs rounded-lg ${view==='ring'?'bg-primary text-white':'bg-white border border-gray-200 text-gray-600'}`}>关系环形</button>
      </div>

      {view === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {skwmDimensions.map(d => (
            <div key={d.letter} id={`dim-${d.letter}`}
              className={`bg-white border rounded-lg p-4 shadow-sm transition-colors ${active === d.letter ? 'border-primary-200 ring-1 ring-primary-100' : 'border-gray-200'}`}
              onMouseEnter={() => setActive(d.letter)} onMouseLeave={() => setActive(null)}>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-7 h-7 rounded bg-primary-50 text-primary font-bold text-sm flex items-center justify-center">{d.letter}</span>
                <div><div className="text-sm font-semibold text-gray-800">{d.nameZh}</div><div className="text-[10px] text-gray-400">{d.nameEn}</div></div>
              </div>
              <div className="text-xs text-gray-500 mb-2">{d.definition}</div>
              <div className="flex flex-wrap gap-1">{d.elements.map(e => <span key={e} className="px-1.5 py-0.5 bg-gray-50 text-gray-500 rounded text-[10px] border border-gray-100">{e}</span>)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-8 shadow-sm flex justify-center">
          <svg width="500" height="480" viewBox="0 0 500 480">
            {/* Center */}
            <circle cx="250" cy="240" r="36" fill="#eff6ff" stroke="#2563eb" strokeWidth="2" />
            <text x="250" y="244" textAnchor="middle" fontSize="12" fontWeight="bold" fill="#2563eb">SKWM</text>
            {/* 7 Dimensions in a circle */}
            {skwmDimensions.map((d, i) => {
              const angle = (i * 2 * Math.PI) / 7 - Math.PI / 2
              const cx = 250 + 150 * Math.cos(angle), cy = 240 + 150 * Math.sin(angle)
              return (
                <g key={d.letter}>
                  <line x1="250" y1="240" x2={cx} y2={cy} stroke={active === d.letter ? '#2563eb' : '#e5e7eb'} strokeWidth={active === d.letter ? 2 : 1} />
                  <circle cx={cx} cy={cy} r={active === d.letter ? 24 : 20} fill={active === d.letter ? '#eff6ff' : '#f9fafb'} stroke={active === d.letter ? '#2563eb' : '#d1d5db'} strokeWidth="1.5" />
                  <text x={cx} y={cy+1} textAnchor="middle" fontSize="11" fontWeight="bold" fill={active === d.letter ? '#2563eb' : '#6b7280'}>{d.letter}</text>
                  <text x={cx} y={cy+18} textAnchor="middle" fontSize="8" fill="#9ca3af">{d.nameZh}</text>
                </g>
              )
            })}
          </svg>
        </div>
      )}
    </div>
  )
}
""")

w("src/pages/TimelinePage.tsx", """import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { BarChart, Bar, XAxis, ResponsiveContainer } from 'recharts'
import { timelineData } from '../data/overview'

export default function TimelinePage() {
  const [year, setYear] = useState(2026)
  const yData = timelineData.find(d => d.year === year)
  return (
    <div>
      <Breadcrumb items={['TIMELINE']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">时间回溯</h1>
      <div className="flex items-center gap-4 mb-4">
        <input type="range" min={1937} max={2026} value={year} onChange={e => setYear(+e.target.value)} className="flex-1 accent-primary" />
        <span className="text-sm font-semibold text-gray-700 w-16">{year}</span>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">节点</div><div className="text-lg font-semibold">{yData?.nodes || 0}</div></div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">热点</div><div className="text-lg font-semibold">tourism (50)</div></div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">前沿</div><div className="text-lg font-semibold">+8,760</div></div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">切片</div><div className="text-lg font-semibold">{year - 1937 + 1}/89</div></div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={timelineData}>
            <XAxis dataKey="year" tick={{fontSize:9,fill:'#9ca3af'}} tickFormatter={y=>String(y)} interval={19} />
            <Bar dataKey="nodes" fill="#dbeafe" radius={[2,2,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
""")

w("src/pages/DataPage.tsx", """import { Breadcrumb } from '../components/Breadcrumb'
import { dataSources } from '../data/data-sources'

export default function DataPage() {
  const total = dataSources.reduce((s, d) => s + d.count, 0)
  return (
    <div>
      <Breadcrumb items={['DATA']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">数据概览</h1>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">数据源数量</div><div className="text-lg font-semibold">{dataSources.length}</div></div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm"><div className="text-xs text-gray-400">总记录数</div><div className="text-lg font-semibold">{total.toLocaleString()}</div></div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-xs">
          <thead><tr className="bg-gray-50 text-gray-400"><th className="text-left px-4 py-2.5 font-medium">数据源</th><th className="text-left px-4 py-2.5 font-medium">语言</th><th className="text-right px-4 py-2.5 font-medium">数量</th><th className="text-right px-4 py-2.5 font-medium">更新</th></tr></thead>
          <tbody>{dataSources.map(d => (
            <tr key={d.name} className="border-t border-gray-100"><td className="px-4 py-2.5 text-gray-700">{d.name}</td><td className="px-4 py-2.5 text-gray-500">{d.language}</td><td className="px-4 py-2.5 text-right text-gray-700 font-medium">{d.count.toLocaleString()}</td><td className="px-4 py-2.5 text-right text-gray-400">{d.updated}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
""")

print(f"\n✅ Generated {sum(len(files) for _, _, files in os.walk(BASE))} files in {BASE}")
