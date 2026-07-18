import { useState } from 'react'
import { generatePptx } from '../services/api'
import { showToast } from '../components/Toast'
import { Loader, Sparkles, Presentation, ChevronDown, Lightbulb } from 'lucide-react'

const SUGGESTIONS = [
  { topic: 'The Solar System', icon: '🪐' },
  { topic: 'Photosynthesis', icon: '🌿' },
  { topic: 'World War 2', icon: '🌍' },
  { topic: 'Ancient Egypt', icon: '🏛️' },
  { topic: 'Climate Change', icon: '🌡️' },
  { topic: 'Artificial Intelligence', icon: '🤖' },
  { topic: 'The Human Body', icon: '🧬' },
  { topic: 'Ocean Ecosystems', icon: '🌊' },
  { topic: 'Space Exploration', icon: '🚀' },
  { topic: 'World War 2', icon: '⚔️' },
  { topic: 'DNA and Genetics', icon: '🧬' },
  { topic: 'Volcanoes and Earthquakes', icon: '🌋' },
]

export default function PptxPage() {
  const [topic, setTopic] = useState('')
  const [slides, setSlides] = useState(10)
  const [loading, setLoading] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)

  const handle = async () => {
    if (!topic.trim()) return
    setLoading(true)
    try {
      await generatePptx(topic, slides)
      showToast(`Presentation on "${topic}" downloaded!`, 'success')
    } catch (e) {
      showToast('Failed to generate presentation: ' + e.message, 'error')
    }
    setLoading(false)
  }

  const pick = (t) => {
    setTopic(t)
    setShowSuggestions(false)
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-2">
        <Presentation size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">PowerPoint Generator</h1>
      </div>
      <p className="text-xs text-[#555] mb-6">
        Slidesgo-style presentations with images, icons, and professional layouts
      </p>

      <div className="space-y-4">
        {/* Topic input */}
        <div className="relative">
          <input
            value={topic}
            onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handle()}
            onFocus={() => setShowSuggestions(true)}
            placeholder="Topic e.g. The Solar System, World War 2, Photosynthesis..."
            className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50"
          />
          <button
            onClick={() => setShowSuggestions(!showSuggestions)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-[#888]"
          >
            <Lightbulb size={16} />
          </button>

          {/* Suggestions dropdown */}
          {showSuggestions && !topic && (
            <div className="absolute z-10 top-full left-0 right-0 mt-2 bg-[#141414] border border-[#2a2a2a] rounded-xl p-3 shadow-xl">
              <p className="text-xs text-[#555] mb-2 px-1">Suggested topics:</p>
              <div className="grid grid-cols-2 gap-1.5">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => pick(s.topic)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm text-[#ccc] hover:bg-[#1e1e1e] hover:text-[#e8e8e8] transition-colors"
                  >
                    <span>{s.icon}</span>
                    <span>{s.topic}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Slide count */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-[#666]">Slides:</label>
          {[5, 8, 10, 15].map(n => (
            <button key={n} onClick={() => setSlides(n)}
              className={`w-10 h-8 rounded-lg text-xs font-medium transition-colors ${
                slides === n ? 'bg-[#7c6af7] text-white' : 'bg-[#141414] border border-[#2a2a2a] text-[#666] hover:text-[#999]'
              }`}>
              {n}
            </button>
          ))}
        </div>

        {/* Generate button */}
        <button onClick={handle} disabled={!topic.trim() || loading}
          className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading
            ? <><Loader size={15} className="animate-spin" /> Generating {slides} slides — takes ~30s...</>
            : <><Sparkles size={15} /> Generate PowerPoint</>}
        </button>

        {loading && (
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-3 text-center">
            <p className="text-xs text-[#666]">
              AI is writing content, fetching images, and building your presentation...
            </p>
            <p className="text-xs text-[#444] mt-1">
              This usually takes 20-40 seconds depending on slide count
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
