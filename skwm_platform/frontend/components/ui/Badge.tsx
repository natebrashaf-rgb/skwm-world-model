export type BadgeTone = "green" | "amber" | "red" | "blue" | "slate" | "purple" | "emerald";

const tones: Record<BadgeTone, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  slate: "bg-slate-50 text-slate-700 ring-slate-200",
  purple: "bg-purple-50 text-purple-700 ring-purple-200",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export function Badge({
  className = "",
  tone = "slate",
  children,
  ...props
}: { tone?: BadgeTone; className?: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-1 text-xs font-semibold ring-1 ${tones[tone]} ${className}`} {...props}>
      {children}
    </span>
  );
}
