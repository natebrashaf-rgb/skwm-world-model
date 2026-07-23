import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip } from 'recharts'
import API from '../data/api'

export default function TimelinePage() {
  const [year, setYear] = useState(2026)
  const [tl, setTl] = useState<{year:number;entities:number;entities_clean:number;sparse:boolean}[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    API.timeline(1895).then(r => {
      setTl(r.timeline || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const yData = tl.find(d => d.year === year)

  if (loading) return <div className="text-xs text-gray-400 py-12 text-center">加载中...</div>
  if (!tl.length) return <div className="text-xs text-gray-400 py-12 text-center">暂无数据</div>

  return (
    <div>
      <Breadcrumb items={['TIMELINE']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-2">时间回溯</h1>
      <p className="text-xs text-gray-400 mb-4">89年数据切片 · 2000年后密度≥400节点/年 (早年灰显标注"数据稀疏")</p>
      <div className="flex items-center gap-4 mb-4">
        <input type="range" min={tl[0]?.year || 1895} max={tl[tl.length-1]?.year || 2026} value={year} onChange={e => setYear(+e.target.value)}
          className="flex-1 accent-primary" />
        <span className="text-sm font-semibold text-gray-700 w-16">{year}{yData?.sparse ? ' ⚠️' : ''}</span>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div className="text-xs text-gray-400">实体数</div>
          <div className="text-lg font-semibold">{yData?.entities || 0}</div>
          {yData?.sparse && <div className="text-[10px] text-amber-500">数据稀疏</div>}
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div className="text-xs text-gray-400">去停用词</div>
          <div className="text-lg font-semibold">{yData?.entities_clean || 0}</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div className="text-xs text-gray-400">年切片</div>
          <div className="text-lg font-semibold">{year - 1895 + 1}/89</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div className="text-xs text-gray-400">热点(2026)</div>
          <div className="text-lg font-semibold">旅游</div>
          <div className="text-[10px] text-gray-400">热度 6,555</div>
        </div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={tl}>
            <XAxis dataKey="year" tick={{fontSize:9,fill:'#9ca3af'}} tickFormatter={y=>String(y)} interval={19} />
            <Tooltip />
            <Bar dataKey="entities_clean" fill="#dbeafe" radius={[2,2,0,0]} name="实体数(去停用词)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
