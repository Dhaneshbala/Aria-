import { forwardRef, useRef, useState, useCallback } from 'react'
import { Download, ZoomIn, ZoomOut, Maximize2, RotateCcw } from 'lucide-react'

/**
 * MindMapWidget — upgraded with collapsible nodes, zoom/pan, PNG export, radial layout.
 */

const COLORS = [
  '#7c6af7', '#4ade80', '#60a5fa', '#f59e0b',
  '#f87171', '#a78bfa', '#34d399', '#fb923c',
]

export default function MindMapWidget({ data, compact = false, showDownload = true }) {
  const svgRef = useRef()
  const [collapsed, setCollapsed] = useState({})
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [layout, setLayout] = useState('radial') // 'radial' | 'tree'
  const [dragging, setDragging] = useState(false)
  const dragStart = useRef(null)

  if (!data) return null

  const branches = data.branches || []
  const W = compact ? 600 : 900
  const H = compact ? 400 : 600
  const cx = W / 2
  const cy = H / 2

  const toggleCollapse = (idx) => {
    setCollapsed(c => ({ ...c, [idx]: !c[idx] }))
  }

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }) }

  // Mouse drag for panning
  const onMouseDown = (e) => {
    if (e.target.closest('button')) return
    setDragging(true)
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
  }
  const onMouseMove = (e) => {
    if (!dragging || !dragStart.current) return
    setPan({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y })
  }
  const onMouseUp = () => { setDragging(false); dragStart.current = null }

  const downloadSVG = () => {
    if (!svgRef.current) return
    const svg = svgRef.current.outerHTML
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mindmap-${data.center || 'aria'}.svg`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const downloadPNG = () => {
    if (!svgRef.current) return
    const svgEl = svgRef.current
    const svgData = new XMLSerializer().serializeToString(svgEl)
    const canvas = document.createElement('canvas')
    const scale = 2
    canvas.width = W * scale
    canvas.height = H * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)

    const img = new Image()
    img.onload = () => {
      ctx.fillStyle = '#0a0a0a'
      ctx.fillRect(0, 0, W, H)
      ctx.drawImage(img, 0, 0, W, H)
      canvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `mindmap-${data.center || 'aria'}.png`
        a.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      })
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)))
  }

  return (
    <div className="w-full">
      {showDownload && (
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <button onClick={() => setLayout(l => l === 'radial' ? 'tree' : 'radial')}
              className="text-xs text-[#555] hover:text-[#aaa] px-2 py-1 rounded-lg hover:bg-[#1a1a1a] transition-colors">
              {layout === 'radial' ? '🌳 Tree' : '🔄 Radial'}
            </button>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setZoom(z => Math.min(z + 0.2, 3))}
              className="p-1 rounded text-[#555] hover:text-[#aaa] hover:bg-[#1a1a1a] transition-colors">
              <ZoomIn size={14} />
            </button>
            <button onClick={() => setZoom(z => Math.max(z - 0.2, 0.4))}
              className="p-1 rounded text-[#555] hover:text-[#aaa] hover:bg-[#1a1a1a] transition-colors">
              <ZoomOut size={14} />
            </button>
            <button onClick={resetView}
              className="p-1 rounded text-[#555] hover:text-[#aaa] hover:bg-[#1a1a1a] transition-colors">
              <Maximize2 size={14} />
            </button>
            <div className="w-px h-4 bg-[#2a2a2a] mx-1" />
            <button onClick={downloadSVG}
              className="flex items-center gap-1 text-xs text-[#555] hover:text-[#aaa] px-2 py-1 rounded-lg hover:bg-[#1a1a1a] transition-colors">
              <Download size={12} /> SVG
            </button>
            <button onClick={downloadPNG}
              className="flex items-center gap-1 text-xs text-[#555] hover:text-[#aaa] px-2 py-1 rounded-lg hover:bg-[#1a1a1a] transition-colors">
              <Download size={12} /> PNG
            </button>
          </div>
        </div>
      )}

      <div
        className="overflow-hidden rounded-2xl border border-[#2a2a2a] cursor-grab active:cursor-grabbing"
        style={{ background: '#0a0a0a' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <div style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: dragging ? 'none' : 'transform 0.15s ease-out',
        }}>
          <MindMapSVG ref={svgRef} data={data} W={W} H={H} cx={cx} cy={cy}
            layout={layout} collapsed={collapsed} toggleCollapse={toggleCollapse} compact={compact} />
        </div>
      </div>
    </div>
  )
}

const MindMapSVG = forwardRef(function MindMapSVG(
  { data, W, H, cx, cy, layout, collapsed, toggleCollapse, compact }, ref
) {
  const branches = data.branches || []
  const fontSize = compact ? 9 : 11
  const centerFontSize = compact ? 11 : 14
  const nodeW = compact ? 90 : 120
  const nodeH = compact ? 24 : 30
  const branchR = compact ? 130 : 190
  const childR = compact ? 220 : 310

  if (layout === 'tree') {
    return <TreeView ref={ref} data={data} W={W} H={H} branches={branches}
      fontSize={fontSize} centerFontSize={centerFontSize} nodeW={nodeW} nodeH={nodeH}
      collapsed={collapsed} toggleCollapse={toggleCollapse} compact={compact} />
  }

  // Radial layout
  const angleStep = branches.length > 0 ? (2 * Math.PI) / branches.length : 1

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ fontFamily: 'Inter, sans-serif' }}
    >
      <defs>
        {branches.map((_, bi) => (
          <radialGradient key={bi} id={`bg${bi}`} cx="50%" cy="50%">
            <stop offset="0%" stopColor={COLORS[bi % COLORS.length]} stopOpacity="0.25" />
            <stop offset="100%" stopColor={COLORS[bi % COLORS.length]} stopOpacity="0.05" />
          </radialGradient>
        ))}
        <radialGradient id="centerGrad" cx="50%" cy="50%">
          <stop offset="0%" stopColor="#7c6af7" />
          <stop offset="100%" stopColor="#4f46e5" />
        </radialGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {branches.map((branch, bi) => {
        const angle = angleStep * bi - Math.PI / 2
        const bx = cx + branchR * Math.cos(angle)
        const by = cy + branchR * Math.sin(angle)
        const color = COLORS[bi % COLORS.length]
        const children = branch.children || []
        const isCollapsed = collapsed[bi]
        const childSpread = Math.min(Math.PI / 2.5, (children.length * Math.PI) / 8)
        const childStart = angle - childSpread / 2

        return (
          <g key={bi}>
            {/* Spoke: center → branch */}
            <line x1={cx} y1={cy} x2={bx} y2={by}
              stroke={color} strokeWidth="1.5" opacity="0.4" />

            {/* Branch node */}
            <rect
              x={bx - nodeW / 2} y={by - nodeH / 2}
              width={nodeW} height={nodeH} rx={nodeH / 2}
              fill={`url(#bg${bi})`} stroke={color} strokeWidth="1" opacity="0.9"
              style={{ cursor: children.length > 0 ? 'pointer' : 'default' }}
              onClick={() => children.length > 0 && toggleCollapse(bi)}
            />
            <text x={bx} y={by + fontSize * 0.4}
              textAnchor="middle" fill={color} fontSize={fontSize} fontWeight="600"
              style={{ pointerEvents: 'none' }}
            >
              {truncate(branch.label, compact ? 12 : 16)}
            </text>

            {/* Collapse indicator */}
            {children.length > 0 && (
              <text x={bx + nodeW / 2 + 8} y={by + fontSize * 0.3}
                fill={color} fontSize={10} opacity="0.6"
                style={{ pointerEvents: 'none' }}
              >
                {isCollapsed ? `+${children.length}` : '−'}
              </text>
            )}

            {/* Children (if not collapsed) */}
            {!isCollapsed && children.map((child, ci) => {
              const childAngle = children.length === 1
                ? angle
                : childStart + (childSpread / Math.max(children.length - 1, 1)) * ci
              const chx = cx + childR * Math.cos(childAngle)
              const chy = cy + childR * Math.sin(childAngle)

              return (
                <g key={ci}>
                  <line x1={bx} y1={by} x2={chx} y2={chy}
                    stroke={color} strokeWidth="1" opacity="0.2" strokeDasharray="3,3" />
                  <circle cx={chx} cy={chy} r={3} fill={color} opacity="0.5" />
                  <text x={chx} y={chy - (fontSize + 1)}
                    textAnchor="middle" fill="#666" fontSize={fontSize - 1}
                  >
                    {truncate(String(child), compact ? 14 : 18)}
                  </text>
                </g>
              )
            })}
          </g>
        )
      })}

      {/* Center node */}
      <ellipse cx={cx} cy={cy} rx={compact ? 55 : 70} ry={compact ? 22 : 28}
        fill="url(#centerGrad)" filter="url(#glow)" />
      <text x={cx} y={cy + centerFontSize * 0.35}
        textAnchor="middle" fill="white" fontSize={centerFontSize} fontWeight="700"
      >
        {truncate(data.center || '', compact ? 12 : 16)}
      </text>
    </svg>
  )
})

