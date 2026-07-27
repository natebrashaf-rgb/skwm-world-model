import type { HTMLAttributes, ButtonHTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-lg border border-slate-200 bg-white shadow-panel ${className}`} {...props} />;
}
