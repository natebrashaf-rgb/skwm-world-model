import { Card } from "@/components/ui/Card";

export function RecentReports({
  reports,
}: {
  reports: Array<{ id: string; title: string; createdAt: string; type: string }>;
}) {
  return (
    <Card className="p-5">
      <h2 className="font-semibold text-ink">最近服务记录</h2>
      <div className="mt-4 space-y-3">
        {reports.length === 0 ? (
          <p className="text-sm text-slate-500">暂无服务记录，开始使用智能问答吧</p>
        ) : (
          reports.map((report) => (
            <div
              key={report.id}
              className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-700">{report.title}</span>
                <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-500">
                  {report.type}
                </span>
              </div>
              <span className="text-xs text-slate-500">{report.createdAt}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
