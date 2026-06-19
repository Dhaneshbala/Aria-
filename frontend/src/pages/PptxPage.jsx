import { useState } from 'react'
import { generatePptx } from '../services/api'
import { Presentation, Loader, Sparkles } from 'lucide-react'

export default function PptxPage() {
  const [topic, setTopic] = useState('')
  const [slides, setSlides] = useState(10)
  const [loading, setLoading] = useState(false)

  const handle = async () => {
    if (!topic.trim()) return
    setLoading(true)
    try {
      await generatePptx(topic, slides)
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <Sparkles size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">PowerPoint Generator</h1>
      </div>
      <div className="space-y-4">
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handle()}
          placeholder="Topic e.g. The Solar System, World War 2, Photosynthesis..."
          className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50"
        />
        <div className="flex items-center gap-3">
          <label className="text-xs text-[#666]">Slides:</label>
          {[5, 8, 10, 15].map(n => (
            <button key={n} onClick={() => setSlides(n)}
              className={`w-10 h-8 rounded-lg text-xs transition-colors ${
                slides === n ? 'bg-[#7c6af7] text-white' : 'bg-[#141414] border border-[#2a2a2a] text-[#666]'
              }`}>
              {n}
            </button>
          ))}
        </div>
        <button onClick={handle} disabled={!topic.trim() || loading}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading
            ? <><Loader size={15} className="animate-spin" /> Generating {slides} slides — this takes ~30 seconds...</>
            : <><Sparkles size={15} /> Generate PowerPoint</>}
        </button>
        {loading && (
          <p className="text-xs text-[#555] text-center">
            AI is writing content, fetching images and building your presentation...
          </p>
        )}
      </div>
    </div>
  )
}