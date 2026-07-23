import { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { DraggableChatBot } from './DraggableChatBot'

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F8FA]">
      <Sidebar />
      <main id="main-content" className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-6xl mx-auto px-6 py-8 pb-24">
          {children}
        </div>
      </main>
      <DraggableChatBot />
    </div>
  )
}
