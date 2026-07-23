export function Breadcrumb({ items }: { items: string[] }) {
  return (
    <div className="text-[11px] font-semibold tracking-wider text-primary uppercase mb-2">
      {items.join(' / ')}
    </div>
  )
}
