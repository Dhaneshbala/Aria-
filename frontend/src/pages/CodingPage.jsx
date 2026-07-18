import { useState } from 'react'
import { Code, Copy, Check, Terminal, Bug, Lightbulb, FileCode, GitBranch, TestTube } from 'lucide-react'

const CODE_FEATURES = [
  { id: 'explain',   icon: Lightbulb, label: 'Explain Code',   placeholder: 'Paste code to explain...' },
  { id: 'debug',     icon: Bug,       label: 'Debug Code',     placeholder: 'Paste code with a bug...' },
  { id: 'generate',  icon: FileCode,  label: 'Generate Code',  placeholder: 'Describe what you want to build...' },
  { id: 'refactor',  icon: GitBranch, label: 'Refactor Code',  placeholder: 'Paste code to improve...' },
  { id: 'tests',     icon: TestTube,  label: 'Generate Tests', placeholder: 'Paste function/class to test...' },
  { id: 'terminal',  icon: Terminal,  label: 'Terminal Help',  placeholder: 'What command do you need help with?' },
]

export default function CodingPage() {
  const [activeFeature, setActiveFeature] = useState('explain')
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)

  const feature = CODE_FEATURES.find(f => f.id === activeFeature)

  const handleSubmit = async () => {
    if (!input.trim() || loading) return
    setLoading(true)
    setOutput('')
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          message: `[CODE MODE] ${feature.label}:\n\n${input}`,
          mode: 'normal',
        }),
      })
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'text') setOutput(t => t + data.content)
            } catch {}
          }
        }
      }
    } catch (e) {
      setOutput('Error: ' + e.message)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <Code size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Coding Assistant</h1>
      </div>

      {/* Feature tabs */}
      <div className="flex gap-1 bg-[#111] border border-[#1e1e1e] p-1 rounded-xl mb-4 overflow-x-auto">
        {CODE_FEATURES.map(f => (
          <button key={f.id} onClick={() => { setActiveFeature(f.id); setOutput(''); setInput('') }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs whitespace-nowrap transition-colors flex-shrink-0 ${
              activeFeature === f.id
                ? 'bg-[#7c6af7] text-white'
                : 'text-[#666] hover:text-[#aaa]'
            }`}>
            <f.icon size={13} /> {f.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="space-y-3">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={feature?.placeholder}
          rows={8}
          className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50 resize-none font-mono"
        />
        <button onClick={handleSubmit} disabled={!input.trim() || loading}
          className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading ? 'Processing...' : feature?.label}
        </button>
      </div>

      {/* Output */}
      {output && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-[#555]">Output</span>
            <button onClick={() => navigator.clipboard.writeText(output)}
              className="text-xs text-[#555] hover:text-[#aaa] flex items-center gap-1">
              <Copy size={11} /> Copy
            </button>
          </div>
          <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] whitespace-pre-wrap overflow-x-auto font-mono leading-relaxed">
            {output}
          </pre>
        </div>
      )}
    </div>
  )
}
