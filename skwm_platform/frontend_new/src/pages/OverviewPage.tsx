import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { BarChart, Bar, XAxis, ResponsiveContainer } from 'recharts'
import { Database, Share2, Layers, BookOpen, Info } from 'lucide-react'
import API, { OverviewData, HotspotItem, FrontierItem, TimelineYear } from '../data/api'

const ICONS = [Database, Share2, Layers, BookOpen]

function Tooltip({ text }: { text: string }) {
  return <span className="inline-flex items-center ml-1 group relative cursor-help">
    <Info size={12} className="text-gray-300 hover:text-gray-400" />
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 text-white text-[10px] rounded shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-10">{text}</span>
  </span>
}

export default function OverviewPage() {
  const [ov, setOv] = useState<OverviewData | null>(null)
  const [hot, setHot] = useState<HotspotItem[]>([])
  const [front, setFront] = useState<FrontierItem[]>([])
  const [tl, setTl] = useState<TimelineYear[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      API.overview().catch(e => { setError(e.message); return null }),
      API.hotspot('2026', 10).catch(() => null),
      API.frontier('2026', 5).catch(() => null),
      API.timeline(2000).catch(() => null),
    ]).then(([o, h, f, t]) => {
      if (o) setOv(o)
      if (h) setHot(h.hotspots)
      if (f) setFront(f.frontier)
      if (t) setTl(t.timeline)
    })
  }, [])

  if (error) return <div className="text-red-500 text-sm py-8 text-center">⚠️ {error}</div>
  if (!ov && !hot.length) return <div className="text-gray-400 text-sm py-12 text-center">加载中...</div>

  const stats = [
    { label: '知识图谱', value: ov?.state_vectors?.toLocaleString() || 'N/A', tip: '跨年状态向量总数，每个实体每年计为1条' },
    { label: '知识关系', value: ov?.knowledge_relations?.toLocaleString() || 'N/A', tip: '实体间无向关系总数（原始双计已校正）' },
    { label: '时间跨度', value: ov?.year_range || 'N/A', tip: '数据覆盖的年份范围' },
    { label: '最新实体', value: ov?.latest_year_entities?.toLocaleString() || 'N/A', tip: `${ov?.latest_year || '2026'}年的唯一实体数` },
  ]

  return (
    <div>
      <Breadcrumb items={['OVERVIEW']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">中阿文旅世界模型</h1>
      <p className="text-xs text-gray-400 mb-6">状态向量 · 89年切片 · 中阿英三语</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((s, i) => {
          const Icon = ICONS[i]
          return (
            <div key={s.label} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <Icon size={18} strokeWidth={1.5} className="text-gray-400 mb-2" />
              <div className="text-2xl font-semibold text-gray-900">{s.value}</div>
              <div className="text-xs text-gray-400">
                {s.label}
                <Tooltip text={s.tip} />
              </div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">研究热点 TOP 10</h3>
          {hot.length === 0 ? <div className="text-xs text-gray-400">暂无数据</div> : (
            <div className="space-y-1.5">
              {hot.map(h => (
                <div key={h.name} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-4 text-right shrink-0">{h.rank}</span>
                  <span className="text-xs text-gray-700 w-28 truncate shrink-0" title={h.label_zh || h.name}>{h.label_zh || h.name}</span>
                  <div className="h-3.5 rounded bg-primary-100 flex-shrink-0" style={{ width: `${(h.heat / hot[0].heat) * 100}%`, maxWidth: 200 }} />
                  <span className="text-xs text-gray-500 font-medium">{h.heat.toLocaleString()}</span>
                  {h.label_ar && <span className="text-[9px] text-gray-300" dir="rtl">{h.label_ar}</span>}
                </div>
              ))}
            </div>
          )}
          <div className="text-[9px] text-gray-300 mt-2">基于实体热度值排序，已合并同义词并过滤领域外噪声词</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">新兴前沿 TOP 5</h3>
          {front.length === 0 ? <div className="text-xs text-gray-400">暂无数据</div> : (
            <div className="space-y-2">
              {front.map(f => (
                <div key={f.name} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-4">{f.rank}</span>
                    <span className="text-sm text-gray-700">{f.label_zh || f.name}</span>
                    {f.label_ar && <span className="text-[9px] text-gray-300" dir="rtl">{f.label_ar}</span>}
                  </div>
                  <span className="text-xs font-medium text-green-600">+{f.growth.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
          <div className="text-[9px] text-gray-300 mt-2">基于年度热度增长量排序，已过滤噪声词</div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">时间线（2000-2026）</h3>
        {tl.length === 0 ? <div className="text-xs text-gray-400">暂无数据</div> : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={tl}>
              <XAxis dataKey="year" tick={{fontSize:10,fill:'#9ca3af'}} tickFormatter={y=>String(y)} interval={3} />
              <Bar dataKey="entities_clean" fill="#dbeafe" radius={[2,2,0,0]} name="实体数" />
            </BarChart>
          </ResponsiveContainer>
        )}
        <div className="text-[9px] text-gray-300 mt-1">2000年后数据密度稳定（≥400实体/年），早期年份已过滤</div>
      </div>
    </div>
  )
}
