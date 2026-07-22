import type { Metadata } from "next";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppHeader } from "@/components/layout/AppHeader";
import { AppSidebar } from "@/components/layout/AppSidebar";

export const metadata: Metadata = {
  title: "SKWM 智能学科服务平台",
  description:
    "科学知识世界模型驱动的高校图书馆智能学科服务模式研究——以中阿文旅知识服务平台为例",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="stylesheet" href="/globals.css" />
      </head>
      <body>
        <ErrorBoundary>
          <div className="min-h-screen bg-[#f6f8fb]">
            <AppHeader />
            <div className="mx-auto flex max-w-7xl gap-6 px-6 py-6">
              <AppSidebar />
              <main className="min-w-0 flex-1">{children}</main>
            </div>
          </div>
        </ErrorBoundary>
      </body>
    </html>
  );
}
