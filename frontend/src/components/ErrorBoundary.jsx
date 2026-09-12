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
    this.setState({ hasError: false, message: '' })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full px-6">
          <p className="text-5xl mb-4">⚠️</p>
          <h1 className="text-lg font-semibold text-[#e8e8e8] mb-2">Something went wrong</h1>
          <p className="text-sm text-[#666] mb-4 text-center max-w-md">
            {this.state.message || 'An unexpected error occurred while rendering this page.'}
          </p>
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
