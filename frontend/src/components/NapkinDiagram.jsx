import React, { useMemo, useRef, useState } from 'react'

/**
 * NapkinDiagram — Napkin AI-style visual, rendered INLINE in chat (not a page).
 * Backend sends a small editable spec {visual_type, title, nodes[], edges[]};
 * this component lays it out deterministically as pretty SVG.
 * Like Napkin: switch visual type, switch theme, edit text inline, export.
 */

export const NAPKIN_TYPES = [
  { id: 'flowchart', label: 'Flow', hint: 'order & decisions' },
  { id: 'steps', label: 'Steps', hint: 'numbered sequence' },
  { id: 'mindmap', label: 'Mind map', hint: 'big-picture branches' },
  { id: 'cycle', label: 'Cycle', hint: 'loops back' },
  { id: 'timeline', label: 'Timeline', hint: 'events in time' },
  { id: 'comparison', label: 'Compare', hint: 'side by side' },
  { id: 'pyramid', label: 'Pyramid', hint: 'hierarchy' },
  { id: 'venn', label: 'Venn', hint: 'overlaps' },
  { id: 'pie', label: 'Pie', hint: 'shares of whole' },
  { id: 'bar', label: 'Bars', hint: 'compare sizes' },
]

const THEMES = {
  colorful: {
    label: 'Colorful', bg: '#ffffff', card: '#ffffff', text: '#1e1f20', sub: '#5f6368',
    line: '#dadce0', font: 'Inter, system-ui, sans-serif', sketch: false,
    palette: ['#7c6af7', '#f59e0b', '#10b981', '#ec4899', '#3b82f6', '#ef4444', '#14b8a6', '#f97316'],
  },
  pastel: {
    label: 'Pastel', bg: '#fdf8f3', card: '#ffffff', text: '#3f3d56', sub: '#8a87a0',
    line: '#e8ddcf', font: 'Inter, system-ui, sans-serif', sketch: false,
    palette: ['#a78bfa', '#fbbf24', '#6ee7b7', '#f9a8d4', '#93c5fd', '#fca5a5', '#5eead4', '#fdba74'],
  },
  minimal: {
    label: 'Minimal', bg: '#ffffff', card: '#fafafa', text: '#111111', sub: '#666666',
    line: '#e5e5e5', font: 'Inter, system-ui, sans-serif', sketch: false,
    palette: ['#111111', '#444444', '#777777', '#999999', '#bbbbbb', '#dddddd', '#333333', '#555555'],
  },
  dark: {
    label: 'Dark', bg: '#131314', card: '#1e1f20', text: '#e3e3e3', sub: '#9aa0a6',
    line: '#3c4043', font: 'Inter, system-ui, sans-serif', sketch: false,
    palette: ['#a89bf8', '#fbbc04', '#34d399', '#f472b6', '#60a5fa', '#f87171', '#2dd4bf', '#fb923c'],
  },
  sketch: {
    label: 'Sketch ✏️', bg: '#fdfbf3', card: '#fffef9', text: '#2b2b2b', sub: '#6b6257',
    line: '#d8cfbd', font: "'Caveat','Segoe Print','Comic Sans MS',cursive", sketch: true,
    palette: ['#6c5ce7', '#e17055', '#00b894', '#e84393', '#0984e3', '#d63031', '#00cec9', '#fdcb6e'],
  },
}

const W = 640
const H = 420

function wrap(text, max = 20) {
  const words = String(text || '').split(/\s+/)
  const lines = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > max && cur) { lines.push(cur); cur = w }
    else cur = (cur + ' ' + w).trim()
  }
  if (cur) lines.push(cur)
  return lines.slice(0, 3)
}

function numFrom(label, fallback) {
  const m = String(label).match(/(\d+(?:\.\d+)?)\s*%/)
  if (m) return parseFloat(m[1])
  const m2 = String(label).match(/(\d+(?:\.\d+)?)/)
  if (m2) return parseFloat(m2[1])
  return fallback
}

function colorFor(theme, i) {
  return theme.palette[i % theme.palette.length]
}

