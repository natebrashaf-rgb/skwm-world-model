import { Breadcrumb } from '../components/Breadcrumb'
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
