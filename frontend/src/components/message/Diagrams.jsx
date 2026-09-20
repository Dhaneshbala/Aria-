/** Legacy specialist diagram renderers (validated SVG / mermaid CDN). Extracted from Message.jsx. */
import React from 'react'
export function SvgDiagram({ code }) {
  const [scale, setScale] = React.useState(1)
  const [expanded, setExpanded] = React.useState(false)
  const sanitized = code.replace(/<script[\s\S]*?<\/script>/gi, '').trim()
  if (!sanitized.toLowerCase().startsWith('<svg')) {
    return (
      <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
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
  const Wrapper = expanded ? 'div' : 'div'
  return (
    <>
      <div className="bg-[#fafafa] rounded-b-xl border border-[#2a2a2a] border-t-0 p-3 relative group overflow-hidden">
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
          <span className="text-[10px] font-mono bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
          <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
          <button onClick={() => setExpanded(v => !v)} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center" title={expanded ? 'Collapse' : 'Fullscreen'}>{expanded ? '⤓' : '⤢'}</button>
          <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
        </div>
        <div className="flex items-center justify-center overflow-auto p-2" style={{ maxHeight: expanded ? '70vh' : 'auto' }}>
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-full [&>svg]:h-auto drop-shadow-[0_2px_8px_rgba(0,0,0,0.08)]" />
        </div>
        <div className="absolute bottom-2 left-3 text-[10px] font-mono tracking-wider text-[#9aa0a6] bg-white/90 backdrop-blur px-2 py-1 rounded-full border border-[#e8eaed]">Study Buddy diagram · pinch to zoom · drag to pan</div>
      </div>
      {expanded && <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20" onClick={() => setExpanded(false)} />}
      {expanded && (
        <div className="fixed inset-0 z-30 flex items-center justify-center p-4 sm:p-8 pointer-events-none">
          <div className="bg-[#fafafa] rounded-2xl shadow-2xl border border-[#2a2a2a] p-4 max-w-[90vw] max-h-[90vh] overflow-auto pointer-events-auto">
            <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-none" />
          </div>
        </div>
      )}
    </>
  )
}

// Label cleaner shared by the sanitizer and the repair builder: strips every
// character that breaks mermaid 10 node labels.
export function cleanMermaidLabel(s) {
  return String(s || '')
    .replace(/[()]/g, '-')           // parens break [...] and {...}
    .replace(/[[{}\]]/g, '-')        // nested brackets/braces break parsing
    .replace(/[#;:"'`<>|&]/g, (ch) => (ch === '&' ? ' and ' : ch === '|' ? ' - ' : ch === '#' ? 'No.' : ch === ':' ? ' -' : ch === ';' ? ',' : ''))
    .replace(/-{2,}/g, '-')
    .replace(/\s{2,}/g, ' ')
    .trim()
    .slice(0, 48)
}

// ── Mermaid sanitizer — small local LLMs emit labels that break mermaid 10 ──
// Parentheses/brackets/colons/semicolons/quotes/#&<>| inside node labels cause
// "Syntax error in text / mermaid version 10.9.8". Sanitize before render and
// fall back to a readable list when the diagram still won't parse.
export function sanitizeMermaid(raw) {
  let code = String(raw || '')
    .replace(/```\s*mermaid\s*/gi, '')
    .replace(/```/g, '')
    .replace(/\r/g, '')
    .trim()
  if (!code) return 'graph TD\n    A[Diagram coming up]'

  // Strip markdown + HTML that LLMs sneak into labels
  code = code
    .replace(/<[^>]*>/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')

  // Normalize unicode arrows to ASCII (models love —> / →)
  code = code
    .replace(/[—–―−]+>/g, '-->')
    .replace(/→/g, '-->')
    .replace(/⇒/g, '==>')
    .replace(/&gt;>?/g, '-->')

  const lines = code.split('\n').map(l => l.replace(/\s+$/, ''))
  const first = (lines.find(l => l.trim()) || '').trim().toLowerCase()

  const isSequence = first.startsWith('sequencediagram')
  const isPie = first.startsWith('pie')
  const isMindmap = first.startsWith('mindmap')
  const isGraph = /^(graph|flowchart)\b/.test(first)

  const cleanLabel = cleanMermaidLabel

  if (isSequence) {
    // Keep "A->>B: message" shape — do NOT strip < > (arrows need them).
    const out = lines.map((l, i) => {
      if (i === 0) return 'sequenceDiagram'
      return l.replace(/[#`]/g, '').slice(0, 120)
    }).filter((l, i) => i === 0 || l.trim()).slice(0, 20)
    return out.join('\n')
  }

  if (isPie) {
    const out = [lines[0].replace(/[`<>]/g, '').slice(0, 80) || 'pie title Breakdown']
    for (const l of lines.slice(1)) {
      const m = l.match(/^\s*"?([^":]+)"?\s*:\s*([\d.]+)\s*$/)
      if (m) out.push(`    "${cleanLabel(m[1]).replace(/"/g, '')}" : ${m[2]}`)
      else if (l.trim() && !/^\s*%%/.test(l)) {
        const label = cleanLabel(l.replace(/[:0-9.]+$/, ''))
        if (label) out.push(`    "${label}" : 1`)
      }
      if (out.length > 10) break
    }
    if (out.length < 2) out.push('    "A" : 1')
    return out.join('\n')
  }

  if (isMindmap) {
    // Mindmap shapes use ( ) [ ] { } — only strip markdown killers.
    return lines.map((l, i) => {
      if (i === 0) return 'mindmap'
      let body = l.replace(/[#;:"'`<>]/g, (ch) => (ch === ':' ? ' -' : ch === ';' ? ',' : ''))
      // Fix root((label (with parens))) → root((label - with parens -))
      // Greedy (.*) grabs the outermost ((...)) so inner parens get cleaned.
      body = body.replace(/\(\(\s*(.*)\s*\)\)/g, (_, inner) => `((${cleanLabel(inner)}))`)
      return body.slice(0, 100)
    }).filter((l, i) => i === 0 || l.trim()).slice(0, 24).join('\n')
  }

  // graph / flowchart (default): sanitize every [...] and {...} label
  let body = isGraph ? lines.join('\n') : `graph TD\n${lines.join('\n')}`
  body = body
    .replace(/\[([^\]\n]*)\]/g, (_, inner) => `[${cleanLabel(inner)}]`)
    .replace(/\{([^}\n]*)\}/g, (_, inner) => `{${cleanLabel(inner)}}`)
    .replace(/\(\(\s*(.+)\s*\)\)/g, (_, inner) => `((${cleanLabel(inner)}))`)
    .replace(/\(\s*([^)\]\n]{1,60}?)\s*\)/g, (m, inner) => {
      // Leave edge-label pipes |..| and link syntax alone; only fix (label) nodes
      if (/^(graph|flowchart|subgraph|end|click|style|class)/i.test(m)) return m
      if (/-->|---|===/.test(m)) return m
      return `(${cleanLabel(inner)})`
    })
  // Drop lines that are still empty or bare prose (models add explanations)
  const kept = []
  for (const l of body.split('\n')) {
    const t = l.trim()
    if (!t) continue
    if (/^(graph|flowchart|subgraph|end|click|style|classDef)\b/i.test(t)) { kept.push(l); continue }
    if (/-->|---|==>|-.->|~~~|&|%%/.test(l)) { kept.push(l); continue }
    if (/^\s*[A-Za-z0-9_]+\s*[\[({]/.test(l)) { kept.push(l); continue }
    if (/^\s*[A-Za-z0-9_]+\s*-->/.test(l)) { kept.push(l); continue }
    if (/^\s*%%/.test(l)) { kept.push(l); continue }
    // Bare prose line — skip (it would be a syntax error)
    if (!/[\[({>]/.test(t) && kept.length > 1) continue
    kept.push(l)
  }
  const result = kept.slice(0, 24).join('\n').trim()
  return result.includes('\n') ? result : `${result}\n    A[Diagram]`
}

// Pull human-readable steps out of (possibly broken) mermaid for the fallback card.
export function extractMermaidLabels(raw) {
  const labels = []
  const code = String(raw || '')
  const bracket = [...code.matchAll(/\[([^\]\n]{1,60})\]/g)].map(m => m[1].trim())
  const brace = [...code.matchAll(/\{([^}\n]{1,60})\}/g)].map(m => m[1].trim())
  const seq = [...code.matchAll(/:\s*([^\n]{1,80})/g)].map(m => m[1].trim())
  const pie = [...code.matchAll(/"([^"]{1,40})"\s*:/g)].map(m => m[1].trim())
  for (const l of [...bracket, ...brace, ...pie, ...seq]) {
    const clean = l.replace(/[*`#]/g, '').trim().slice(0, 60)
    if (clean && !labels.includes(clean) && labels.length < 8) labels.push(clean)
  }
  // mindmap branches: indented plain lines
  if (!labels.length) {
    for (const line of code.split('\n')) {
      const t = line.trim().replace(/^[*•\-\d.)\s]+/, '').trim()
      if (t && !/^(mindmap|graph|flowchart|sequenceDiagram|pie|root)/i.test(t) && t.length > 2 && labels.length < 8)
        labels.push(t.slice(0, 60))
    }
  }
  return labels
}

// Build a guaranteed-valid linear flowchart from extracted labels.
// Last-resort self-heal: when the model's mermaid won't parse even after
// sanitizing, render this instead of an error card so the student always
// gets a visual. Returns null when nothing usable can be extracted.
export function buildRepairGraph(raw) {
  const labels = extractMermaidLabels(raw)
    .map((l) => cleanMermaidLabel(l))
    .filter(Boolean)
    .slice(0, 6)
  if (!labels.length) return null
  const ids = labels.map((_, i) => String.fromCharCode(65 + i))
  const lines = ['graph TD']
  labels.forEach((l, i) => lines.push(`    ${ids[i]}[${l || `Step ${i + 1}`}]`))
  for (let i = 0; i < ids.length - 1; i++) lines.push(`    ${ids[i]} --> ${ids[i + 1]}`)
  return lines.join('\n')
}

// ── Mermaid renderer — CDN, themed, interactive ─────────────────────────────

export function MermaidDiagram({ code }) {
  const [svg, setSvg] = React.useState(null)
  const [error, setError] = React.useState(null)
  const [cleaned, setCleaned] = React.useState('')
  const [repaired, setRepaired] = React.useState(false)
  const [scale, setScale] = React.useState(1)
  React.useEffect(() => {
    let cancelled = false
    setSvg(null)
    setError(null)
    setRepaired(false)
    async function render() {
      let clean = sanitizeMermaid(code)
      if (!cancelled) setCleaned(clean)
      const tryParse = async (text) => {
        if (!window.mermaid.parse) return true
        try { await window.mermaid.parse(text); return true }
        catch { return false }
      }
      try {
        if (!window.mermaid) {
          await new Promise((resolve, reject) => {
            const s = document.createElement('script')
            s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.8/dist/mermaid.min.js'
            s.onload = resolve
            s.onerror = () => reject(new Error('Could not load diagram library (offline?)'))
            document.head.appendChild(s)
          })
        }
        // Always (re)initialize: a previous page may have set startOnLoad or
        // left suppressErrorRendering off, which makes mermaid return an
        // error-SVG ("Syntax error in text…") instead of throwing.
        window.mermaid.initialize({
          startOnLoad: false,
          suppressErrorRendering: true,
          theme: 'base',
          securityLevel: 'strict',
          maxTextSize: 5000,
          flowchart: { htmlLabels: false },
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
        // Self-heal: if the sanitized diagram still won't parse, rebuild a
        // guaranteed-valid flowchart from its labels so the student always
        // gets a visual instead of an error card.
        if (!(await tryParse(clean))) {
          const fixed = buildRepairGraph(code)
          if (fixed && await tryParse(fixed)) {
            clean = fixed
            if (!cancelled) { setCleaned(fixed); setRepaired(true) }
          } else {
            throw new Error('Diagram syntax not supported — showing steps instead')
          }
        }
        const id = 'm' + Math.random().toString(36).slice(2, 9)
        const { svg } = await window.mermaid.render(id, clean)
        // Belt-and-braces: if error-SVG still slips through, treat as failure
        // so we show the friendly fallback instead of "Syntax error in text".
        if (/syntax error in text|mermaid version/i.test(svg || '')) {
          throw new Error('Diagram syntax not supported — showing steps instead')
        }
        if (!cancelled) setSvg(svg)
      } catch (e) {
        if (!cancelled) setError(String(e.message || e).slice(0, 300))
      }
    }
    render()
    return () => { cancelled = true }
  }, [code])
  if (error) {
    const steps = extractMermaidLabels(cleaned || code)
    return (
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-b-xl p-4">
        <p className="text-xs text-[#bbb] font-medium mb-1">Diagram couldn't render — here's the gist:</p>
        {steps.length > 0 ? (
          <ol className="text-xs text-[#888] leading-relaxed list-decimal ml-4 space-y-0.5">
            {steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        ) : (
          <p className="text-xs text-[#666]">The AI's diagram had invalid syntax. Ask me to "explain it as steps" instead.</p>
        )}
        <details className="mt-2">
          <summary className="text-[11px] text-[#555] cursor-pointer hover:text-[#888]">Details · {error}</summary>
          <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-lg p-3 overflow-x-auto mt-2 m-0">
            <code className="text-[11px] font-mono text-[#777] leading-relaxed">{cleaned || code}</code>
          </pre>
        </details>
      </div>
    )
  }
  if (!svg) {
    return <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-b-xl p-8 text-center text-xs text-[#666] flex items-center justify-center gap-2"><span className="w-3 h-3 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" /> Rendering diagram…</div>
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
    <div className="bg-[#131314] rounded-b-xl border border-[#2a2a2a] border-t-0 p-3 relative group overflow-hidden">
      {repaired && (
        <span className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full bg-[#7c6af7]/15 border border-[#7c6af7]/30 text-[#a89bf8] z-10" title="The AI's diagram had invalid syntax — Study Buddy rebuilt it automatically">
          ✨ auto-fixed
        </span>
      )}
      <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
        <span className="text-[10px] font-mono bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
        <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
        <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
      </div>
      <div className="flex items-center justify-center overflow-auto p-2">
        <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: svg }} className="[&>svg]:max-w-full [&>svg]:h-auto" />
      </div>
    </div>
  )
}

// ── Copy message button ───────────────────────────────────────────────────────
