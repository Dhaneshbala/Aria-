import { useState, useEffect, useRef } from 'react'
import { generateMindmap } from '../services/api'
import { startTask, cancelTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import MindMapWidget from '../components/MindMapWidget'
import { Network } from 'lucide-react'

export default function MindMapPage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.mindmap
  const [topic, setTopic] = useState(saved.topic || '')
  const [mindmap, setMindmap] = useState(saved.data || null)
  const [loading, setLoading] = useState(
    () => useStore.getState().bgTasks?.mindmap?.status === 'running'
  )
  const bg = useBgTask('mindmap')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  // Adopt a background run when returning mid-generation, or a result
  // that landed in the store while we were away.
  useEffect(() => {
    if (bg?.status === 'running') {
      setLoading(true)
      if (bg.topic && !topic) setTopic(bg.topic)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (bg?.status === 'done' && !mindmap && saved.data) {
      setMindmap(saved.data)
      setTopic(saved.topic || topic)
      setLoading(false)
    } else if ((bg?.status === 'error' || bg?.status === 'cancelled') && loading && !mindmap) {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg?.status])

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('mindmap', { data: mindmap, topic })
  }, [mindmap, topic])

  const generate = async () => {
    if (!topic.trim()) return
    const t = topic.trim()
    setLoading(true)
    try {
      // Background-safe: navigate away and the map still lands in the store.
      const data = await startTask('mindmap', {
        label: `Mind map: ${t}`,
        page: '/create',
        topic: t,
        run: (signal) => generateMindmap(t, signal),
        onDone: (d) => setStudyTool('mindmap', { data: d.mindmap || d, topic: t }),
      })
      if (!mountedRef.current) return
      setMindmap(data.mindmap || data)
    } catch {}
    if (mountedRef.current) setLoading(false)
  }

  const cancel = () => {
    cancelTask('mindmap')
    setLoading(false)
  }

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter">
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
          <p className="text-[#555] text-xs">Keeps working if you leave this page</p>
          <button onClick={cancel} className="mt-1 px-4 py-1.5 rounded-full bg-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8]">Cancel</button>
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
