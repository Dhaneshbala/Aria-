/**
 * NapkinDiagram layout engine — one renderer per visual type.
 * Extracted from NapkinDiagram.jsx. Pure rendering; no state.
 * NOTE: StraightArrow was dead code (only CurvedArrow is used) — removed.
 */
import { W, barLabel, colorFor, hexToRgba, numFrom, wrap } from './diagramUtils'

export function NodeCard({ x, y, w, h, node, color, theme, num, uid }) {
  const lines = wrap(node.label, 18)
  const sub = node.sub ? wrap(node.sub, 24).slice(0, 1) : []
  const gradId = `ng-${uid}-${node.id || num || 0}`
  return (
    <g filter={`url(#napkin-soft-${uid})`}>
      {/* Gradient background */}
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.08" />
          <stop offset="100%" stopColor={color} stopOpacity="0.03" />
        </linearGradient>
      </defs>
      <rect x={x} y={y} width={w} height={h} rx={theme.sketch ? 4 : 14} fill={theme.card} stroke={color} strokeWidth={theme.sketch ? 2 : 1.5} />
      <rect x={x} y={y} width={w} height={h} rx={theme.sketch ? 4 : 14} fill={`url(#${gradId})`} />
      {/* Left accent bar */}
      <rect x={x} y={y + 4} width={4} height={h - 8} rx={2} fill={color} />
      {num != null && (
        <circle cx={x + 22} cy={y + h / 2} r={12} fill={color}>
          <animate attributeName="r" values="12;13;12" dur="2s" repeatCount="indefinite" />
        </circle>
      )}
      {num != null && <text x={x + 22} y={y + h / 2 + 4.5} textAnchor="middle" fontSize={11} fontWeight="800" fill="#fff">{num}</text>}
      <text x={x + (num != null ? 42 : 20)} y={y + 22} fontSize={theme.sketch ? 19 : 13.5} fontWeight="700" fill={theme.text}>
        {node.icon ? `${node.icon} ` : ''}{lines[0] || ''}
      </text>
      {lines.slice(1).map((ln, i) => (
        <text key={i} x={x + (num != null ? 42 : 20)} y={y + 22 + (i + 1) * 16} fontSize={theme.sketch ? 17 : 13.5} fontWeight="700" fill={theme.text}>{ln}</text>
      ))}
      {sub.map((s, i) => (
        <text key={'s' + i} x={x + (num != null ? 42 : 20)} y={y + 24 + lines.length * 16 + i * 13} fontSize={theme.sketch ? 15 : 11} fill={theme.sub}>{s}</text>
      ))}
    </g>
  )
}

export function CurvedArrow({ x1, y1, x2, y2, color }) {
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const dx = x2 - x1
  const dy = y2 - y1
  // Curve offset for visual interest
  const cx = mx + dy * 0.15
  const cy = my - dx * 0.15
  return (
    <g>
      <path
        d={`M${x1},${y1} Q${cx},${cy} ${x2},${y2}`}
        fill="none" stroke={color} strokeWidth={2} opacity={0.6}
        strokeLinecap="round"
      />
      <polygon
        points="0,-4 8,0 0,4"
        transform={`translate(${x2},${y2}) rotate(${Math.atan2(y2 - cy, x2 - cx) * 180 / Math.PI})`}
        fill={color} opacity={0.8}
      />
    </g>
  )
}

