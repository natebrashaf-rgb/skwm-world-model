import { Card } from "@/components/ui/Card";

export function MetricCard({
  label,
  value,
  helper,
  icon,
}: {
  label: string;
  value: string | number;
  helper: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-slate-500">{label}</div>
          <div className="mt-2 text-3xl font-semibold text-ink">{value}</div>
        </div>
        {icon && <div className="text-navy/30">{icon}</div>}
      </div>
      <div className="mt-2 text-xs text-slate-500">{helper}</div>
    </Card>
  );
}
