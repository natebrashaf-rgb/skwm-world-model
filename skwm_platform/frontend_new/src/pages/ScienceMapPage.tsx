import { Breadcrumb } from '../components/Breadcrumb'
import { ScatterChart, Scatter, XAxis, YAxis, ResponsiveContainer, Legend } from 'recharts'

const clusters = [
  { name: '文旅融合', data: Array.from({length:12},()=>({x:Math.random()*30,y:Math.random()*30})) },
  { name: '阿拉伯语NLP', data: Array.from({length:10},()=>({x:50+Math.random()*30,y:20+Math.random()*30})) },
  { name: '知识图谱', data: Array.from({length:8},()=>({x:30+Math.random()*20,y:50+Math.random()*30})) },
  { name: '科学计量', data: Array.from({length:6},()=>({x:60+Math.random()*30,y:60+Math.random()*30})) },
]

export default function ScienceMapPage() {
  return (
    <div>
      <Breadcrumb items={['SCIENCE MAP']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">科学地图</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart>
              <XAxis type="number" dataKey="x" tick={false} /><YAxis type="number" dataKey="y" tick={false} />
              {clusters.map((c,i) => <Scatter key={c.name} name={c.name} data={c.data} fill={['#2563eb','#16a34a','#d97706','#8b5cf6'][i]} opacity={0.5} />)}
              <Legend wrapperStyle={{fontSize:11}} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2">
          {clusters.map(c => <div key={c.name} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm text-xs"><span className="font-medium text-gray-700">{c.name}</span><div className="text-gray-400 mt-1">主题数：{c.data.length}</div></div>)}
        </div>
      </div>
    </div>
  )
}
