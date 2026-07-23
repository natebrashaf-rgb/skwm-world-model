import { useState } from 'react'
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
