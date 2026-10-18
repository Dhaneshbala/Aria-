import { useState, useEffect } from 'react'
import { Copy, Check } from 'lucide-react'
import DOMPurify from 'dompurify'

/** Model-produced SVG is untrusted input — strip scripts/event handlers. */
function cleanSvg(svg) {
  try {
    return DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true } })
  } catch {
    return ''
  }
}

// ── SVG Diagram renderer — interactive, exportable, premium ──────────────────
function SvgDiagram({ code }) {
  const [scale, setScale] = useState(1)
  const [expanded, setExpanded] = useState(false)
  const sanitized = cleanSvg(code.replace(/<script[\s\S]*?<\/script>/gi, '').trim())
  if (!sanitized.toLowerCase().startsWith('<svg')) {
    return (
      <pre className="bg-[#0d0d0d] border border-aria-border rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#ccc] leading-relaxed">{code}</code>
      </pre>
    )
  }
  const download = () => {
    const blob = new Blob([sanitized], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'aria-diagram.svg'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <>
      <div className="bg-[#fafafa] rounded-b-xl border border-aria-border border-t-0 p-3 relative group overflow-hidden">
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-aria-border text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
          <span className="text-[10px] font-mono bg-[#1a1a1a] border border-aria-border text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
          <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-aria-border text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
          <button onClick={() => setExpanded(v => !v)} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-aria-border text-[#aaa] hover:text-white flex items-center justify-center" title={expanded ? 'Collapse' : 'Fullscreen'}>{expanded ? '⤓' : '⤢'}</button>
          <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
        </div>
        <div className="flex items-center justify-center overflow-auto p-2" style={{ maxHeight: expanded ? '70vh' : 'auto' }}>
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-full [&>svg]:h-auto drop-shadow-[0_2px_8px_rgba(0,0,0,0.08)]" />
        </div>
        <div className="absolute bottom-2 left-3 text-[10px] font-mono tracking-wider text-aria-muted bg-white/90 backdrop-blur px-2 py-1 rounded-full border border-[#e8eaed]">ARIA diagram · pinch to zoom · drag to pan</div>
      </div>
      {/* Fullscreen backdrop — Escape/click dismiss; the diagram toolbar above keeps keyboard access */}
      {expanded && <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20" onClick={() => setExpanded(false)} aria-hidden="true" />}
      {expanded && (
        <div className="fixed inset-0 z-30 flex items-center justify-center p-4 sm:p-8 pointer-events-none">
          <div className="bg-[#fafafa] rounded-2xl shadow-2xl border border-aria-border p-4 max-w-[90vw] max-h-[90vh] overflow-auto pointer-events-auto">
            <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-none" />
          </div>
        </div>
      )}
    </>
  )
}
// ── Mermaid renderer — CDN, themed, interactive ─────────────────────────────
function MermaidDiagram({ code }) {
  const [svg, setSvg] = useState(null)
  const [error, setError] = useState(null)
  const [scale, setScale] = useState(1)
  useEffect(() => {
    let cancelled = false
    async function render() {
      try {
        if (!window.mermaid) {
          await new Promise((resolve, reject) => {
            const s = document.createElement('script')
            s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'
            s.onload = resolve
            s.onerror = reject
            document.head.appendChild(s)
          })
          window.mermaid.initialize({
            startOnLoad: false,
            theme: 'base',
            securityLevel: 'strict',
            themeVariables: {
              primaryColor: '#7c6af7',
              primaryTextColor: '#e3e3e3',
              primaryBorderColor: '#3c4043',
              lineColor: '#9aa0a6',
              secondaryColor: '#1e1f20',
              tertiaryColor: '#2d2e30',
              background: '#131314',
              mainBkg: '#1e1f20',
              nodeBorder: '#7c6af7',
              clusterBkg: '#1e1f20',
              titleColor: '#e3e3e3',
              edgeLabelBackground: '#2d2e30',
            }
          })
        }
        const id = 'm' + Math.random().toString(36).slice(2, 9)
        const { svg } = await window.mermaid.render(id, code)
        if (!cancelled) setSvg(cleanSvg(svg))
      } catch (e) {
        if (!cancelled) setError(String(e.message || e))
      }
    }
    render()
    return () => { cancelled = true }
  }, [code])
  if (error) {
    return (
      <pre className="bg-[#0d0d0d] border border-aria-border rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#f87171] leading-relaxed">Mermaid error: {error}{"\n\n"}{code}</code>
      </pre>
    )
  }
  if (!svg) {
    return <div className="bg-[#1a1a1a] border border-aria-border rounded-b-xl p-8 text-center text-xs text-[#888] flex items-center justify-center gap-2"><span className="w-3 h-3 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" /> Rendering diagram…</div>
  }
  const download = () => {
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'aria-mermaid.svg'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <div className="bg-aria-bg rounded-b-xl border border-aria-border border-t-0 p-3 relative group overflow-hidden">
      <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-aria-border text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
        <span className="text-[10px] font-mono bg-[#1a1a1a] border border-aria-border text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
        <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-aria-border text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
        <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
      </div>
      <div className="flex items-center justify-center overflow-auto p-2">
        <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: svg }} className="[&>svg]:max-w-full [&>svg]:h-auto" />
      </div>
    </div>
  )
}
// ── Code block with copy ──────────────────────────────────────────────────────

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  const lower = (lang || '').toLowerCase()
  if (lower === 'svg') {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-aria-border border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">diagram · svg</span>
          <button onClick={copy} className="text-[#888] hover:text-[#aaa] transition-colors p-0.5">
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
        <div className="flex items-center justify-between bg-[#161616] border border-aria-border border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">diagram · mermaid</span>
          <button onClick={copy} className="text-[#888] hover:text-[#aaa] transition-colors p-0.5">
            {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <MermaidDiagram code={code} />
      </div>
    )
  }
  return (
    <div className="my-3">
      <div className="flex items-center justify-between bg-[#161616] border border-aria-border border-b-0 rounded-t-xl px-3 py-1.5">
        <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">{lang || 'code'}</span>
        <button onClick={copy} className="text-[#888] hover:text-[#aaa] transition-colors p-0.5">
          {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
        </button>
      </div>
      <pre className="bg-[#0d0d0d] border border-aria-border rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#ccc] leading-relaxed">{code}</code>
      </pre>
    </div>
  )
}

export { SvgDiagram, MermaidDiagram, CodeBlock }
