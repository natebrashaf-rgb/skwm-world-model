import { useState, useRef, useCallback, useEffect } from 'react'
import { MessageSquare, X, Send } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; sources?: { type: string; id: string; year: number; confidence: number }[] }

export function DraggableChatBot() {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Message[]>([
    { role: 'assistant', content: '您好，我是 SKWM 智能助手。可以问我关于中阿文旅研究的问题。' }
  ])
  const [input, setInput] = useState('')
  const [dragging, setDragging] = useState(false)
  const [pos, setPos] = useState({ x: window.innerWidth - 80, y: window.innerHeight - 80 })
  const dragRef = useRef({ startX: 0, startY: 0, elX: 0, elY: 0, moved: false })
  const chatRef = useRef<HTMLDivElement>(null)

  const onSend = useCallback((text: string) => {
    if (!text.trim()) return
    setMsgs(prev => [...prev, { role: 'user', content: text },
      { role: 'assistant', content: `已收到您的问题：「${text}」。知识图谱检索到 5 篇相关文献，正在生成回答…（此为占位响应，待接入 GraphRAG 后端）`,
        sources: [{ type: '文献', id: 'SKWM-2024-001', year: 2024, confidence: 0.92 }] }])
    setInput('')
  }, [])

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if (open) return
    setDragging(true); dragRef.current = { startX: e.clientX, startY: e.clientY, elX: pos.x, elY: pos.y, moved: false }
  }, [open, pos])

  const onPointerMove = useCallback((e: PointerEvent) => {
    if (!dragging) return
    const dx = e.clientX - dragRef.current.startX, dy = e.clientY - dragRef.current.startY
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) dragRef.current.moved = true
    setPos({ x: dragRef.current.elX + dx, y: dragRef.current.elY + dy })
  }, [dragging])

  const onPointerUp = useCallback(() => {
    setDragging(false)
    if (!dragRef.current.moved && !open) setOpen(true)
  }, [open])

  useEffect(() => {
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    return () => { window.removeEventListener('pointermove', onPointerMove); window.removeEventListener('pointerup', onPointerUp) }
  }, [onPointerMove, onPointerUp])

  useEffect(() => { if (open && chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight }, [msgs, open])

  return (
    <>
      {/* Chat panel */}
      {open && <div className="fixed bottom-4 right-4 z-50 w-80 sm:w-96 bg-white border border-gray-200 rounded-xl shadow-xl flex flex-col overflow-hidden" style={{ maxHeight: '70vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <span className="text-sm font-semibold text-gray-800">SKWM 智能问答</span>
          <button onClick={() => setOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={16} /></button>
        </div>
        <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar" style={{ minHeight: 200 }}>
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'bg-primary text-white' : 'bg-gray-50 text-gray-700 border border-gray-100'}`}>
                {m.content}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {m.sources.map((s, j) => (
                      <div key={j} className="text-[11px] text-gray-400 flex gap-2">
                        <span className="font-medium">{s.type}</span>
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
        </div>
        <div className="flex items-center gap-2 px-3 py-2 border-t border-gray-100">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSend(input)}
            placeholder="输入问题..." className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary-200" />
          <button onClick={() => onSend(input)} className="p-2 text-primary hover:bg-primary-50 rounded-lg"><Send size={16} /></button>
        </div>
      </div>}

      {/* Floating button */}
      <button
        onPointerDown={onPointerDown}
        onClick={() => { if (!dragRef.current.moved) setOpen(v => !v) }}
        className="fixed z-50 w-12 h-12 bg-primary text-white rounded-full shadow-lg flex items-center justify-center hover:bg-primary-700 transition-colors cursor-grab active:cursor-grabbing select-none"
        style={{ left: pos.x, top: pos.y, transform: 'translate(-50%, -50%)' }}
      >
        <MessageSquare size={20} />
      </button>
    </>
  )
}
