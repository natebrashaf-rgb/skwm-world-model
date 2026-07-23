import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import API, { HotspotItem } from '../data/api'

export default function HotspotPage() {
  const [data, setData] = useState<HotspotItem[]>([])
  const [year, setYear] = useState('2026')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    API.hotspot(year, 20).then(r => {
      setData(r.hotspots || [])
      setError('')
    }).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [year])

  return (
    <div>
      <Breadcrumb items={['HOTSPOTS']} />
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">热点分析</h1>
          <p className="text-xs text-gray-400 mt-0.5">来源: state_vectors[][0]=heat · 已过滤停用词</p>
        </div>
        <select value={year} onChange={e => setYear(e.target.value)}
          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-white">
          {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {loading && <div className="text-xs text-gray-400 py-8 text-center">加载中...</div>}
      {error && <div className="text-xs text-red-500 py-8 text-center">⚠️ {error}</div>}

      {!loading && !error && data.length === 0 && <div className="text-xs text-gray-400 py-8 text-center">N/A</div>}

      {!loading && data.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">关键词热度 TOP 20 ({year})</h3>
          <div className="space-y-1.5">
            {data.map(h => (
              <div key={h.name} className="flex items-center gap-2">
                <span className="text-xs text-gray-400 w-5 text-right shrink-0">{h.rank}</span>
                <span className="text-xs text-gray-700 w-32 truncate shrink-0" title={h.label_zh || h.name}>
                  {h.label_zh || h.name}
                </span>
                <div className="h-3.5 rounded bg-primary-100 shrink-0" style={{
                  width: `${(h.heat / data[0].heat) * 100}%`,
                  maxWidth: 200
                }} />
                <span className="text-xs text-gray-500 font-medium">{h.heat}</span>
                {h.growth !== 0 && (
                  <span className={`text-[10px] ${h.growth > 0 ? 'text-green-500' : 'text-red-400'}`}>
                    {h.growth > 0 ? '+' : ''}{h.growth}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
