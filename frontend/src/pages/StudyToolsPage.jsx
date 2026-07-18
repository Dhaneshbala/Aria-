import { useState } from 'react'
import { generateEssayFeedback, generateFormula, generateTimeline } from '../services/api'
import { BookOpen, PenTool, Calculator, Clock, Loader } from 'lucide-react'

const TOOLS = [
  { id: 'essay',    icon: PenTool,    label: 'Essay Feedback',   color: 'text-yellow-400' },
  { id: 'formula',  icon: Calculator, label: 'Formula Reference', color: 'text-blue-400' },
  { id: 'timeline', icon: Clock,      label: 'Timeline Generator', color: 'text-green-400' },
]

export default function StudyToolsPage() {
  const [activeTool, setActiveTool] = useState('essay')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')

  // Essay state
  const [essay, setEssay] = useState('')
  const [essayTopic, setEssayTopic] = useState('')

  // Formula state
  const [formulaTopic, setFormulaTopic] = useState('')

  // Timeline state
  const [timelineTopic, setTimelineTopic] = useState('')

  const handleEssay = async () => {
    if (!essay.trim()) return
    setLoading(true)
    setResult('')
    try {
      const data = await generateEssayFeedback(essay, essayTopic)
      setResult(data.feedback || 'No feedback generated.')
    } catch (e) {
      setResult('Error: ' + e.message)
    }
    setLoading(false)
  }

  const handleFormula = async () => {
    if (!formulaTopic.trim()) return
    setLoading(true)
    setResult('')
    try {
      const data = await generateFormula(formulaTopic)
      setResult(data.reference || 'No formulas generated.')
    } catch (e) {
      setResult('Error: ' + e.message)
    }
    setLoading(false)
  }

  const handleTimeline = async () => {
    if (!timelineTopic.trim()) return
    setLoading(true)
    setResult('')
    try {
      const data = await generateTimeline(timelineTopic)
      setResult(data.timeline || 'No timeline generated.')
    } catch (e) {
      setResult('Error: ' + e.message)
    }
    setLoading(false)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <BookOpen size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Study Tools</h1>
      </div>

      {/* Tool tabs */}
      <div className="flex gap-2 mb-6">
        {TOOLS.map(tool => (
          <button key={tool.id} onClick={() => { setActiveTool(tool.id); setResult('') }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm transition-all ${
              activeTool === tool.id
                ? 'bg-[#7c6af7]/15 text-[#a89bf8] border border-[#7c6af7]/30'
                : 'bg-[#141414] border border-[#2a2a2a] text-[#666] hover:text-[#aaa]'
            }`}>
            <tool.icon size={15} className={activeTool === tool.id ? tool.color : ''} />
            {tool.label}
          </button>
        ))}
      </div>

      {/* Essay Feedback */}
      {activeTool === 'essay' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Paste your essay below and get detailed feedback on structure, grammar, arguments, and more.</p>
          <input
            value={essayTopic}
            onChange={e => setEssayTopic(e.target.value)}
            placeholder="Essay topic (optional)"
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <textarea
            value={essay}
            onChange={e => setEssay(e.target.value)}
            placeholder="Paste your essay here..."
            rows={10}
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50 resize-none"
          />
          <button onClick={handleEssay} disabled={!essay.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Analysing essay...' : 'Get Feedback'}
          </button>
        </div>
      )}

      {/* Formula Reference */}
      {activeTool === 'formula' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Get a comprehensive formula reference sheet for any topic.</p>
          <input
            value={formulaTopic}
            onChange={e => setFormulaTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleFormula()}
            placeholder="e.g. Quadratic equations, Chemical bonding, Newton's laws..."
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <button onClick={handleFormula} disabled={!formulaTopic.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Generating formulas...' : 'Get Formulas'}
          </button>
        </div>
      )}

      {/* Timeline */}
      {activeTool === 'timeline' && (
        <div className="space-y-3">
          <p className="text-xs text-[#555]">Generate a chronological timeline for any historical topic.</p>
          <input
            value={timelineTopic}
            onChange={e => setTimelineTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleTimeline()}
            placeholder="e.g. World War 2, Ancient Egypt, Renaissance..."
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
          />
          <button onClick={handleTimeline} disabled={!timelineTopic.trim() || loading}
            className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? 'Generating timeline...' : 'Generate Timeline'}
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-xs text-[#555] py-4 justify-center">
          <Loader size={13} className="animate-spin text-[#7c6af7]" /> Processing...
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <div className="mt-4 bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
          {result}
        </div>
      )}
    </div>
  )
}
