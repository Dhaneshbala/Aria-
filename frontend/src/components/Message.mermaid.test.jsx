import { describe, it, expect } from 'vitest'
import { sanitizeMermaid, extractMermaidLabels, buildRepairGraph, cleanMermaidLabel } from './message/Diagrams'

describe('sanitizeMermaid', () => {
  it('strips parens/colons/semicolons/hashes from graph labels', () => {
    const out = sanitizeMermaid('graph TD\n    A[Evaporation (sun heats water)] --> B[Heat: 50%; #1]')
    expect(out.startsWith('graph TD')).toBe(true)
    const labels = (out.match(/\[.*?\]/g) || []).join(' ')
    expect(labels).not.toMatch(/[()#;:]/)
    expect(out).toContain('-->')
  })

  it('prepends graph TD when header is missing', () => {
    const out = sanitizeMermaid('A[Sun] --> B[Rain]')
    expect(out.startsWith('graph TD')).toBe(true)
  })

  it('keeps sequenceDiagram arrows intact', () => {
    const out = sanitizeMermaid('sequenceDiagram\n    Customer->>Website: search for book')
    expect(out).toContain('sequenceDiagram')
    expect(out).toContain('->>')
  })

  it('balances nested parens in mindmap root', () => {
    const out = sanitizeMermaid('mindmap\n  root((Solar (System)))\n    Rocky planets')
    const opens = (out.match(/\(/g) || []).length
    const closes = (out.match(/\)/g) || []).length
    expect(opens).toBe(closes)
  })

  it('keeps valid diagrams valid', () => {
    const good = 'graph TD\n    A[Sun heats oceans] --> B[Evaporation]\n    B --> C[Condensation - clouds form]'
    expect(sanitizeMermaid(good)).toContain('graph TD')
  })
})

describe('extractMermaidLabels', () => {
  it('extracts fallback steps from broken code', () => {
    const labels = extractMermaidLabels('graph TD\n    A[Evaporation] --> B[Condensation]')
    expect(labels).toContain('Evaporation')
    expect(labels).toContain('Condensation')
  })
})

describe('buildRepairGraph', () => {
  it('rebuilds a chained flowchart from broken input', () => {
    const out = buildRepairGraph('graph TD\n    A[Evaporation (oops)] --> ???\n    B[Condensation: clouds]')
    expect(out.startsWith('graph TD')).toBe(true)
    expect(out).toContain('A[Evaporation -oops-]')
    expect(out).toContain('A --> B')
  })

  it('caps at 6 nodes with 5 edges', () => {
    const many = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
      .map((id, i) => `    ${id}[Step ${i + 1}]`).join('\n')
    const out = buildRepairGraph(`graph TD\n${many}`)
    const edges = out.match(/-->/g) || []
    expect(edges.length).toBe(5)
  })

  it('returns null when nothing usable can be extracted', () => {
    expect(buildRepairGraph('')).toBe(null)
  })
})

describe('cleanMermaidLabel', () => {
  it('removes every label-breaking character', () => {
    expect(cleanMermaidLabel('Heat: 50%; #1 (hot) "quoted" <b> & more')).not.toMatch(/[()#;:"'`<>|]/)
  })
})
