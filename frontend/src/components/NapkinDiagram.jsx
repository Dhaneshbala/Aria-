import React, { useId, useEffect, useMemo, useRef, useState } from 'react'
import { NAPKIN_TYPES, THEMES } from './napkin/themes'
import { W, canvasHeight, colorFor } from './napkin/diagramUtils'
import { renderBody } from './napkin/DiagramLayouts'
import { useNapkinExport } from './napkin/useNapkinExport'

export { NAPKIN_TYPES }

/**
 * NapkinDiagram — Napkin AI-style visual, rendered INLINE in chat (not a page).
 * Backend sends a small editable spec {visual_type, title, nodes[], edges[]};
 * this component lays it out deterministically as pretty SVG.
 * Like Napkin: switch visual type, switch theme, edit text inline, export.
 *
 * Shell component — themes in napkin/themes.js, helpers in
 * napkin/diagramUtils.js, layouts in napkin/DiagramLayouts.jsx,
 * export logic in napkin/useNapkinExport.js.
 */

export default function NapkinDiagram({ spec: initialSpec }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const svgRef = useRef(null)
  const idRef = useRef(100)
  const [title, setTitle] = useState(initialSpec?.title || 'Visual')
  const [nodes, setNodes] = useState(initialSpec?.nodes || [])
  const [vtype, setVtype] = useState(initialSpec?.visual_type || 'flowchart')
  const [themeId, setThemeId] = useState('colorful')
  const [customize, setCustomize] = useState(false)
  const [scale, setScale] = useState(1)
  const theme = THEMES[themeId] || THEMES.colorful
  const H = canvasHeight(vtype, nodes.length)

  // Sync when a new spec arrives (e.g. background LLM refinement or new chat).
  useEffect(() => {
    setTitle(initialSpec?.title || 'Visual')
    setNodes(initialSpec?.nodes || [])
    setVtype(initialSpec?.visual_type || 'flowchart')
  }, [initialSpec?.title, initialSpec?.visual_type, JSON.stringify(initialSpec?.nodes)])

  const patchNode = (idx, field, value) => {
    setNodes(ns => ns.map((n, i) => (i === idx ? { ...n, [field]: value } : n)))
  }
  const removeNode = (idx) => {
    if (nodes.length <= 2) return
    setNodes(ns => ns.filter((_, i) => i !== idx))
  }
  const addNode = () => {
    if (nodes.length >= 8) return
    idRef.current += 1
    setNodes(ns => [...ns, { id: `n${Date.now() % 100000}-${idRef.current}`, label: 'New idea', sub: '', icon: '📌' }])
  }

  const body = useMemo(
    () => renderBody(vtype, nodes, theme, uid),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [vtype, JSON.stringify(nodes), themeId, uid],
  )

  const { downloadSVG, downloadPNG, downloadPDF } = useNapkinExport({
    svgRef, title, theme, canvasW: W, canvasH: H,
  })

  if (!nodes.length) return null

  return (
    <div className="w-full my-3">
      <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
        <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">
          ✨ visual · {vtype} · {theme.label}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} aria-label="Zoom out" className="w-6 h-6 rounded-full text-[#777] hover:text-white text-xs">−</button>
          <span className="text-[10px] font-mono text-[#666] min-w-[34px] text-center" aria-live="polite">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale(s => Math.min(2, s + 0.15))} aria-label="Zoom in" className="w-6 h-6 rounded-full text-[#777] hover:text-white text-xs">+</button>
          <button onClick={() => setCustomize(c => !c)} aria-expanded={customize} aria-label={customize ? 'Finish customizing' : 'Customize diagram'} className={`text-[11px] px-2.5 h-6 rounded-full ml-1 transition-colors ${customize ? 'bg-[#7c6af7] text-white' : 'bg-[#2a2a2a] text-[#aaa] hover:text-white'}`}>
            {customize ? 'Done' : 'Customize'}
          </button>
        </div>
      </div>

      <div className="border border-[#2a2a2a] border-t-0 rounded-b-xl overflow-hidden" style={{ background: theme.bg }}>
        <div className="overflow-auto flex justify-center p-2">
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'top center', transition: 'transform 0.15s ease' }}>
            <svg ref={svgRef} role="img" aria-label={title} viewBox={`0 0 ${W} ${H}`} width={W} style={{ maxWidth: '100%', height: 'auto', fontFamily: theme.font }}>
              <defs>
                <filter id={`napkin-soft-${uid}`} x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="4" floodOpacity="0.1" />
                </filter>
                <linearGradient id={`napkin-grad-0-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor={theme.palette[0]} stopOpacity="0.15" />
                  <stop offset="100%" stopColor={theme.palette[1]} stopOpacity="0.08" />
                </linearGradient>
              </defs>
              <rect width={W} height={H} fill={theme.bg} />
              {/* Subtle grid pattern */}
              <pattern id={`napkin-grid-${uid}`} width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke={theme.line} strokeWidth="0.3" opacity="0.4" />
              </pattern>
              <rect width={W} height={H} fill={`url(#napkin-grid-${uid})`} />
              <text x={W / 2} y={34} textAnchor="middle" fontSize={theme.sketch ? 26 : 15} fontWeight="700" fill={theme.text} letterSpacing={theme.sketch ? 0 : 2}>
                {title.toUpperCase().slice(0, 48)}
              </text>
              <g>
                {body}
              </g>
            </svg>
          </div>
        </div>

        <div className="flex items-center justify-between px-3 py-2 border-t" style={{ borderColor: theme.line, background: theme.card }}>
          <span className="text-[10px] font-mono" style={{ color: theme.sub }}>click Customize to edit text · switch style</span>
          <div className="flex items-center gap-1.5">
            {[
              { l: 'SVG', fn: downloadSVG },
              { l: 'PNG', fn: downloadPNG },
              { l: 'PDF', fn: downloadPDF },
            ].map(b => (
              <button key={b.l} onClick={b.fn} aria-label={`Download as ${b.l}`} className="text-[11px] px-2.5 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">{b.l}</button>
            ))}
          </div>
        </div>

        {customize && (
          <div className="px-3 py-3 border-t space-y-3 max-h-72 overflow-y-auto" style={{ borderColor: theme.line, background: theme.bg }}>
            <div>
              <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: theme.sub }}>Visual type</p>
              <div className="flex flex-wrap gap-1.5">
                {NAPKIN_TYPES.map(t => (
                  <button key={t.id} onClick={() => setVtype(t.id)} title={t.hint}
                    className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${vtype === t.id ? 'bg-[#7c6af7] text-white border-[#7c6af7]' : ''}`}
                    style={vtype === t.id ? undefined : { borderColor: theme.line, color: theme.text, background: theme.card }}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: theme.sub }}>Style</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(THEMES).map(([id, th]) => (
                  <button key={id} onClick={() => setThemeId(id)}
                    className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${themeId === id ? 'bg-[#7c6af7] text-white border-[#7c6af7]' : ''}`}
                    style={themeId === id ? undefined : { borderColor: theme.line, color: theme.text, background: theme.card }}>
                    {th.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: theme.sub }}>Title</p>
              <input value={title} onChange={e => setTitle(e.target.value.slice(0, 60))} aria-label="Diagram title"
                className="w-full text-sm px-2.5 py-1.5 rounded-lg border bg-transparent outline-none focus:border-[#7c6af7]"
                style={{ borderColor: theme.line, color: theme.text }} />
            </div>
            <div className="space-y-1.5">
              {nodes.map((n, i) => (
                <div key={n.id || i} className="flex items-center gap-1.5">
                  <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0"
                    style={{ background: colorFor(theme, i) + '22', border: `1px solid ${colorFor(theme, i)}` }} aria-hidden="true">
                    {n.icon || '📌'}
                  </span>
                  <input value={n.icon || ''} onChange={e => patchNode(i, 'icon', e.target.value.slice(0, 8))} aria-label={`Icon for box ${i + 1}`}
                    className="w-10 text-center text-sm px-1 py-1.5 rounded-lg border bg-transparent outline-none"
                    style={{ borderColor: theme.line, color: theme.text }} title="Icon (emoji)" />
                  <input value={n.label} onChange={e => patchNode(i, 'label', e.target.value.slice(0, 48))} aria-label={`Label for box ${i + 1}`}
                    className="flex-1 text-sm px-2.5 py-1.5 rounded-lg border bg-transparent outline-none"
                    style={{ borderColor: theme.line, color: theme.text }} placeholder="Label" />
                  <input value={n.sub || ''} onChange={e => patchNode(i, 'sub', e.target.value.slice(0, 80))} aria-label={`Detail for box ${i + 1}`}
                    className="flex-1 text-xs px-2.5 py-1.5 rounded-lg border bg-transparent outline-none hidden sm:block"
                    style={{ borderColor: theme.line, color: theme.sub }} placeholder="Detail (optional)" />
                  <button onClick={() => removeNode(i)} aria-label={`Remove box ${i + 1}`} className="text-[#999] hover:text-red-400 px-1" title="Remove">×</button>
                </div>
              ))}
              {nodes.length < 8 && (
                <button onClick={addNode} className="text-[11px] px-3 py-1.5 rounded-full border border-dashed w-full"
                  style={{ borderColor: theme.line, color: theme.sub }}>+ Add box</button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
