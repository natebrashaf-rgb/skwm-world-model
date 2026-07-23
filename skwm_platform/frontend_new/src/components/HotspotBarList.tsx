interface HotspotItem { rank: number; name: string; value: number }
export function HotspotBarList({ data, max }: { data: HotspotItem[]; max?: number }) {
  const mx = max || Math.max(...data.map(d => d.value), 1)
  return (
    <div className="space-y-1.5">
      {data.map(d => (
        <div key={d.rank} className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-4 text-right shrink-0">{d.rank}</span>
          <span className="text-xs text-gray-700 w-28 truncate shrink-0">{d.name}</span>
          <div className="h-3.5 rounded bg-primary-100 flex-shrink-0" style={{ width: `${(d.value / mx) * 100}%`, maxWidth: 200 }} />
          <span className="text-xs text-gray-500 font-medium">{d.value}</span>
        </div>
      ))}
    </div>
  )
}
