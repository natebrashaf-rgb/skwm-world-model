import { Breadcrumb } from '../components/Breadcrumb'
import { topFrontiers } from '../data/overview'

export default function FrontierPage() {
  return (
    <div>
      <Breadcrumb items={['FRONTIER']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">前沿识别</h1>
      <p className="text-sm text-gray-400 mb-6">基于科学计量的前沿与突现主题检测</p>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">前沿主题 TOP 5</h3>
        <div className="space-y-3">
          {topFrontiers.map(f => (
            <div key={f.rank} className="flex items-center justify-between py-2 border-b border-gray-50">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-5">{f.rank}</span>
                <span className="text-sm font-medium text-gray-800">{f.name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs font-semibold text-green-600">+{f.growth.toLocaleString()}</span>
                <svg width="60" height="20" className="text-green-300"><polyline fill="none" stroke="currentColor" strokeWidth="1.5" points="0,15 10,12 20,16 30,8 40,10 50,4 60,2" /></svg>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">突现主题检测</h3>
        <table className="w-full text-xs">
          <thead><tr className="text-gray-400 border-b border-gray-100"><th className="text-left py-2 font-medium">主题</th><th className="text-left py-2 font-medium">突现年份</th><th className="text-left py-2 font-medium">强度</th><th className="text-left py-2 font-medium">状态</th></tr></thead>
          <tbody>
            {[['generative ai','2024','8.42','上升'],['GraphRAG','2024','6.71','上升'],['大语言模型','2023','5.83','成熟'],['数字文旅','2021','4.25','成熟'],['文化遗产数字化','2022','3.96','稳定']].map((r,i) => (
              <tr key={i} className="border-b border-gray-50"><td className="py-2 text-gray-700">{r[0]}</td><td className="py-2 text-gray-500">{r[1]}</td><td className="py-2 text-gray-500">{r[2]}</td><td className="py-2"><span className={`px-1.5 py-0.5 rounded text-[10px] ${r[3]==='上升'?'bg-green-50 text-green-600':r[3]==='成熟'?'bg-blue-50 text-blue-600':'bg-gray-50 text-gray-500'}`}>{r[3]}</span></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
