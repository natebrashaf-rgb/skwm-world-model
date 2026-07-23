import { Breadcrumb } from '../components/Breadcrumb'
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
