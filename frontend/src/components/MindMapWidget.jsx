import { forwardRef, useRef } from 'react'
import { Download } from 'lucide-react'

/**
 * MindMapWidget — standalone, reusable SVG mind map.
 * Used in:
 *   - MindMapPage (full-page)
 *   - Message.jsx (inline in chat when orchestrator returns a mind map)
 */

const COLORS = [
  '#7c6af7', '#4ade80', '#60a5fa', '#f59e0b',
  '#f87171', '#a78bfa', '#34d399', '#fb923c',
]

export default function MindMapWidget({ data, compact = false, showDownload = true }) {
  const svgRef = useRef()

  if (!data) return null

  const branches = data.branches || []
  const W = compact ? 600 : 900
  const H = compact ? 400 : 600
  const cx = W / 2
  const cy = H / 2
  const branchR = compact ? 130 : 190
  const childR = compact ? 220 : 310
  const angleStep = branches.length > 0 ? (2 * Math.PI) / branches.length : 1

  const downloadSVG = () => {
    if (!svgRef.current) return
    const svg = svgRef.current.outerHTML
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `mindmap-${data.center || 'aria'}.svg`
    a.click()
  }

  return (
    <div className="w-full">
      {showDownload && (
        <div className="flex justify-end mb-2">
          <button
            onClick={downloadSVG}
            className="flex items-center gap-1.5 text-xs text-[#555] hover:text-[#aaa] px-2 py-1 rounded-lg hover:bg-[#1a1a1a] transition-colors"
          >
            <Download size={12} /> Download SVG
          </button>
        </div>
      )}

      <MindMapSVG ref={svgRef} data={data} W={W} H={H} cx={cx} cy={cy}
        branchR={branchR} childR={childR} angleStep={angleStep} compact={compact} />
    </div>
  )
}

const MindMapSVG = forwardRef(function MindMapSVG(
  { data, W, H, cx, cy, branchR, childR, angleStep, compact }, ref
) {
  const branches = data.branches || []
  const fontSize = compact ? 9 : 11
  const centerFontSize = compact ? 11 : 14
  const nodeW = compact ? 90 : 120
  const nodeH = compact ? 24 : 30

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full rounded-2xl border border-[#2a2a2a]"
      style={{ background: '#0a0a0a', fontFamily: 'Inter, sans-serif' }}
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

      {/* Branch connections and nodes */}
      {branches.map((branch, bi) => {
        const angle = angleStep * bi - Math.PI / 2
        const bx = cx + branchR * Math.cos(angle)
        const by = cy + branchR * Math.sin(angle)
        const color = COLORS[bi % COLORS.length]
        const children = branch.children || []
        const childSpread = Math.min(Math.PI / 2.5, (children.length * Math.PI) / 8)
        const childStart = angle - childSpread / 2

        return (
          <g key={bi}>
            {/* Spoke: center → branch */}
            <line
              x1={cx} y1={cy} x2={bx} y2={by}
              stroke={color} strokeWidth="1.5" opacity="0.4"
            />

            {/* Branch node background */}
            <rect
              x={bx - nodeW / 2} y={by - nodeH / 2}
              width={nodeW} height={nodeH}
              rx={nodeH / 2}
              fill={`url(#bg${bi})`}
              stroke={color} strokeWidth="1" opacity="0.9"
            />
            <text x={bx} y={by + fontSize * 0.4}
              textAnchor="middle" fill={color}
              fontSize={fontSize} fontWeight="600"
            >
              {truncate(branch.label, compact ? 12 : 16)}
            </text>

            {/* Children */}
            {children.map((child, ci) => {
              const childAngle = children.length === 1
                ? angle
                : childStart + (childSpread / Math.max(children.length - 1, 1)) * ci
              const chx = cx + childR * Math.cos(childAngle)
              const chy = cy + childR * Math.sin(childAngle)

              return (
                <g key={ci}>
                  {/* Spoke: branch → child */}
                  <line
                    x1={bx} y1={by} x2={chx} y2={chy}
                    stroke={color} strokeWidth="1" opacity="0.2"
                    strokeDasharray="3,3"
                  />
                  {/* Child dot */}
                  <circle cx={chx} cy={chy} r={3} fill={color} opacity="0.5" />
                  {/* Child label */}
                  <text
                    x={chx} y={chy - (fontSize + 1)}
                    textAnchor="middle" fill="#666"
                    fontSize={fontSize - 1}
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
        textAnchor="middle" fill="white"
        fontSize={centerFontSize} fontWeight="700"
      >
        {truncate(data.center || '', compact ? 12 : 16)}
      </text>
    </svg>
  )
})

function truncate(str, max) {
  if (!str) return ''
  return str.length > max ? str.slice(0, max - 1) + '…' : str
}
