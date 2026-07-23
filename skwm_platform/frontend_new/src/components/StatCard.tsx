import { LucideIcon } from 'lucide-react'

export function StatCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <Icon size={18} strokeWidth={1.5} className="text-gray-400 mb-2" />
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}
