import { Breadcrumb } from '../components/Breadcrumb'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Legend } from 'recharts'

const data = Array.from({length:20},(_,i)=>({year:2007+i, tourism:20+Math.random()*80+i*5, heritage:15+Math.random()*60+i*3, model:5+Math.random()*40+i*2, tourism_pred:20+Math.random()*80+i*5+20+Math.random()*30, heritage_pred:15+Math.random()*60+i*3+10+Math.random()*20}))

export default function TrendPage() {
  return (
    <div>
      <Breadcrumb items={['TREND']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">趋势预测</h1>
      <p className="text-sm text-gray-400 mb-6">XGBoost 模型 · AUC=0.94</p>
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={data}>
            <XAxis dataKey="year" tick={{fontSize:11,fill:'#9ca3af'}} />
            <YAxis tick={{fontSize:11,fill:'#9ca3af'}} />
            <Line type="monotone" dataKey="tourism" stroke="#2563eb" strokeWidth={2} dot={false} name="tourism (实际)" />
            <Line type="monotone" dataKey="heritage" stroke="#16a34a" strokeWidth={2} dot={false} name="heritage (实际)" />
            <Line type="monotone" dataKey="model" stroke="#d97706" strokeWidth={2} dot={false} name="model (实际)" />
            <Line type="monotone" dataKey="tourism_pred" stroke="#2563eb" strokeWidth={2} strokeDasharray="4 4" dot={false} name="tourism (预测)" />
            <Line type="monotone" dataKey="heritage_pred" stroke="#16a34a" strokeWidth={2} strokeDasharray="4 4" dot={false} name="heritage (预测)" />
            <Legend wrapperStyle={{fontSize:11}} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
