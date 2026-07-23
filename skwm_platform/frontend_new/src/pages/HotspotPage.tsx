import { useState } from 'react'
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
