import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unknown error' }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  handleReset = () => {
    // Remount children by bumping key (passed to wrapper if used),
    // plus clear error state so retry actually re-renders.
    this.setState({ hasError: false, message: '', retryKey: (this.state.retryKey || 0) + 1 })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full px-6" role="alert">
          <p className="text-5xl mb-4" aria-hidden="true">⚠️</p>
          <h1 className="text-lg font-semibold text-[#e8e8e8] mb-2">Something went wrong</h1>
          <p className="text-sm text-[#8e8e8e] mb-4 text-center max-w-md">
            An unexpected error occurred while rendering this page. Your data is safe — try again.
          </p>
          <details className="mb-4 max-w-md w-full text-xs text-[#8e8e8e]">
            <summary className="cursor-pointer hover:text-[#aaa]">Technical details</summary>
            <pre className="mt-2 p-2 rounded bg-[#1e1e1e] overflow-auto whitespace-pre-wrap break-words">{this.state.message}</pre>
          </details>
          <div className="flex gap-3">
            <button
              onClick={this.handleReset}
              className="px-4 py-2 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm transition-colors"
            >
              Try again
            </button>
            <a
              href="/chat"
              className="px-4 py-2 rounded-xl bg-[#2a2a2a] hover:bg-[#333] text-[#aaa] text-sm transition-colors"
            >
              Go to Chat
            </a>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// Key-based remount helper: <ErrorBoundary key={...}> forces fresh mount on reset.
export function withErrorBoundaryKey() {
  return Date.now()
}
