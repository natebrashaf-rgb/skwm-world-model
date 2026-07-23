import { useState, useRef, useEffect } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { Send, Plus } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; sources?: { type: string; id: string; year: number; confidence: number }[] }
interface Session { id: string; title: string; messages: Message[] }

export default function QaPage() {
  const [sessions, setSessions] = useState<Session[]>([{ id: 's1', title: '中阿文旅热点', messages: [] }])
  const [activeId, setActiveId] = useState('s1')
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const active = sessions.find(s => s.id === activeId)!

  const onSend = (text: string) => {
    if (!text.trim()) return
    const newMsgs: Message[] = [...active.messages, { role: 'user', content: text },
      { role: 'assistant', content: `关于「${text}」的查询结果：知识图谱检索到 5 篇相关文献。基于 GraphRAG 的多跳推理生成以下回答…（待接入后端）`,
        sources: [{ type: '文献', id: 'SKWM-2024-001', year: 2024, confidence: 0.92 }, { type: '图谱子图', id: '文旅融合', year: 2024, confidence: 0.87 }] }]
    setSessions(prev => prev.map(s => s.id === activeId ? { ...s, messages: newMsgs, title: s.messages.length === 0 ? text.slice(0, 20) : s.title } : s))
    setInput('')
  }

  useEffect(() => { endRef.current?.scrollIntoView() }, [active.messages])

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Session list */}
      <div className="w-44 shrink-0 space-y-1">
        <button onClick={() => { const id = 's' + Date.now(); setSessions(p => [...p, { id, title: '新会话', messages: [] }]); setActiveId(id) }}
          className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 mb-2"><Plus size={14} />新会话</button>
        {sessions.map(s => (
          <button key={s.id} onClick={() => setActiveId(s.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs ${s.id === activeId ? 'bg-primary-50 text-primary font-medium' : 'text-gray-600 hover:bg-gray-50'}`}>{s.title}</button>
        ))}
      </div>
      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          {active.messages.length === 0 && <div className="text-center text-gray-400 text-sm py-12">输入问题开始智能问答</div>}
          {active.messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[70%] rounded-lg px-3 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'bg-primary text-white' : 'bg-gray-50 text-gray-700 border border-gray-100'}`}>
                {m.content}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {m.sources.map((s, j) => (
                      <div key={j} className="bg-white border border-gray-100 rounded px-2 py-1 flex gap-2 text-[10px] text-gray-400">
                        <span className="font-medium text-gray-500">{s.type}</span>
                        <span>{s.id}</span>
                        <span>{s.year}</span>
                        <span>{Math.round(s.confidence * 100)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && onSend(input)}
            placeholder="输入问题..." className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary-200" />
          <button onClick={() => onSend(input)} className="p-2 text-primary hover:bg-primary-50 rounded-lg"><Send size={16} /></button>
        </div>
      </div>
    </div>
  )
}
