import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { BarChart, Bar, XAxis, ResponsiveContainer } from 'recharts'
import { Database, Share2, Layers, BookOpen } from 'lucide-react'
import API, { OverviewData, HotspotItem, FrontierItem, TimelineYear } from '../data/api'

const ICONS = [Database, Share2, Layers, BookOpen]

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

  if (error) return <div className="text-red-500 text-sm">⚠️ {error}</div>
  if (!ov && !hot.length) return <div className="text-gray-400 text-sm py-12">加载中...</div>

  const stats = [
    { label: '状态向量', value: ov?.state_vectors?.toLocaleString() || 'N/A', source: ov?.sources?.state_vectors || '计算中' },
    { label: '知识关系', value: ov?.knowledge_relations?.toLocaleString() || 'N/A', source: ov?.sources?.knowledge_relations || '计算中' },
    { label: '年切片', value: String(ov?.snapshots ?? 'N/A'), source: ov?.sources?.snapshots || '计算中' },
    { label: '2026年实体', value: ov?.latest_year_entities?.toLocaleString() || 'N/A', note: '最新年份' },
  ]

  return (
    <div>
      <Breadcrumb items={['OVERVIEW']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">中阿文旅世界模型</h1>
      <p className="text-xs text-gray-400 mb-6">
        数据来源: state_vectors.json · 口径: {ov?.year_range || 'N/A'} · 
        <span className="ml-1">{ov?.note || ''}</span>
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((s, i) => {
          const Icon = ICONS[i]
          return (
            <div key={s.label} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <Icon size={18} strokeWidth={1.5} className="text-gray-400 mb-2" />
              <div className="text-2xl font-semibold text-gray-900">{s.value}</div>
              <div className="text-xs text-gray-400">{s.label}</div>
              {s.source && <div className="text-[9px] text-gray-300 mt-0.5">来源: {s.source}</div>}
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">热点 TOP 10</h3>
          {hot.length === 0 ? <div className="text-xs text-gray-400">N/A</div> : (
            <div className="space-y-1.5">
              {hot.map(h => (
                <div key={h.name} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-4 text-right shrink-0">{h.rank}</span>
                  <span className="text-xs text-gray-700 w-28 truncate shrink-0" title={h.label_zh || h.name}>{h.label_zh || h.name}</span>
                  <div className="h-3.5 rounded bg-primary-100 flex-shrink-0" style={{ width: `${(h.heat / hot[0].heat) * 100}%`, maxWidth: 200 }} />
                  <span className="text-xs text-gray-500 font-medium">{h.heat}</span>
                </div>
              ))}
            </div>
          )}
          <div className="text-[9px] text-gray-300 mt-2">来源: state_vectors[][0]=heat · 已过滤停用词</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">前沿 TOP 5</h3>
          {front.length === 0 ? <div className="text-xs text-gray-400">N/A</div> : (
            <div className="space-y-2">
              {front.map(f => (
                <div key={f.name} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-4">{f.rank}</span>
                    <span className="text-sm text-gray-700">{f.label_zh || f.name}</span>
                  </div>
                  <span className="text-xs font-medium text-green-600">+{f.growth.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
          <div className="text-[9px] text-gray-300 mt-2">来源: state_vectors[][1]=growth · |growth|≤heat峰值</div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">时间线 (2000-2026, 数据密度≥400节点/年)</h3>
        {tl.length === 0 ? <div className="text-xs text-gray-400">N/A</div> : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={tl}>
              <XAxis dataKey="year" tick={{fontSize:10,fill:'#9ca3af'}} tickFormatter={y=>String(y)} interval={3} />
              <Bar dataKey="entities_clean" fill="#dbeafe" radius={[2,2,0,0]} name="实体数(去停用词)" />
            </BarChart>
          </ResponsiveContainer>
        )}
        <div className="text-[9px] text-gray-300 mt-1">来源: len(state_vectors[year]) · 早期稀疏年份默认隐藏</div>
      </div>
    </div>
  )
}
