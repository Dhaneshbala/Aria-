import { useState, useEffect, useRef, useCallback } from 'react'
import { getKnowledgeGraphData, getKnowledgeGraphStats, searchKnowledgeGraph, clearKnowledgeGraph } from '../services/api'
import { showToast } from '../components/Toast'

const TYPE_COLORS = {
  person: '#7c6af7',
  file: '#f59e0b',
  date: '#06b6d4',
  concept: '#10b981',
  project: '#ef4444',
  topic: '#8b5cf6',
}

const TYPE_ICONS = {
  person: '👤',
  file: '📄',
  date: '📅',
  concept: '💡',
  project: '📁',
  topic: '📚',
}

export default function KnowledgeGraphPage() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [stats, setStats] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const canvasRef = useRef(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [graph, statsData] = await Promise.all([
        getKnowledgeGraphData(300),
        getKnowledgeGraphStats(),
      ])
      setGraphData(graph)
      setStats(statsData)
    } catch (e) {
      showToast('Failed to load knowledge graph', 'error')
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    try {
      const results = await searchKnowledgeGraph(searchQuery)
      setSearchResults(results)
    } catch (e) {
      showToast('Search failed', 'error')
    }
  }

  const handleClear = async () => {
    if (!confirm('Clear entire knowledge graph? This cannot be undone.')) return
    try {
      await clearKnowledgeGraph()
      setGraphData({ nodes: [], edges: [] })
      setStats(null)
      showToast('Knowledge graph cleared', 'success')
    } catch (e) {
      showToast('Failed to clear', 'error')
    }
  }

  // Draw graph on canvas
  useEffect(() => {
    if (!canvasRef.current || graphData.nodes.length === 0) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const width = canvas.width = canvas.parentElement.clientWidth
    const height = canvas.height = canvas.parentElement.clientHeight

    ctx.fillStyle = '#0f0f0f'
    ctx.fillRect(0, 0, width, height)

    const filteredNodes = filter === 'all'
      ? graphData.nodes
      : graphData.nodes.filter(n => n.type === filter)

    if (filteredNodes.length === 0) return

    // Layout: force-directed approximation (simple circular)
    const cx = width / 2
    const cy = height / 2
    const radius = Math.min(width, height) * 0.35
    const nodePositions = {}

    filteredNodes.forEach((node, i) => {
      const angle = (i / filteredNodes.length) * Math.PI * 2
      const r = radius * (0.5 + (node.mentions || 1) * 0.1)
      nodePositions[node.id] = {
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        node,
      }
    })

    // Draw edges
    ctx.strokeStyle = 'rgba(124, 106, 247, 0.15)'
    ctx.lineWidth = 1
    graphData.edges.forEach(edge => {
      const a = nodePositions[edge.source]
      const b = nodePositions[edge.target]
      if (a && b) {
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.stroke()
      }
    })

    // Draw nodes
    Object.values(nodePositions).forEach(({ x, y, node }) => {
      const color = TYPE_COLORS[node.type] || '#7c6af7'
      const size = 4 + Math.min(node.mentions || 1, 10) * 1.5

      ctx.beginPath()
      ctx.arc(x, y, size, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.3)'
      ctx.lineWidth = 1
      ctx.stroke()

      // Label
      if (node.mentions >= 2 || filteredNodes.length < 30) {
        ctx.fillStyle = '#e8e8e8'
        ctx.font = '10px system-ui'
        ctx.textAlign = 'center'
        const label = node.value.length > 20 ? node.value.slice(0, 20) + '…' : node.value
        ctx.fillText(label, x, y + size + 12)
      }
    })

    // Handle click
    const handleClick = (e) => {
      const rect = canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top

      for (const { x, y, node } of Object.values(nodePositions)) {
        const dist = Math.sqrt((mx - x) ** 2 + (my - y) ** 2)
        if (dist < 15) {
          setSelectedNode(node)
          return
        }
      }
      setSelectedNode(null)
    }

    canvas.onclick = handleClick
  }, [graphData, filter])

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-[#e8e8e8]">Knowledge Graph</h1>
        <div className="flex gap-2">
          <button onClick={loadData} className="px-3 py-1.5 text-xs rounded-lg bg-[#1a1a2e] text-[#aaa] hover:bg-[#252540] transition-colors">
            Refresh
          </button>
          <button onClick={handleClear} className="px-3 py-1.5 text-xs rounded-lg bg-red-900/30 text-red-400 hover:bg-red-900/50 transition-colors">
            Clear
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#7c6af7]">{stats.total_nodes}</div>
            <div className="text-xs text-[#666]">Nodes</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#06b6d4]">{stats.total_edges}</div>
            <div className="text-xs text-[#666]">Connections</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#10b981]">{stats.by_type?.person || 0}</div>
            <div className="text-xs text-[#666]">People</div>
          </div>
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#f59e0b]">{stats.by_type?.file || 0}</div>
            <div className="text-xs text-[#666]">Files</div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="flex gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search the knowledge graph..."
          className="flex-1 px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
        />
        <button onClick={handleSearch} className="px-4 py-2 text-sm rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">
          Search
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {['all', 'person', 'file', 'date', 'concept', 'project', 'topic'].map(type => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              filter === type
                ? 'bg-[#7c6af7] text-white'
                : 'bg-[#1a1a2e] text-[#888] hover:bg-[#252540]'
            }`}
          >
            {type === 'all' ? 'All' : `${TYPE_ICONS[type] || ''} ${type}`}
          </button>
        ))}
      </div>

      {/* Canvas */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#666]">Loading...</div>
      ) : graphData.nodes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-[#666] gap-2">
          <p className="text-3xl">🧠</p>
          <p>No knowledge graph data yet</p>
          <p className="text-xs text-[#555]">Start chatting and Aria will automatically build a knowledge graph from your conversations</p>
        </div>
      ) : (
        <div className="flex-1 rounded-xl border border-[#2a2a40] overflow-hidden relative">
          <canvas ref={canvasRef} className="w-full h-full cursor-pointer" />
          {selectedNode && (
            <div className="absolute bottom-3 left-3 right-3 p-3 rounded-xl bg-[#1a1a2e]/95 backdrop-blur border border-[#2a2a40]">
              <div className="flex items-center gap-2 mb-1">
                <span>{TYPE_ICONS[selectedNode.type]}</span>
                <span className="font-semibold text-sm text-[#e8e8e8]">{selectedNode.value}</span>
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: TYPE_COLORS[selectedNode.type] + '30', color: TYPE_COLORS[selectedNode.type] }}>
                  {selectedNode.type}
                </span>
              </div>
              <div className="text-xs text-[#888]">
                Mentions: {selectedNode.mentions} · Conversations: {selectedNode.conversations?.length || 0} · First seen: {selectedNode.first_seen?.slice(0, 10)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Search results */}
      {searchResults.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-[#aaa]">Search Results</h3>
          {searchResults.map((r, i) => (
            <div key={i} className="p-2 rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-xs">
              <span className="mr-2">{TYPE_ICONS[r.type]}</span>
              <span className="text-[#e8e8e8]">{r.value}</span>
              <span className="ml-2 text-[#666]">({r.type})</span>
              {r.mentions > 1 && <span className="ml-2 text-[#7c6af7]">×{r.mentions}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
