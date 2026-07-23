import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import API, { FrontierItem } from '../data/api'

export default function FrontierPage() {
  const [data, setData] = useState<FrontierItem[]>([])
  const [year, setYear] = useState('2026')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    API.frontier(year, 10).then(r => {
      setData(r.frontier || [])
      setError('')
    }).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [year])

  return (
    <div>
      <Breadcrumb items={['FRONTIER']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">前沿识别</h1>
      <p className="text-xs text-gray-400 mb-4">
        来源: state_vectors[][1]=growth · |growth|≤heat峰值 · 已过滤停用词
        <select value={year} onChange={e => setYear(e.target.value)}
          className="ml-2 px-2 py-0.5 text-xs border border-gray-200 rounded bg-white">
          {[2026, 2025, 2024, 2023, 2022].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </p>

      {loading && <div className="text-xs text-gray-400 py-8">加载中...</div>}
      {error && <div className="text-xs text-red-500 py-8">⚠️ {error}</div>}
      {!loading && !error && data.length === 0 && <div className="text-xs text-gray-400 py-8">N/A</div>}

      {!loading && data.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">前沿主题 TOP {data.length} ({year})</h3>
          <div className="space-y-2">
            {data.map(f => (
              <div key={f.name} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-5">{f.rank}</span>
                  <span className="text-sm font-medium text-gray-800">{f.label_zh || f.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">热度 {f.heat}</span>
                  <span className="text-xs font-semibold text-green-600">+{f.growth.toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
