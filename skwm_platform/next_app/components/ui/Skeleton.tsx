export function MetricSkeleton() {
  return <div className="h-28 animate-pulse rounded-lg bg-slate-200" />;
}

export function CardSkeleton() {
  return <div className="h-48 animate-pulse rounded-lg bg-slate-200" />;
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 rounded bg-slate-200" />
      ))}
    </div>
  );
}
