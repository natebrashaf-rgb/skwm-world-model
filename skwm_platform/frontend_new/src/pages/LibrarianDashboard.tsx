import { useEffect, useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { FileText, Database, Globe, Clock, TrendingUp, Activity, Quote, CheckCircle, XCircle, AlertCircle, User, BookOpen, MessageSquare } from 'lucide-react'

const ICON_MAP: Record<string, any> = { 'file-text': FileText, 'database': Database, 'globe': Globe, 'clock': Clock, 'trending-up': TrendingUp, 'activity': Activity, 'quote': Quote }

type KpiData = { value: string; unit: string; icon: string; trend: string }
type RoleItem = { type: string; title: string; score: number; action: string }

export default function LibrarianDashboard() {
  const [kpi, setKpi] = useState<Record<string, KpiData>>({})
  const [review, setReview] = useState({ pending: 0, approved_today: 0, rejected_today: 0 })
  const [recs, setRecs] = useState<Record<string, { items: RoleItem[] }>>({})
  const [policies, setPolicies] = useState<any[]>([])
  const [activeRole, setActiveRole] = useState('teacher')
  const [timeView, setTimeView] = useState<'overview' | 'review' | 'policy'>('overview')

  useEffect(() => {
    fetch('/api/policy/kpi').then(r => r.json()).then(d => { setKpi(d.kpi || {}); setReview(d.review_queue || {}) })
    fetch('/api/policy/recommendations').then(r => r.json()).then(d => setRecs(d.recommendations || {}))
    fetch('/api/policy/entities').then(r => r.json()).then(d => setPolicies(d.timeline || []))
  }, [])

  const renderKpiCard = (key: string, data: KpiData) => {
    const Icon = ICON_MAP[data.icon] || Database
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
        <Icon size={16} className="text-gray-400 mb-1" />
        <div className="text-xl font-semibold text-gray-900">{data.value}<span className="text-xs text-gray-400 ml-1">{data.unit}</span></div>
        <div className="text-[11px] text-gray-400">{key}</div>
      </div>
    )
  }

  return (
    <div>
      <Breadcrumb items={['LIBRARIAN DASHBOARD']} />
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">馆员工作台</h1>
        <div className="flex gap-1">
          {(['overview', 'review', 'policy'] as const).map(v => (
            <button key={v} onClick={() => setTimeView(v)}
              className={`px-3 py-1.5 text-xs rounded-lg ${timeView===v?'bg-primary-50 text-primary font-medium border border-primary-200':'text-gray-500 border border-gray-200 hover:bg-gray-50'}`}>
              {v === 'overview' ? '驾驶舱' : v === 'review' ? '待审核' : '政策时间线'}
            </button>
          ))}
        </div>
      </div>

      {timeView === 'overview' && (
        <>
          {/* KPI */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            {Object.entries(kpi).slice(0, 8).map(([k, v]) => (
              <div key={k}>
                {renderKpiCard(k, v)}
              </div>
            ))}
          </div>

          {/* Review Queue */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm flex items-center gap-2"><AlertCircle size={16} className="text-amber-500" /><div><div className="text-lg font-semibold">{review.pending}</div><div className="text-[10px] text-gray-400">待审核</div></div></div>
            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm flex items-center gap-2"><CheckCircle size={16} className="text-green-500" /><div><div className="text-lg font-semibold">{review.approved_today}</div><div className="text-[10px] text-gray-400">今日通过</div></div></div>
            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm flex items-center gap-2"><XCircle size={16} className="text-red-400" /><div><div className="text-lg font-semibold">{review.rejected_today}</div><div className="text-[10px] text-gray-400">今日退回</div></div></div>
          </div>

          {/* Role-based Recommendations */}
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
            <div className="flex border-b border-gray-100">
              {['teacher','student','librarian'].map(r => (
                <button key={r} onClick={() => setActiveRole(r)}
                  className={`flex-1 px-3 py-2 text-xs font-medium ${activeRole===r?'text-primary border-b-2 border-primary':'text-gray-500 hover:text-gray-700'}`}>
                  {r === 'teacher' ? '👩‍🏫 教师' : r === 'student' ? '👨‍🎓 学生' : '👩‍💼 馆员'}
                </button>
              ))}
            </div>
            <div className="p-3 space-y-1">
              {(recs[activeRole]?.items || []).slice(0, 5).map((item, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      item.type==='frontier'?'bg-purple-50 text-purple-600':
                      item.type==='concept'?'bg-green-50 text-green-600':
                      'bg-blue-50 text-blue-600'
                    }`}>{item.type}</span>
                    <span className="text-xs text-gray-700">{item.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-400">{(item.score)}</span>
                    <span className="text-[10px] text-primary cursor-pointer">{item.action}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {timeView === 'review' && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">待审核问答队列</h3>
          {[1,2,3].map(i => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-50">
              <div className="flex items-center gap-2">
                <MessageSquare size={14} className="text-gray-400" />
                <span className="text-xs text-gray-600">中阿文旅热点分析 #{i}</span>
              </div>
              <div className="flex gap-1">
                <button className="px-2 py-0.5 text-[10px] bg-green-50 text-green-600 border border-green-200 rounded">通过</button>
                <button className="px-2 py-0.5 text-[10px] bg-red-50 text-red-500 border border-red-200 rounded">退回</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {timeView === 'policy' && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">政策→热点时间关联</h3>
          <div className="space-y-2">
            {policies.slice(0, 10).map((p, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-b border-gray-50">
                <span className="text-[10px] text-gray-400 w-16">{p.first_year}-{p.last_year}</span>
                <span className="text-xs text-gray-700 flex-1 truncate">{p.policy}</span>
                <span className="text-[10px] text-gray-400">{p.occurrences}次</span>
                <div className="flex gap-1">
                  {(p.related_hotspots || []).slice(0,2).map((h: any, j: number) => (
                    <span key={j} className="text-[9px] bg-blue-50 text-blue-600 px-1 py-0.5 rounded">{h.keyword}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