export default function NapkinDiagram({ spec: initialSpec }) {
  const svgRef = useRef(null)
  const [title, setTitle] = useState(initialSpec?.title || 'Visual')
  const [nodes, setNodes] = useState(initialSpec?.nodes || [])
  const [vtype, setVtype] = useState(initialSpec?.visual_type || 'flowchart')
  const [themeId, setThemeId] = useState('colorful')
  const [customize, setCustomize] = useState(false)
  const [scale, setScale] = useState(1)
  const theme = THEMES[themeId] || THEMES.colorful

  const patchNode = (idx, field, value) => {
    setNodes(ns => ns.map((n, i) => (i === idx ? { ...n, [field]: value } : n)))
  }
  const removeNode = (idx) => {
    if (nodes.length <= 2) return
    setNodes(ns => ns.filter((_, i) => i !== idx))
  }
  const addNode = () => {
    if (nodes.length >= 8) return
    setNodes(ns => [...ns, { id: `n${Date.now() % 10000}`, label: 'New idea', sub: '', icon: '📌' }])
  }

  const body = useMemo(
    () => renderBody(vtype, nodes, theme),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [vtype, JSON.stringify(nodes), themeId],
  )

  const serialize = () => {
    if (!svgRef.current) return null
    const clone = svgRef.current.cloneNode(true)
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    return new XMLSerializer().serializeToString(clone)
  }
  const downloadSVG = () => {
    const s = serialize()
    if (!s) return
    const blob = new Blob([s], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.replace(/\s+/g, '-').toLowerCase() || 'aria-visual'}.svg`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const downloadPNG = () => {
    const s = serialize()
    if (!s) return
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = W * 2
      canvas.height = H * 2
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = theme.bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0, W, H)
      canvas.toBlob((blob) => {
        if (!blob) return
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${title.replace(/\s+/g, '-').toLowerCase() || 'aria-visual'}.png`
        a.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      })
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(s)))
  }
  const downloadPDF = async () => {
    const s = serialize()
    if (!s) return
    const { jsPDF } = await import('jspdf')
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = W * 2
      canvas.height = H * 2
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = theme.bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0, W, H)
      const pdf = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'landscape' })
      const pw = pdf.internal.pageSize.getWidth()
      const ph = pdf.internal.pageSize.getHeight()
      pdf.setFontSize(14)
      pdf.text(title, 40, 40)
      pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 40, 55, pw - 80, ((pw - 80) * H) / W)
      pdf.save(`${title.replace(/\s+/g, '-').toLowerCase() || 'aria-visual'}.pdf`)
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(s)))
  }

  if (!nodes.length) return null

  return (
    <div className="w-full my-3">
      <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
        <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">
          ✨ visual · {vtype} · {theme.label}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-6 h-6 rounded-full text-[#777] hover:text-white text-xs">−</button>
          <span className="text-[10px] font-mono text-[#666] min-w-[34px] text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale(s => Math.min(2, s + 0.15))} className="w-6 h-6 rounded-full text-[#777] hover:text-white text-xs">+</button>
          <button onClick={() => setCustomize(c => !c)} className={`text-[11px] px-2.5 h-6 rounded-full ml-1 transition-colors ${customize ? 'bg-[#7c6af7] text-white' : 'bg-[#2a2a2a] text-[#aaa] hover:text-white'}`}>
            {customize ? 'Done' : 'Customize'}
          </button>
        </div>
      </div>

      <div className="border border-[#2a2a2a] border-t-0 rounded-b-xl overflow-hidden" style={{ background: theme.bg }}>
        <div className="overflow-auto flex justify-center p-2">
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'top center', transition: 'transform 0.15s ease' }}>
            <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width={W} style={{ maxWidth: '100%', height: 'auto', fontFamily: theme.font }}>
              <defs>
                <filter id="napkin-rough">
                  <feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="2" result="n" />
                  <feDisplacementMap in="SourceGraphic" in2="n" scale="3" />
                </filter>
                <filter id="napkin-soft" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="5" floodOpacity="0.12" />
                </filter>
              </defs>
              <rect width={W} height={H} fill={theme.bg} />
              <text x={W / 2} y={34} textAnchor="middle" fontSize={theme.sketch ? 26 : 15} fontWeight="700" fill={theme.text} letterSpacing={theme.sketch ? 0 : 2}>
                {title.toUpperCase().slice(0, 48)}
              </text>
              <g filter={theme.sketch ? 'url(#napkin-rough)' : undefined}>
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
              <button key={b.l} onClick={b.fn} className="text-[11px] px-2.5 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">{b.l}</button>
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
              <input value={title} onChange={e => setTitle(e.target.value.slice(0, 60))}
                className="w-full text-sm px-2.5 py-1.5 rounded-lg border bg-transparent outline-none focus:border-[#7c6af7]"
                style={{ borderColor: theme.line, color: theme.text }} />
            </div>
            <div className="space-y-1.5">
              {nodes.map((n, i) => (
                <div key={n.id || i} className="flex items-center gap-1.5">
                  <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0"
                    style={{ background: colorFor(theme, i) + '22', border: `1px solid ${colorFor(theme, i)}` }}>
                    {n.icon || '📌'}
                  </span>
                  <input value={n.icon || ''} onChange={e => patchNode(i, 'icon', e.target.value.slice(0, 4))}
                    className="w-10 text-center text-sm px-1 py-1.5 rounded-lg border bg-transparent outline-none"
                    style={{ borderColor: theme.line, color: theme.text }} title="Icon (emoji)" />
                  <input value={n.label} onChange={e => patchNode(i, 'label', e.target.value.slice(0, 48))}
                    className="flex-1 text-sm px-2.5 py-1.5 rounded-lg border bg-transparent outline-none"
                    style={{ borderColor: theme.line, color: theme.text }} placeholder="Label" />
                  <input value={n.sub || ''} onChange={e => patchNode(i, 'sub', e.target.value.slice(0, 80))}
                    className="flex-1 text-xs px-2.5 py-1.5 rounded-lg border bg-transparent outline-none hidden sm:block"
                    style={{ borderColor: theme.line, color: theme.sub }} placeholder="Detail (optional)" />
                  <button onClick={() => removeNode(i)} className="text-[#999] hover:text-red-400 px-1" title="Remove">×</button>
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

// ── Layout engine: one renderer per visual type ──────────────────────────────

function NodeCard({ x, y, w, h, node, color, theme, num }) {
  const lines = wrap(node.label, 18)
  const sub = node.sub ? wrap(node.sub, 24).slice(0, 1) : []
  return (
    <g filter="url(#napkin-soft)">
      <rect x={x} y={y} width={w} height={h} rx={theme.sketch ? 4 : 14} fill={theme.card} stroke={color} strokeWidth={theme.sketch ? 2 : 1.5} />
      <rect x={x} y={y} width={5} height={h} rx={2.5} fill={color} />
      {num != null && (
        <circle cx={x + 20} cy={y + 20} r={11} fill={color}>
          <title>step</title>
        </circle>
      )}
      {num != null && <text x={x + 20} y={y + 24.5} textAnchor="middle" fontSize={12} fontWeight="800" fill="#fff">{num}</text>}
      <text x={x + (num != null ? 38 : 18)} y={y + 22} fontSize={theme.sketch ? 19 : 13.5} fontWeight="700" fill={theme.text}>
        {node.icon ? `${node.icon} ` : ''}{lines[0] || ''}
      </text>
      {lines.slice(1).map((ln, i) => (
        <text key={i} x={x + (num != null ? 38 : 18)} y={y + 22 + (i + 1) * 16} fontSize={theme.sketch ? 17 : 13.5} fontWeight="700" fill={theme.text}>{ln}</text>
      ))}
      {sub.map((s, i) => (
        <text key={'s' + i} x={x + (num != null ? 38 : 18)} y={y + 24 + lines.length * 16 + i * 13} fontSize={theme.sketch ? 15 : 11} fill={theme.sub}>{s}</text>
      ))}
    </g>
  )
}

function Arrow({ x1, y1, x2, y2, color }) {
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={2.5} />
      <polygon points={`0,-5 10,0 0,5`} transform={`translate(${x2},${y2}) rotate(${Math.atan2(y2 - my, x2 - mx) * 180 / Math.PI})`} fill={color} />
    </g>
  )
}

function renderBody(vtype, nodes, theme) {
  const n = nodes.length
  if (!n) return null
  const C = (i) => colorFor(theme, i)

  if (vtype === 'flowchart') {
    const bw = 320
    const bh = 58
    const gap = 26
    const total = n * bh + (n - 1) * gap
    let y = 60 + Math.max(0, (300 - total) / 2)
    const x = (W - bw) / 2
    return (
      <g>
        {nodes.map((nd, i) => (
          <g key={nd.id || i}>
            <NodeCard x={x} y={y + i * (bh + gap)} w={bw} h={bh} node={nd} color={C(i)} theme={theme} />
            {i < n - 1 && <Arrow x1={W / 2} y1={y + i * (bh + gap) + bh} x2={W / 2} y2={y + (i + 1) * (bh + gap)} color={C(i)} />}
          </g>
        ))}
      </g>
    )
  }

  if (vtype === 'steps') {
    const perRow = n > 3 ? Math.ceil(n / 2) : n
    const rows = Math.ceil(n / perRow)
    const bw = Math.min(300, (W - 60 - (perRow - 1) * 16) / perRow)
    const bh = 96
    return (
      <g>
        {nodes.map((nd, i) => {
          const r = Math.floor(i / perRow)
          const c = i % perRow
          const rowN = Math.min(perRow, n - r * perRow)
          const x0 = (W - (rowN * bw + (rowN - 1) * 16)) / 2
          const y0 = 66 + r * (bh + 30) - (rows > 1 ? 20 : 0)
          const x = x0 + c * (bw + 16)
          return (
            <g key={nd.id || i}>
              <NodeCard x={x} y={y0} w={bw} h={bh} node={nd} color={C(i)} theme={theme} num={i + 1} />
              {c < rowN - 1 && <Arrow x1={x + bw} y1={y0 + bh / 2} x2={x + bw + 16} y2={y0 + bh / 2} color={C(i)} />}
            </g>
          )
        })}
      </g>
    )
  }

  if (vtype === 'mindmap') {
    const cx = W / 2
    const cy = 230
    const R = 128
    return (
      <g>
        {nodes.slice(1).map((nd, i) => {
          const a = ((2 * Math.PI) / Math.max(n - 1, 1)) * i - Math.PI / 2
          const bx = cx + R * Math.cos(a) * 1.55
          const by = cy + R * Math.sin(a) * 0.82
          return (
            <g key={nd.id || i}>
              <line x1={cx} y1={cy} x2={bx} y2={by} stroke={C(i + 1)} strokeWidth={2} opacity={0.55} />
              <g filter="url(#napkin-soft)">
                <rect x={bx - 88} y={by - 26} width={176} height={52} rx={26} fill={theme.card} stroke={C(i + 1)} strokeWidth={1.5} />
                <text x={bx} y={by - 2} textAnchor="middle" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={C(i + 1)}>
                  {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 20)}
                </text>
                {nd.sub && <text x={bx} y={by + 14} textAnchor="middle" fontSize={10} fill={theme.sub}>{String(nd.sub).slice(0, 24)}</text>}
              </g>
            </g>
          )
        })}
        <ellipse cx={cx} cy={cy} rx={86} ry={34} fill={C(0)} filter="url(#napkin-soft)" />
        <text x={cx} y={cy - 2} textAnchor="middle" fontSize={theme.sketch ? 21 : 14} fontWeight="800" fill="#fff">
          {(nodes[0].icon ? nodes[0].icon + ' ' : '') + String(nodes[0].label).slice(0, 18)}
        </text>
        {nodes[0].sub && <text x={cx} y={cy + 15} textAnchor="middle" fontSize={10} fill="#ffffff" opacity={0.85}>{String(nodes[0].sub).slice(0, 26)}</text>}
      </g>
    )
  }

  if (vtype === 'cycle') {
    const cx = W / 2
    const cy = 235
    const R = 110
    return (
      <g>
        {nodes.map((nd, i) => {
          const a = ((2 * Math.PI) / n) * i - Math.PI / 2
          const nx = cx + R * Math.cos(a) * 1.5
          const ny = cy + R * Math.sin(a) * 0.85
          const a2 = ((2 * Math.PI) / n) * (i + 1) - Math.PI / 2
          const tx = cx + R * Math.cos(a2) * 1.5
          const ty = cy + R * Math.sin(a2) * 0.85
          return (
            <g key={nd.id || i}>
              <line x1={nx} y1={ny} x2={(nx + tx) / 2} y2={(ny + ty) / 2} stroke={C(i)} strokeWidth={2} strokeDasharray="6 4" opacity={0.7} />
              <g filter="url(#napkin-soft)">
                <rect x={nx - 80} y={ny - 26} width={160} height={52} rx={12} fill={theme.card} stroke={C(i)} strokeWidth={2} />
                <text x={nx} y={ny - 1} textAnchor="middle" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={theme.text}>
                  {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 18)}
                </text>
                {nd.sub && <text x={nx} y={ny + 15} textAnchor="middle" fontSize={10} fill={theme.sub}>{String(nd.sub).slice(0, 22)}</text>}
              </g>
            </g>
          )
        })}
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={22} opacity={0.5}>↻</text>
      </g>
    )
  }

  if (vtype === 'timeline') {
    const y0 = 225
    const x0 = 70
    const x1 = W - 70
    const step = n > 1 ? (x1 - x0) / (n - 1) : 0
    return (
      <g>
        <line x1={x0} y1={y0} x2={x1} y2={y0} stroke={theme.sub} strokeWidth={3} strokeLinecap="round" opacity={0.5} />
        {nodes.map((nd, i) => {
          const x = x0 + step * i
          const above = i % 2 === 0
          const ly = above ? y0 - 66 : y0 + 44
          return (
            <g key={nd.id || i}>
              <line x1={x} y1={y0} x2={x} y2={above ? y0 - 40 : y0 + 22} stroke={C(i)} strokeWidth={2} />
              <circle cx={x} cy={y0} r={11} fill={C(i)} stroke={theme.bg} strokeWidth={3} />
              <text x={x} y={y0 + 4.5} textAnchor="middle" fontSize={10} fontWeight="800" fill="#fff">{i + 1}</text>
              <text x={x} y={ly} textAnchor="middle" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={theme.text}>
                {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 18)}
              </text>
              {nd.sub && <text x={x} y={ly + 15} textAnchor="middle" fontSize={10} fill={theme.sub}>{String(nd.sub).slice(0, 22)}</text>}
            </g>
          )
        })}
      </g>
    )
  }

  if (vtype === 'comparison') {
    const left = nodes.filter((_, i) => i % 2 === 0).slice(0, 4)
    const right = nodes.filter((_, i) => i % 2 === 1).slice(0, 4)
    const rows = Math.max(left.length, right.length)
    const colW = 270
    const y0 = 60
    const rh = 62
    const gap = 14
    const col = (list, x, off) => (
      <g>
        {list.map((nd, i) => (
          <g key={nd.id || i}>
            <NodeCard x={x} y={y0 + i * (rh + gap)} w={colW} h={rh} node={nd} color={C(off + i * 2)} theme={theme} />
          </g>
        ))}
      </g>
    )
    return (
      <g>
        {col(left, 40, 0)}
        {col(right, W - 40 - colW, 1)}
        <line x1={W / 2} y1={y0} x2={W / 2} y2={y0 + rows * (rh + gap)} stroke={theme.line} strokeWidth={2} strokeDasharray="5 5" />
        <text x={W / 2} y={y0 + (rows * (rh + gap)) / 2} textAnchor="middle" fontSize={16} fontWeight="800" fill={theme.bg}
          stroke={theme.sub} strokeWidth={3} paintOrder="stroke">VS</text>
        <text x={W / 2} y={y0 + (rows * (rh + gap)) / 2} textAnchor="middle" fontSize={16} fontWeight="800" fill={theme.sub}>VS</text>
      </g>
    )
  }

  if (vtype === 'pyramid') {
    const levels = Math.min(n, 6)
    const topW = 180
    const botW = 460
    const y0 = 62
    const lh = Math.min(52, 300 / levels)
    return (
      <g>
        {nodes.slice(0, levels).map((nd, i) => {
          const wTop = topW + ((botW - topW) * i) / levels
          const wBot = topW + ((botW - topW) * (i + 1)) / levels
          const y = y0 + i * (lh + 6)
          const cx = W / 2
          return (
            <g key={nd.id || i} filter="url(#napkin-soft)">
              <polygon points={`${cx - wTop / 2},${y} ${cx + wTop / 2},${y} ${cx + wBot / 2},${y + lh} ${cx - wBot / 2},${y + lh}`}
                fill={C(i)} opacity={0.88} stroke={theme.bg} strokeWidth={2} />
              <text x={cx} y={y + lh / 2 + 5} textAnchor="middle" fontSize={theme.sketch ? 19 : 13} fontWeight="700" fill="#fff">
                {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 26)}
              </text>
            </g>
          )
        })}
      </g>
    )
  }

  if (vtype === 'venn') {
    const two = nodes.slice(0, 2)
    const extra = nodes.slice(2, 5)
    const cy = 230
    const r = 105
    const cx1 = W / 2 - (n > 2 ? 95 : 80)
    const cx2 = W / 2 + (n > 2 ? 95 : 80)
    return (
      <g>
        <circle cx={cx1} cy={cy} r={r} fill={C(0)} opacity={0.45} stroke={C(0)} strokeWidth={2.5} />
        <circle cx={cx2} cy={cy} r={r} fill={C(1)} opacity={0.45} stroke={C(1)} strokeWidth={2.5} />
        {two[0] && (
          <g>
            <text x={cx1 - 48} y={cy - 2} textAnchor="middle" fontSize={theme.sketch ? 20 : 13.5} fontWeight="800" fill={theme.text}>
              {two[0].icon ? `${two[0].icon} ` : ''}{String(two[0].label).slice(0, 16)}
            </text>
            {two[0].sub && <text x={cx1 - 48} y={cy + 15} textAnchor="middle" fontSize={10.5} fill={theme.sub}>{String(two[0].sub).slice(0, 20)}</text>}
          </g>
        )}
        {two[1] && (
          <g>
            <text x={cx2 + 48} y={cy - 2} textAnchor="middle" fontSize={theme.sketch ? 20 : 13.5} fontWeight="800" fill={theme.text}>
              {two[1].icon ? `${two[1].icon} ` : ''}{String(two[1].label).slice(0, 16)}
            </text>
            {two[1].sub && <text x={cx2 + 48} y={cy + 15} textAnchor="middle" fontSize={10.5} fill={theme.sub}>{String(two[1].sub).slice(0, 20)}</text>}
          </g>
        )}
        {extra.map((nd, i) => (
          <text key={nd.id || i} x={W / 2} y={cy - 8 + i * 17} textAnchor="middle" fontSize={theme.sketch ? 17 : 11.5} fontWeight="700" fill={theme.text}>
            {nd.icon ? `${nd.icon} ` : '∩ '}{String(nd.label).slice(0, 20)}
          </text>
        ))}
        {n > 2 && <text x={W / 2} y={cy + 92} textAnchor="middle" fontSize={11} fill={theme.sub}>shared in the middle</text>}
      </g>
    )
  }

  if (vtype === 'pie') {
    const vals = nodes.map(nd => numFrom(nd.label + ' ' + (nd.sub || ''), 1))
    const total = vals.reduce((a, b) => a + b, 0) || 1
    const cx = 250
    const cy = 235
    const r = 105
    let acc = -Math.PI / 2
    const slices = vals.map((v, i) => {
      const a0 = acc
      acc += (v / total) * Math.PI * 2
      return { a0, a1: acc, i }
    })
    const pt = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)]
    return (
      <g>
        {slices.map(({ a0, a1, i }) => {
          const [x0, y0] = pt(a0)
          const [x1, y1] = pt(a1)
          const large = a1 - a0 > Math.PI ? 1 : 0
          const mid = (a0 + a1) / 2
          const pct = Math.round((vals[i] / total) * 100)
          return (
            <g key={nodes[i].id || i}>
              <path d={`M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} Z`}
                fill={C(i)} stroke={theme.bg} strokeWidth={2.5} opacity={0.9} />
              <text x={cx + (r * 0.62) * Math.cos(mid)} y={cy + (r * 0.62) * Math.sin(mid) + 4}
                textAnchor="middle" fontSize={12} fontWeight="800" fill="#fff">{pct}%</text>
            </g>
          )
        })}
        {nodes.map((nd, i) => (
          <g key={'l' + (nd.id || i)}>
            <rect x={390} y={110 + i * 30} width={13} height={13} rx={3.5} fill={C(i)} />
            <text x={410} y={121 + i * 30} fontSize={12.5} fontWeight="600" fill={theme.text}>
              {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 22)}
            </text>
          </g>
        ))}
      </g>
    )
  }

  // bar (default fallback)
  const vals = nodes.map(nd => numFrom(nd.label + ' ' + (nd.sub || ''), 0))
  const maxV = Math.max(...vals, 1)
  const hasNums = vals.some(v => v > 0)
  const bw = 360
  const x0 = 190
  return (
    <g>
      {nodes.map((nd, i) => {
        const frac = hasNums ? vals[i] / maxV : (n - i * 0.4) / n
        const y = 72 + i * 52
        return (
          <g key={nd.id || i}>
            <text x={x0 - 10} y={y + 15} textAnchor="end" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={theme.text}>
              {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).replace(/\d+(\.\d+)?\s*%?/, '').trim().slice(0, 16) || nd.label}
            </text>
            <rect x={x0} y={y} width={bw} height={22} rx={11} fill={theme.line} opacity={0.5} />
            <rect x={x0} y={y} width={Math.max(24, bw * frac)} height={22} rx={11} fill={C(i)} />
            {hasNums && vals[i] > 0 && (
              <text x={x0 + Math.max(24, bw * frac) + 8} y={y + 15} fontSize={11.5} fontWeight="700" fill={theme.sub}>{vals[i]}</text>
            )}
          </g>
        )
      })}
    </g>
  )
}
