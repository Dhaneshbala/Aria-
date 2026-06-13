import { useState } from 'react'
import { generateImage } from '../services/api'
import { Sparkles, Download, Loader, Zap } from 'lucide-react'

const PRESETS = [
  { emoji: '🌌', text: 'Draw the solar system with all planets labelled' },
  { emoji: '🌿', text: 'A colourful diagram of photosynthesis' },
  { emoji: '💧', text: 'An educational poster showing the water cycle' },
  { emoji: '🧬', text: 'A diagram of the human digestive system' },
  { emoji: '⏳', text: 'A timeline of ancient Egyptian history' },
  { emoji: '🔬', text: 'A labelled diagram of an animal cell' },
  { emoji: '🗺️', text: 'A mind map about the causes of World War 1' },
  { emoji: '➗', text: 'A visual explanation of the Pythagorean theorem' },
]

export default function ImageGenPage() {
  const [prompt, setPrompt] = useState('')
  const [image, setImage] = useState(null)
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const generate = async (text) => {
    const p = text || prompt
    if (!p.trim()) return
    setLoading(true)
    setImage(null)
    setError(null)
    setSource('')
    try {
      const data = await generateImage(p)
      if (data.image) {
        setImage(data.image)
        setSource(data.source || 'pollinations')
        setPrompt(p)
      } else {
        setError(data.error || 'Could not generate image. Check your internet connection.')
      }
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  const download = () => {
    if (!image) return
    const a = document.createElement('a')
    a.href = image
    a.download = `aria-${Date.now()}.jpg`
    a.click()
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Image Generator</h1>
      </div>
      <div className="flex items-center gap-2 mb-5 bg-green-500/8 border border-green-500/15 rounded-xl px-3 py-2">
        <Zap size={12} className="text-green-400 flex-shrink-0" />
        <p className="text-xs text-green-400">
          Powered by <strong>Pollinations.ai</strong> — free, no GPU needed, works on your MacBook Air M4
        </p>
      </div>

      <div className="space-y-4">
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); generate() }}}
          placeholder="Describe any educational image, diagram, or illustration..."
          rows={3}
          className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50 resize-none"
        />

        <button onClick={() => generate()} disabled={!prompt.trim() || loading}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading
            ? <><Loader size={15} className="animate-spin" /> Generating...</>
            : <><Sparkles size={15} /> Generate Image</>}
        </button>

        {/* Preset buttons */}
        <div>
          <p className="text-xs text-[#444] mb-2">Try these:</p>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map(({ emoji, text }) => (
              <button key={text}
                onClick={() => generate(text)}
                disabled={loading}
                className="flex items-center gap-2 text-left text-xs px-3 py-2.5 bg-[#141414] border border-[#2a2a2a] rounded-xl text-[#666] hover:text-[#aaa] hover:border-[#7c6af7]/30 transition-colors disabled:opacity-40">
                <span className="text-base flex-shrink-0">{emoji}</span>
                <span className="leading-tight">{text}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex flex-col items-center py-10 gap-3 mt-4">
          <div className="w-12 h-12 rounded-2xl bg-[#7c6af7]/10 flex items-center justify-center">
            <Sparkles size={20} className="text-[#7c6af7] animate-pulse" />
          </div>
          <p className="text-[#888] text-sm">Creating your image...</p>
          <p className="text-xs text-[#444]">Usually takes 5–15 seconds</p>
        </div>
      )}

      {error && (
        <div className="mt-5 bg-red-500/8 border border-red-500/15 rounded-xl p-4">
          <p className="text-sm text-red-400 font-medium mb-1">Could not generate image</p>
          <p className="text-xs text-red-400/60">{error}</p>
          <p className="text-xs text-[#444] mt-2">
            Image generation requires an internet connection (uses Pollinations.ai).
          </p>
        </div>
      )}

      {image && (
        <div className="mt-5">
          <img src={image} alt={prompt}
            className="w-full rounded-2xl border border-[#2a2a2a] shadow-2xl" />
          <div className="flex items-center justify-between mt-3">
            <p className="text-xs text-[#444] truncate flex-1 mr-3">{prompt}</p>
            <button onClick={download}
              className="flex items-center gap-1.5 text-xs text-[#666] hover:text-[#aaa] px-3 py-1.5 rounded-lg bg-[#141414] border border-[#2a2a2a] transition-colors flex-shrink-0">
              <Download size={12} /> Save
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
