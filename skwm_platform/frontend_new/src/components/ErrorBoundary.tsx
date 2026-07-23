import { Component, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { hasError: boolean; error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-[#F7F8FA] p-8">
          <div className="max-w-lg bg-white border border-red-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-bold text-red-600 mb-2">⚠️ 应用异常</h2>
            <p className="text-sm text-gray-600 mb-3">SKWM 遇到了一个意外错误：</p>
            <pre className="text-xs bg-red-50 border border-red-100 rounded-lg p-3 text-red-700 overflow-auto max-h-32 mb-4">
              {this.state.error?.message || '未知错误'}
            </pre>
            <div className="text-xs text-gray-400 mb-4">
              <p>常见原因：网络连接超时、资源加载失败。</p>
              <p>请尝试：</p>
              <ol className="list-decimal ml-4 mt-1 space-y-0.5">
                <li>按 F5 刷新页面</li>
                <li>Ctrl+F5 强制刷新（跳过缓存）</li>
                <li>更换浏览器或使用无痕模式</li>
                <li>如果持续出现，请联系馆员</li>
              </ol>
            </div>
            <button onClick={() => window.location.reload()}
              className="px-4 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary-700">
              刷新页面
            </button>
            <pre className="mt-4 text-[9px] text-gray-300 overflow-auto max-h-24">
              {this.state.error?.stack?.split('\n').slice(0, 5).join('\n')}
            </pre>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
