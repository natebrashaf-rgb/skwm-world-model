import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Legend, CartesianGrid, Tooltip } from 'recharts'
import API from '../data/api'

export default function TrendPage() {
  const [keywords] = useState(['旅游', '文化', '遗产', '数字'])
  const [selected, setSelected] = useState('旅游')
  const [data, setData] = useState<{year:number;heat:number}[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true); setError('')
    API.trend(selected).then(r => {
      setData(r.trend || [])
    }).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [selected])

  return (
    <div>
      <Breadcrumb items={['TREND']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">趋势预测</h1>
      <p className="text-xs text-gray-400 mb-6">来源: state_vectors[year][keyword][0]=heat</p>

      <div className="flex gap-2 mb-4">
        {keywords.map(k => (
          <button key={k} onClick={() => setSelected(k)}
            className={`px-3 py-1.5 text-xs rounded-lg border ${selected===k?'bg-primary-50 border-primary-200 text-primary font-medium':'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>
            {k}
          </button>
        ))}
      </div>

      {loading && <div className="text-xs text-gray-400 py-8">加载中...</div>}
      {error && <div className="text-xs text-red-500 py-8">⚠️ {error}</div>}

      {!loading && !error && data.length === 0 && <div className="text-xs text-gray-400 py-8">N/A (该关键词无历史数据)</div>}

      {!loading && data.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="year" tick={{fontSize:11,fill:'#9ca3af'}} />
              <YAxis tick={{fontSize:11,fill:'#9ca3af'}} />
              <Tooltip />
              <Line type="monotone" dataKey="heat" stroke="#2563eb" strokeWidth={2} dot={false} name={selected} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
