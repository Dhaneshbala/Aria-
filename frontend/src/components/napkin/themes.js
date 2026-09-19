/**
 * NapkinDiagram themes + visual-type catalogue.
 * Extracted from NapkinDiagram.jsx — single source of truth for type metadata.
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

export const THEMES = {
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
