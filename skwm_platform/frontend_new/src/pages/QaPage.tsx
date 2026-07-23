import { useState, useRef, useEffect } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { Send, Plus, CheckCircle, XCircle, Clock, ExternalLink, FileText, ShieldAlert, ShieldCheck } from 'lucide-react'

interface EvidenceSource {
  type: string; id: string; title: string; year: number; confidence: number; snippet: string
}
interface QAItem {
  qa_id: string; question: string; answer: string
  sources: EvidenceSource[]; overall_confidence: number
  has_sufficient_evidence: boolean; review_status: string
  reviewed_by?: string; review_comment?: string; edited_answer?: string; rejected_reason?: string
}

const STATUS_META: Record<string, {icon: any; label: string; color: string}> = {
  pending: { icon: Clock, label: '待审', color: 'text-amber-500' },
  approved: { icon: CheckCircle, label: '已通过', color: 'text-green-600' },
  rejected: { icon: XCircle, label: '已退回', color: 'text-red-500' },
  edited: { icon: ShieldCheck, label: '馆员编辑', color: 'text-blue-600' },
}

export default function QaPage() {
  const [sessions, setSessions] = useState<{id: string; title: string; items: QAItem[]}[]>([
    { id: 's1', title: '新会话', items: [] }
  ])
  const [activeId, setActiveId] = useState('s1')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'chat' | 'review'>('chat')
  const [pendingList, setPendingList] = useState<QAItem[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const active = sessions.find(s => s.id === activeId)!

  const askGraphRAG = async (text: string) => {
    setLoading(true)
    try {
      const r = await fetch('/api/graphrag/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question: text })
      })
      const d = await r.json()
      const item: QAItem = {
        qa_id: d.qa_id || Date.now().toString(),
        question: text,
        answer: d.answer || '处理失败',
        sources: d.sources || [],
        overall_confidence: d.overall_confidence || 0,
        has_sufficient_evidence: d.has_sufficient_evidence ?? false,
        review_status: d.review_status || 'pending',
      }
      setSessions(prev => prev.map(s => s.id === activeId ? {
        ...s,
        title: s.items.length === 0 ? text.slice(0, 20) : s.title,
        items: [...s.items, item]
      } : s))
    } catch (e: any) {
      setSessions(prev => prev.map(s => s.id === activeId ? {
        ...s, items: [...s.items, {
          qa_id: 'err', question: text, answer: `请求失败: ${e.message}`,
          sources: [], overall_confidence: 0, has_sufficient_evidence: false, review_status: 'pending'
        }]
      } : s))
    }
    setLoading(false)
  }

  const loadPending = async () => {
    const r = await fetch('/api/graphrag/pending')
    const d = await r.json()
    setPendingList(d.qa_list || [])
  }

  const approveQA = async (qaId: string) => {
    await fetch('/api/graphrag/approve', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ qa_id: qaId, reviewer: '馆员', comment: '审核通过' })
    })
    loadPending()
  }

  const rejectQA = async (qaId: string) => {
    const reason = prompt('退回原因:') || '证据不足'
    await fetch('/api/graphrag/reject', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ qa_id: qaId, reviewer: '馆员', reason })
    })
    loadPending()
  }

  useEffect(() => { endRef.current?.scrollIntoView() }, [active.items])
  useEffect(() => { if (view === 'review') loadPending() }, [view])

  const onSend = (text: string) => {
    if (!text.trim() || loading) return
    askGraphRAG(text)
    setInput('')
  }

  const renderSources = (sources: EvidenceSource[]) => {
    if (!sources || sources.length === 0) return null
    const openDetail = (s: EvidenceSource) => {
      if (s.type === 'paper' && s.id) window.open(`/api/graphrag/qa/${s.id}`, '_blank')
    }
    return (
      <div className="mt-2 pt-2 border-t border-gray-100 space-y-1">
        <div className="text-[10px] font-medium text-gray-400">证据来源 ({sources.length})</div>
        {sources.slice(0, 4).map((s, j) => (
          <div key={j} className="flex items-center gap-1.5 text-[10px] text-gray-500 bg-gray-50 rounded px-2 py-1">
            <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
              s.type === 'paper' ? 'bg-blue-50 text-blue-600' :
              s.type === 'entity' ? 'bg-green-50 text-green-600' :
              'bg-gray-100 text-gray-600'
            }`}>{s.type}</span>
            <span className="flex-1 truncate">{s.title || s.id}</span>
            {s.year > 0 && <span className="text-gray-400">{s.year}</span>}
            <span className={`font-medium ${s.confidence > 0.7 ? 'text-green-600' : 'text-amber-500'}`}>
              {(s.confidence * 100).toFixed(0)}%
            </span>
            <button onClick={() => openDetail(s)} className="text-gray-400 hover:text-primary"><ExternalLink size={10} /></button>
          </div>
        ))}
      </div>
    )
  }

  const renderReviewStatus = (item: QAItem) => {
    const meta = STATUS_META[item.review_status]
    if (!meta) return null
    const Icon = meta.icon
    return (
      <div className={`flex items-center gap-1 text-[10px] ${meta.color} mt-1`}>
        <Icon size={12} />
        <span>{meta.label}</span>
        {item.overall_confidence > 0 && <span className="text-gray-400">| 置信度 {(item.overall_confidence * 100).toFixed(0)}%</span>}
        {item.reviewed_by && <span className="text-gray-400">| {item.reviewed_by}</span>}
      </div>
    )
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Sidebar */}
      <div className="w-40 shrink-0 space-y-1">
        <div className="flex gap-1 mb-2">
          <button onClick={() => setView('chat')}
            className={`flex-1 px-2 py-1.5 text-xs rounded-lg ${view==='chat'?'bg-primary-50 text-primary font-medium':'text-gray-500 hover:bg-gray-50'}`}>问答</button>
          <button onClick={() => setView('review')}
            className={`flex-1 px-2 py-1.5 text-xs rounded-lg ${view==='review'?'bg-primary-50 text-primary font-medium':'text-gray-500 hover:bg-gray-50'}`}>审核</button>
        </div>
        {view === 'chat' && sessions.map(s => (
          <button key={s.id} onClick={() => setActiveId(s.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs ${s.id===activeId?'bg-primary-50 text-primary font-medium':'text-gray-600 hover:bg-gray-50'}`}>{s.title}</button>
        ))}
        {view === 'chat' && <button onClick={() => setSessions(p => [...p, {id:'s'+Date.now(),title:'新会话',items:[]}])}
          className="w-full flex items-center gap-1 px-3 py-2 text-xs text-gray-500 hover:bg-gray-50 rounded-lg"><Plus size={12} />新会话</button>}
      </div>

      {/* Chat view */}
      {view === 'chat' && (
        <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
            {active.items.length === 0 && (
              <div className="text-center text-gray-400 text-sm py-12">
                输入问题开始带有溯源的 GraphRAG 智能问答<br/>
                <span className="text-xs">答案会自动标注置信度与证据来源</span>
              </div>
            )}
            {active.items.map((item, i) => (
              <div key={i} className="space-y-1">
                {/* User question */}
                <div className="flex justify-end">
                  <div className="max-w-[75%] bg-primary text-white rounded-lg px-3 py-2 text-sm leading-relaxed">{item.question}</div>
                </div>
                {/* AI Answer */}
                <div className="flex justify-start">
                  <div className="max-w-[80%] bg-gray-50 text-gray-700 border border-gray-100 rounded-lg px-3 py-2 text-sm leading-relaxed">
                    {!item.has_sufficient_evidence && item.overall_confidence < 0.3 && (
                      <div className="flex items-center gap-1 text-amber-600 text-xs mb-2 bg-amber-50 px-2 py-1 rounded">
                        <ShieldAlert size={14} /> 证据不足
                      </div>
                    )}
                    <div className="whitespace-pre-wrap">{item.answer}</div>
                    {item.sources.length > 0 && renderSources(item.sources)}
                    {renderReviewStatus(item)}
                    {item.review_comment && (
                      <div className="mt-1 text-[10px] text-gray-400 italic">馆员注: {item.review_comment}</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && <div className="text-center text-xs text-gray-400">检索中...</div>}
            <div ref={endRef} />
          </div>
          <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && onSend(input)}
              placeholder="输入问题..." className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary-200" />
            <button onClick={() => onSend(input)} disabled={loading} className="p-2 text-primary hover:bg-primary-50 rounded-lg"><Send size={16} /></button>
          </div>
        </div>
      )}

      {/* Review view */}
      {view === 'review' && (
        <div className="flex-1 bg-white border border-gray-200 rounded-lg shadow-sm p-4 overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700">馆员审核 · 待审问答</h3>
            <button onClick={loadPending} className="text-xs text-primary hover:underline">刷新</button>
          </div>
          {pendingList.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-12">暂无待审问答</div>
          ) : (
            <div className="space-y-4">
              {pendingList.map((item, i) => (
                <div key={i} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-800">{item.question}</div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {item.sources?.length || 0} 条证据 · 置信度 {(item.overall_confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="flex gap-1 ml-2">
                      <button onClick={() => approveQA(item.qa_id)}
                        className="px-2 py-1 text-[10px] bg-green-50 text-green-600 border border-green-200 rounded hover:bg-green-100">通过</button>
                      <button onClick={() => rejectQA(item.qa_id)}
                        className="px-2 py-1 text-[10px] bg-red-50 text-red-500 border border-red-200 rounded hover:bg-red-100">退回</button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5 max-h-20 overflow-y-auto">
                    {item.answer?.slice(0, 200)}...
                  </div>
                  {item.sources && item.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.sources.slice(0, 3).map((s, j) => (
                        <span key={j} className="text-[9px] px-1.5 py-0.5 bg-gray-50 border border-gray-100 rounded text-gray-500">
                          {s.type}: {(s.title || s.id).slice(0, 20)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
