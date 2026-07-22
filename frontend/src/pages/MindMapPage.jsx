import { useState, useEffect } from 'react'
import { generateMindmap } from '../services/api'
import { useStore } from '../store'
import MindMapWidget from '../components/MindMapWidget'
import { Network } from 'lucide-react'

export default function MindMapPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.mindmap
  const [topic, setTopic] = useState(saved.topic || '')
  const [mindmap, setMindmap] = useState(saved.data || null)
  const [loading, setLoading] = useState(false)

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('mindmap', { data: mindmap, topic })
  }, [mindmap, topic])

  const generate = async () => {
    if (!topic.trim()) return
    setLoading(true)
    try {
      const data = await generateMindmap(topic)
      setMindmap(data.mindmap || data)
    } catch {}
    setLoading(false)
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <Network size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Mind Map Generator</h1>
      </div>

      {!mindmap && !loading && (
        <div className="space-y-4 max-w-lg">
          <input
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && generate()}
            placeholder="Topic (e.g. The Water Cycle, Machine Learning, Ancient Rome...)"
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <button onClick={generate} disabled={!topic.trim()}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            Generate Mind Map
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Building mind map for "{topic}"...</p>
        </div>
      )}

      {mindmap && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[#e8e8e8] font-medium">{mindmap.center}</h2>
            <button
              onClick={() => { setMindmap(null); setTopic('') }}
              className="text-xs text-[#555] hover:text-[#888] px-3 py-1.5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]"
            >
              ↺ New map
            </button>
          </div>
          <MindMapWidget data={mindmap} showDownload={true} />
        </div>
      )}
    </div>
  )
}