const TreeView = forwardRef(function TreeView(
  { ref, data, W, H, branches, fontSize, centerFontSize, nodeW, nodeH, collapsed, toggleCollapse, compact }, _
) {
  const treeW = W
  const treeH = H
  const centerX = 80
  const centerY = treeH / 2
  const levelGap = (treeW - 160) / 3
  const color = '#7c6af7'

  return (
    <svg ref={ref} viewBox={`0 0 ${treeW} ${treeH}`}
      className="w-full" style={{ fontFamily: 'Inter, sans-serif' }}>
      <defs>
        <linearGradient id="treeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#7c6af7" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
      </defs>

      {/* Center node */}
      <rect x={centerX - 50} y={centerY - 18} width={100} height={36} rx={18}
        fill="url(#treeGrad)" />
      <text x={centerX} y={centerY + centerFontSize * 0.35}
        textAnchor="middle" fill="white" fontSize={centerFontSize} fontWeight="700"
      >
        {truncate(data.center || '', 12)}
      </text>

      {/* Branches going right */}
      {branches.map((branch, bi) => {
        const branchY = 40 + ((treeH - 80) / Math.max(branches.length, 1)) * (bi + 0.5)
        const bx = centerX + levelGap
        const isCollapsed = collapsed[bi]
        const ch = branch.children || []
        const branchColor = COLORS[bi % COLORS.length]

        return (
          <g key={bi}>
            {/* Connection line */}
            <path d={`M${centerX + 50} ${centerY} C${centerX + levelGap / 2} ${centerY}, ${bx - levelGap / 2} ${branchY}, ${bx} ${branchY}`}
              fill="none" stroke={branchColor} strokeWidth="1.5" opacity="0.4" />

            {/* Branch node */}
            <rect x={bx - nodeW / 2} y={branchY - nodeH / 2}
              width={nodeW} height={nodeH} rx={nodeH / 2}
              fill={`${branchColor}20`} stroke={branchColor} strokeWidth="1"
              style={{ cursor: ch.length > 0 ? 'pointer' : 'default' }}
              onClick={() => ch.length > 0 && toggleCollapse(bi)}
            />
            <text x={bx} y={branchY + fontSize * 0.4}
              textAnchor="middle" fill={branchColor} fontSize={fontSize} fontWeight="600"
              style={{ pointerEvents: 'none' }}
            >
              {truncate(branch.label, 14)}
            </text>

            {ch.length > 0 && (
              <text x={bx + nodeW / 2 + 6} y={branchY + fontSize * 0.3}
                fill={branchColor} fontSize={9} opacity="0.6"
                style={{ pointerEvents: 'none' }}
              >
                {isCollapsed ? `+${ch.length}` : '−'}
              </text>
            )}

            {/* Children */}
            {!isCollapsed && ch.map((child, ci) => {
              const childY = branchY + ((ci - (ch.length - 1) / 2) * 28)
              const chx = bx + levelGap * 0.7

              return (
                <g key={ci}>
                  <line x1={bx + nodeW / 2} y1={branchY} x2={chx - 50} y2={childY}
                    stroke={branchColor} strokeWidth="1" opacity="0.2" strokeDasharray="3,3" />
                  <rect x={chx - 50} y={childY - 12} width={100} height={24} rx={12}
                    fill="#1a1a1a" stroke={`${branchColor}40`} strokeWidth="1" />
                  <text x={chx} y={childY + fontSize * 0.35}
                    textAnchor="middle" fill="#888" fontSize={fontSize - 1}
                  >
                    {truncate(String(child), 16)}
                  </text>
                </g>
              )
            })}
          </g>
        )
      })}
    </svg>
  )
})

function truncate(str, max) {
  if (!str) return ''
  return str.length > max ? str.slice(0, max - 1) + '…' : str
}