export function renderBody(vtype, nodes, theme, uid = 'x') {
  const n = nodes.length
  if (!n) return null
  const C = (i) => colorFor(theme, i)
  const soft = `url(#napkin-soft-${uid})`

  if (vtype === 'flowchart') {
    const bw = 320
    const bh = 58
    const gap = 28
    const total = n * bh + (n - 1) * gap
    let y = 60 + Math.max(0, (300 - total) / 2)
    const x = (W - bw) / 2
    return (
      <g>
        {nodes.map((nd, i) => (
          <g key={nd.id || i}>
            <NodeCard x={x} y={y + i * (bh + gap)} w={bw} h={bh} node={nd} color={C(i)} theme={theme} uid={uid} />
            {i < n - 1 && <CurvedArrow x1={W / 2} y1={y + i * (bh + gap) + bh} x2={W / 2} y2={y + (i + 1) * (bh + gap)} color={C(i)} />}
          </g>
        ))}
      </g>
    )
  }

  if (vtype === 'steps') {
    const perRow = n > 3 ? Math.ceil(n / 2) : n
    const rows = Math.ceil(n / perRow)
    const bw = Math.min(280, (W - 60 - (perRow - 1) * 20) / perRow)
    const bh = 100
    return (
      <g>
        {nodes.map((nd, i) => {
          const r = Math.floor(i / perRow)
          const c = i % perRow
          const rowN = Math.min(perRow, n - r * perRow)
          const x0 = (W - (rowN * bw + (rowN - 1) * 20)) / 2
          const y0 = 66 + r * (bh + 36) - (rows > 1 ? 20 : 0)
          const x = x0 + c * (bw + 20)
          return (
            <g key={nd.id || i}>
              <NodeCard x={x} y={y0} w={bw} h={bh} node={nd} color={C(i)} theme={theme} num={i + 1} uid={uid} />
              {c < rowN - 1 && <CurvedArrow x1={x + bw} y1={y0 + bh / 2} x2={x + bw + 20} y2={y0 + bh / 2} color={C(i)} />}
            </g>
          )
        })}
      </g>
    )
  }

  if (vtype === 'mindmap') {
    const cx = W / 2
    const cy = 230
    const R = 130
    return (
      <g>
        {nodes.slice(1).map((nd, i) => {
          const a = ((2 * Math.PI) / Math.max(n - 1, 1)) * i - Math.PI / 2
          const bx = cx + R * Math.cos(a) * 1.55
          const by = cy + R * Math.sin(a) * 0.82
          const branchColor = C(i + 1)
          return (
            <g key={nd.id || i}>
              {/* Curved branch */}
              <path
                d={`M${cx},${cy} Q${cx + (bx - cx) * 0.5},${cy} ${bx},${by}`}
                fill="none" stroke={branchColor} strokeWidth={2.5} opacity={0.4}
                strokeLinecap="round"
              />
              <g filter={soft}>
                <rect x={bx - 90} y={by - 28} width={180} height={56} rx={28} fill={theme.card} stroke={branchColor} strokeWidth={1.5} />
                <rect x={bx - 90} y={by - 28} width={180} height={56} rx={28} fill={hexToRgba(branchColor, 0.06)} />
                <text x={bx} y={by - 2} textAnchor="middle" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={branchColor}>
                  {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 20)}
                </text>
                {nd.sub && <text x={bx} y={by + 14} textAnchor="middle" fontSize={10} fill={theme.sub}>{String(nd.sub).slice(0, 24)}</text>}
              </g>
            </g>
          )
        })}
        <ellipse cx={cx} cy={cy} rx={88} ry={36} fill={C(0)} filter={soft} />
        <ellipse cx={cx} cy={cy} rx={88} ry={36} fill={`url(#napkin-grad-0-${uid})`} />
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
        {/* Circular track */}
        <ellipse cx={cx} cy={cy} rx={R * 1.5} ry={R * 0.85} fill="none" stroke={theme.line} strokeWidth={1} strokeDasharray="4 4" opacity={0.3} />
        {nodes.map((nd, i) => {
          const a = ((2 * Math.PI) / n) * i - Math.PI / 2
          const nx = cx + R * Math.cos(a) * 1.5
          const ny = cy + R * Math.sin(a) * 0.85
          const a2 = ((2 * Math.PI) / n) * (i + 1) - Math.PI / 2
          const tx = cx + R * Math.cos(a2) * 1.5
          const ty = cy + R * Math.sin(a2) * 0.85
          return (
            <g key={nd.id || i}>
              <CurvedArrow x1={nx} y1={ny} x2={(nx + tx) / 2} y2={(ny + ty) / 2} color={C(i)} />
              <g filter={soft}>
                <rect x={nx - 82} y={ny - 28} width={164} height={56} rx={14} fill={theme.card} stroke={C(i)} strokeWidth={2} />
                <rect x={nx - 82} y={ny - 28} width={164} height={56} rx={14} fill={hexToRgba(C(i), 0.06)} />
                <text x={nx} y={ny - 1} textAnchor="middle" fontSize={theme.sketch ? 18 : 12.5} fontWeight="700" fill={theme.text}>
                  {nd.icon ? `${nd.icon} ` : ''}{String(nd.label).slice(0, 18)}
                </text>
                {nd.sub && <text x={nx} y={ny + 15} textAnchor="middle" fontSize={10} fill={theme.sub}>{String(nd.sub).slice(0, 22)}</text>}
              </g>
            </g>
          )
        })}
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={22} opacity={0.4}>↻</text>
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
        <line x1={x0} y1={y0} x2={x1} y2={y0} stroke={theme.sub} strokeWidth={3} strokeLinecap="round" opacity={0.4} />
        {nodes.map((nd, i) => {
          const x = x0 + step * i
          const above = i % 2 === 0
          const ly = above ? y0 - 68 : y0 + 46
          return (
            <g key={nd.id || i}>
              <line x1={x} y1={y0} x2={x} y2={above ? y0 - 42 : y0 + 24} stroke={C(i)} strokeWidth={2} opacity={0.5} />
              <circle cx={x} cy={y0} r={12} fill={C(i)} stroke={theme.bg} strokeWidth={3}>
                <animate attributeName="r" values="12;13;12" dur="2s" repeatCount="indefinite" begin={`${i * 0.3}s`} />
              </circle>
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
    const rh = 64
    const gap = 16
    const col = (list, x, off) => (
      <g>
        {list.map((nd, i) => (
          <g key={nd.id || i}>
            <NodeCard x={x} y={y0 + i * (rh + gap)} w={colW} h={rh} node={nd} color={C(off + i * 2)} theme={theme} uid={uid} />
          </g>
        ))}
      </g>
    )
    return (
      <g>
        {col(left, 40, 0)}
        {col(right, W - 40 - colW, 1)}
        <line x1={W / 2} y1={y0} x2={W / 2} y2={y0 + rows * (rh + gap)} stroke={theme.line} strokeWidth={2} strokeDasharray="5 5" opacity={0.5} />
        <rect x={W / 2 - 18} y={y0 + (rows * (rh + gap)) / 2 - 14} width={36} height={28} rx={14} fill={theme.card} stroke={theme.sub} strokeWidth={1.5} />
        <text x={W / 2} y={y0 + (rows * (rh + gap)) / 2 + 5} textAnchor="middle" fontSize={14} fontWeight="800" fill={theme.sub}>VS</text>
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
            <g key={nd.id || i} filter={soft}>
              <polygon points={`${cx - wTop / 2},${y} ${cx + wTop / 2},${y} ${cx + wBot / 2},${y + lh} ${cx - wBot / 2},${y + lh}`}
                fill={C(i)} opacity={0.9} stroke={theme.bg} strokeWidth={2} />
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
    const cy = 230
    const r = 105
    // 3-circle layout when 3+ sets (e.g. soccer/tennis/swimming); else 2-circle.
    if (n >= 3) {
      const cx = W / 2
      const cyT = 175
      const cyB = 275
      const circles = [
        { x: cx - 80, y: cyB, c: C(0), nd: nodes[0] },
        { x: cx + 80, y: cyB, c: C(1), nd: nodes[1] },
        { x: cx, y: cyT, c: C(2), nd: nodes[2] },
      ]
      const shared = nodes.slice(3, 6)
      return (
        <g>
          {circles.map((cc, i) => (
            <circle key={i} cx={cc.x} cy={cc.y} r={r} fill={cc.c} opacity={0.32} stroke={cc.c} strokeWidth={2.5} />
          ))}
          {circles.map((cc, i) => (
            <g key={'t' + i}>
              <text x={cc.x} y={cc.y - (i === 2 ? 52 : 42)} textAnchor="middle" fontSize={theme.sketch ? 20 : 13.5} fontWeight="800" fill={theme.text}>
                {cc.nd.icon ? `${cc.nd.icon} ` : ''}{wrap(cc.nd.label, 16)[0] || ''}
              </text>
              {wrap(cc.nd.label, 16)[1] && <text x={cc.x} y={cc.y - (i === 2 ? 38 : 28)} textAnchor="middle" fontSize={12} fontWeight="700" fill={theme.text}>{wrap(cc.nd.label, 16)[1]}</text>}
            </g>
          ))}
          {shared.map((nd, i) => (
            <text key={nd.id || i} x={cx} y={cyB - 8 + i * 16} textAnchor="middle" fontSize={11.5} fontWeight="700" fill={theme.text}>
              {nd.icon ? `${nd.icon} ` : '∩ '}{String(nd.label).slice(0, 22)}
            </text>
          ))}
          <text x={cx} y={cyB + 92} textAnchor="middle" fontSize={11} fill={theme.sub}>shared in the middle</text>
        </g>
      )
    }
    const two = nodes.slice(0, 2)
    const extra = nodes.slice(2, 5)
    const cx1 = W / 2 - (n > 2 ? 95 : 80)
    const cx2 = W / 2 + (n > 2 ? 95 : 80)
    return (
      <g>
        <circle cx={cx1} cy={cy} r={r} fill={C(0)} opacity={0.35} stroke={C(0)} strokeWidth={2.5} />
        <circle cx={cx2} cy={cy} r={r} fill={C(1)} opacity={0.35} stroke={C(1)} strokeWidth={2.5} />
        {two[0] && (
          <g>
            {wrap(two[0].label, 14).slice(0, 2).map((ln, li) => (
              <text key={li} x={cx1 - 48} y={cy - 2 + li * 15} textAnchor="middle" fontSize={theme.sketch ? 20 : 13.5} fontWeight="800" fill={theme.text}>
                {li === 0 && two[0].icon ? `${two[0].icon} ` : ''}{ln}
              </text>
            ))}
            {two[0].sub && <text x={cx1 - 48} y={cy + 30} textAnchor="middle" fontSize={10.5} fill={theme.sub}>{String(two[0].sub).slice(0, 20)}</text>}
          </g>
        )}
        {two[1] && (
          <g>
            {wrap(two[1].label, 14).slice(0, 2).map((ln, li) => (
              <text key={li} x={cx2 + 48} y={cy - 2 + li * 15} textAnchor="middle" fontSize={theme.sketch ? 20 : 13.5} fontWeight="800" fill={theme.text}>
                {li === 0 && two[1].icon ? `${two[1].icon} ` : ''}{ln}
              </text>
            ))}
            {two[1].sub && <text x={cx2 + 48} y={cy + 30} textAnchor="middle" fontSize={10.5} fill={theme.sub}>{String(two[1].sub).slice(0, 20)}</text>}
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
              {pct > 5 && (
                <text x={cx + (r * 0.62) * Math.cos(mid)} y={cy + (r * 0.62) * Math.sin(mid) + 4}
                  textAnchor="middle" fontSize={12} fontWeight="800" fill="#fff">{pct}%</text>
              )}
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
              {nd.icon ? `${nd.icon} ` : ''}{barLabel(nd.label)}
            </text>
            <rect x={x0} y={y} width={bw} height={22} rx={11} fill={theme.line} opacity={0.4} />
            <rect x={x0} y={y} width={Math.max(24, bw * frac)} height={22} rx={11} fill={C(i)}>
              <animate attributeName="width" from="0" to={Math.max(24, bw * frac)} dur="0.6s" fill="freeze" begin={`${i * 0.1}s`} />
            </rect>
            {hasNums && vals[i] > 0 && (
              <text x={x0 + Math.max(24, bw * frac) + 8} y={y + 15} fontSize={11.5} fontWeight="700" fill={theme.sub}>{vals[i]}</text>
            )}
          </g>
        )
      })}
    </g>
  )
}
