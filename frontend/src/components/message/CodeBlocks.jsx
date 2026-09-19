/** Copy button + fenced code blocks (svg/mermaid render inline). Extracted from Message.jsx. */
import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { SvgDiagram, MermaidDiagram } from './Diagrams'
export function CopyMessageButton({ content }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button onClick={handleCopy}
      className="absolute top-0 right-0 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 bg-[#1a1a1a] border border-[#2a2a2a] text-[#666] hover:text-white transition-all"
      title="Copy response">
      {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
    </button>
  )
}

// ── Code block with copy ──────────────────────────────────────────────────────

export function CodeBlock({ code, lang, defer }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  const lower = (lang || '').toLowerCase()
  // While the answer is still streaming the fenced block is incomplete —
  // mounting the diagram renderer per token causes spinner flicker and
  // transient parse errors. Show plain code until the stream finishes.
  if (defer && (lower === 'svg' || lower === 'mermaid')) {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">diagram · {lower} · drawing…</span>
        </div>
        <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
          <code className="text-xs font-mono text-[#666] leading-relaxed">{code}</code>
        </pre>
      </div>
    )
  }
  if (lower === 'svg') {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">diagram · svg</span>
          <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
            {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <SvgDiagram code={code} />
      </div>
    )
  }
  if (lower === 'mermaid') {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">diagram · mermaid</span>
          <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
            {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <MermaidDiagram code={code} />
      </div>
    )
  }
  return (
    <div className="my-3">
      <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
        <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">{lang || 'code'}</span>
        <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
          {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
        </button>
      </div>
      <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#ccc] leading-relaxed">{code}</code>
      </pre>
    </div>
  )
}

// ── Tool result (web search, vision, youtube) ─────────────────────────────────
