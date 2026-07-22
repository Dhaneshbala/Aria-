import { useState } from 'react'
import { Wrench, FileText, Quote, ArrowLeftRight, BarChart3, Mic } from 'lucide-react'
import { showToast } from '../components/Toast'

const TABS = [
  { id: 'summariser', label: 'Smart Summariser', icon: FileText },
  { id: 'citation', label: 'Citation Generator', icon: Quote },
  { id: 'converter', label: 'Unit Converter', icon: ArrowLeftRight },
  { id: 'plotter', label: 'Graph Plotter', icon: BarChart3 },
  { id: 'voice-cards', label: 'Voice to Cards', icon: Mic },
]

const UNIT_GROUPS = {
  'Length': ['m', 'km', 'cm', 'mm', 'ft', 'in', 'mi'],
  'Mass': ['kg', 'g', 'lb', 'oz'],
  'Temperature': ['C', 'F', 'K'],
  'Volume': ['L', 'mL', 'gal', 'fl_oz'],
  'Speed': ['km/h', 'mph', 'm/s'],
  'Data': ['KB', 'MB', 'GB', 'TB'],
}

const ALL_UNITS = Object.values(UNIT_GROUPS).flat()

export default function UtilitiesPage() {
  const [tab, setTab] = useState('summariser')
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex border-b border-[#2a2a40] px-4 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
              tab === t.id
                ? 'border-[#7c6af7] text-[#7c6af7]'
                : 'border-transparent text-[#888] hover:text-[#ccc]'
            }`}
          >
            <t.icon size={14} />
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'summariser' && <SummariserTab />}
        {tab === 'citation' && <CitationTab />}
        {tab === 'converter' && <ConverterTab />}
        {tab === 'plotter' && <PlotterTab />}
        {tab === 'voice-cards' && <VoiceToCardsTab />}
      </div>
    </div>
  )
}

function SummariserTab() {
  const [text, setText] = useState('')
  const [level, setLevel] = useState('paragraph')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSummarise = async () => {
    if (!text.trim()) return
    setLoading(true); setResult('')
    try {
      const resp = await fetch('/api/v2/util/summarise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, level }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setResult(data.summary)
    } catch (e) {
      showToast(`Summarise failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 mb-2">
        <FileText size={18} className="text-[#7c6af7]" />
        <h2 className="text-base font-semibold text-[#e8e8e8]">Smart Summariser</h2>
      </div>
      <p className="text-xs text-[#666]">Paste text and get a summary at your preferred detail level.</p>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Paste your text here..."
        rows={8}
        className="w-full px-4 py-3 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] resize-none"
      />
      <div className="flex items-center gap-3">
        <label className="text-xs text-[#888]">Detail level:</label>
        {['one_liner', 'paragraph', 'detailed'].map(l => (
          <button key={l} onClick={() => setLevel(l)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
              level === l
                ? 'bg-[#7c6af7] text-white'
                : 'bg-[#252540] border border-[#2a2a40] text-[#888] hover:text-[#ccc]'
            }`}>
            {l === 'one_liner' ? 'One-liner' : l === 'paragraph' ? 'Paragraph' : 'Detailed'}
          </button>
        ))}
      </div>
      <button onClick={handleSummarise} disabled={!text.trim() || loading}
        className="px-5 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
        {loading ? 'Summarising...' : 'Summarise'}
      </button>
      {result && (
        <div className="p-4 rounded-xl bg-[#252540] border border-[#2a2a40]">
          <p className="text-xs text-[#888] mb-2">Summary</p>
          <p className="text-sm text-[#ccc] leading-relaxed whitespace-pre-wrap">{result}</p>
        </div>
      )}
    </div>
  )
}

function CitationTab() {
  const [fields, setFields] = useState({ author: '', title: '', year: '', publisher: '', url: '', journal: '' })
  const [style, setStyle] = useState('apa')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const update = (key, val) => setFields(f => ({ ...f, [key]: val }))

  const handleGenerate = async () => {
    if (!fields.author.trim() || !fields.title.trim()) {
      showToast('Author and title are required', 'error')
      return
    }
    setLoading(true); setResult('')
    try {
      const resp = await fetch('/api/v2/util/citation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: fields, style }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setResult(data.citation)
    } catch (e) {
      showToast(`Citation failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 mb-2">
        <Quote size={18} className="text-[#7c6af7]" />
        <h2 className="text-base font-semibold text-[#e8e8e8]">Citation Generator</h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[
          { key: 'author', label: 'Author', placeholder: 'J. Smith', required: true },
          { key: 'title', label: 'Title', placeholder: 'Article title', required: true },
          { key: 'year', label: 'Year', placeholder: '2024' },
          { key: 'publisher', label: 'Publisher', placeholder: 'Publisher name' },
          { key: 'url', label: 'URL', placeholder: 'https://...' },
          { key: 'journal', label: 'Journal', placeholder: 'Journal name' },
        ].map(f => (
          <div key={f.key}>
            <label className="block text-xs text-[#888] mb-1">
              {f.label} {f.required && <span className="text-red-400">*</span>}
            </label>
            <input
              value={fields[f.key]}
              onChange={e => update(f.key, e.target.value)}
              placeholder={f.placeholder}
              className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <label className="text-xs text-[#888]">Style:</label>
        {['apa', 'mla', 'harvard', 'chicago'].map(s => (
          <button key={s} onClick={() => setStyle(s)}
            className={`px-3 py-1.5 rounded-lg text-xs uppercase transition-all ${
              style === s
                ? 'bg-[#7c6af7] text-white'
                : 'bg-[#252540] border border-[#2a2a40] text-[#888] hover:text-[#ccc]'
            }`}>
            {s}
          </button>
        ))}
      </div>
      <button onClick={handleGenerate} disabled={loading}
        className="px-5 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
        {loading ? 'Generating...' : 'Generate Citation'}
      </button>
      {result && (
        <div className="p-4 rounded-xl bg-[#252540] border border-[#2a2a40]">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-[#888]">Citation ({style.toUpperCase()})</p>
            <button onClick={() => { navigator.clipboard.writeText(result); showToast('Copied!', 'success') }}
              className="text-xs text-[#7c6af7] hover:text-[#a89bf8]">
              Copy
            </button>
          </div>
          <p className="text-sm text-[#ccc] leading-relaxed" dangerouslySetInnerHTML={{ __html: result.replace(/\*(.*?)\*/g, '<em>$1</em>') }} />
        </div>
      )}
    </div>
  )
}

function ConverterTab() {
  const [value, setValue] = useState('')
  const [fromUnit, setFromUnit] = useState('kg')
  const [toUnit, setToUnit] = useState('lb')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleConvert = async () => {
    const num = parseFloat(value)
    if (isNaN(num)) {
      showToast('Enter a valid number', 'error')
      return
    }
    setLoading(true); setResult(null)
    try {
      const resp = await fetch('/api/v2/util/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: num, from_unit: fromUnit, to_unit: toUnit }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setResult(data)
    } catch (e) {
      showToast(`Conversion failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  const swapUnits = () => { setFromUnit(toUnit); setToUnit(fromUnit); setResult(null) }

  return (
    <div className="space-y-4 max-w-lg mx-auto">
      <div className="flex items-center gap-2 mb-2">
        <ArrowLeftRight size={18} className="text-[#7c6af7]" />
        <h2 className="text-base font-semibold text-[#e8e8e8]">Unit Converter</h2>
      </div>

      <div>
        <label className="block text-xs text-[#888] mb-1">Value</label>
        <input
          type="number"
          value={value}
          onChange={e => { setValue(e.target.value); setResult(null) }}
          placeholder="Enter value"
          className="w-full px-4 py-2.5 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
        />
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-xs text-[#888] mb-1">From</label>
          <select value={fromUnit} onChange={e => { setFromUnit(e.target.value); setResult(null) }}
            className="w-full appearance-none px-3 py-2.5 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] outline-none focus:border-[#7c6af7] cursor-pointer">
            {Object.entries(UNIT_GROUPS).map(([group, units]) => (
              <optgroup key={group} label={group}>
                {units.map(u => <option key={u} value={u}>{u}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        <button onClick={swapUnits}
          className="p-2.5 rounded-xl bg-[#252540] border border-[#2a2a40] text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors mb-px">
          <ArrowLeftRight size={16} />
        </button>
        <div className="flex-1">
          <label className="block text-xs text-[#888] mb-1">To</label>
          <select value={toUnit} onChange={e => { setToUnit(e.target.value); setResult(null) }}
            className="w-full appearance-none px-3 py-2.5 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] outline-none focus:border-[#7c6af7] cursor-pointer">
            {Object.entries(UNIT_GROUPS).map(([group, units]) => (
              <optgroup key={group} label={group}>
                {units.map(u => <option key={u} value={u}>{u}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      <button onClick={handleConvert} disabled={loading || !value}
        className="px-5 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
        {loading ? 'Converting...' : 'Convert'}
      </button>

      {result && (
        <div className="p-5 rounded-2xl bg-[#252540] border border-[#2a2a40] text-center">
          <p className="text-3xl font-bold text-[#e8e8e8] mb-1">
            {result.output} <span className="text-lg text-[#888]">{result.to}</span>
          </p>
          <p className="text-xs text-[#666]">{result.input} {result.from}</p>
          {result.formula && (
            <p className="text-xs text-[#7c6af7] mt-2 font-mono">{result.formula}</p>
          )}
        </div>
      )}
    </div>
  )
}

function PlotterTab() {
  const [expression, setExpression] = useState('')
  const [xMin, setXMin] = useState(-10)
  const [xMax, setXMax] = useState(10)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handlePlot = async () => {
    if (!expression.trim()) return
    setLoading(true); setResult(null)
    try {
      const resp = await fetch('/api/v2/util/plot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression, x_min: xMin, x_max: xMax }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setResult(data)
    } catch (e) {
      showToast(`Plot failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  const renderBarChart = (points, yMin, yMax) => {
    if (!points || points.length === 0) return null
    const range = yMax - yMin || 1
    const maxBars = 40
    const step = Math.max(1, Math.floor(points.length / maxBars))
    const sampled = points.filter((_, i) => i % step === 0)
    const barWidth = Math.max(4, Math.floor(500 / sampled.length))

    return (
      <div className="flex items-end gap-px h-40 px-2 pt-2 pb-6 relative">
        {/* Zero line */}
        {yMin < 0 && yMax > 0 && (
          <div className="absolute left-2 right-2 border-t border-[#555] border-dashed"
            style={{ bottom: `${(Math.abs(yMin) / range) * 100 + 6}%` }} />
        )}
        {sampled.map((p, i) => {
          const normalized = (p.y - yMin) / range
          const height = Math.max(1, normalized * 100)
          const isNeg = p.y < 0
          return (
            <div key={i} className="flex-1 flex flex-col items-center justify-end relative"
              title={`x: ${p.x}, y: ${p.y}`}>
              <div
                className={`w-full rounded-t ${isNeg ? 'bg-red-400/70' : 'bg-[#7c6af7]/70'}`}
                style={{
                  height: `${Math.abs(normalized) * 100}%`,
                  minHeight: '1px',
                }}
              />
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 size={18} className="text-[#7c6af7]" />
        <h2 className="text-base font-semibold text-[#e8e8e8]">Graph Plotter</h2>
      </div>
      <p className="text-xs text-[#666]">Enter a mathematical expression using x as the variable.</p>

      <div>
        <label className="block text-xs text-[#888] mb-1">Expression</label>
        <input
          value={expression}
          onChange={e => setExpression(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handlePlot()}
          placeholder="e.g. x^2, sin(x), 2*x + 1"
          className="w-full px-4 py-2.5 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] font-mono"
        />
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-xs text-[#888] mb-1">X Min</label>
          <input type="number" value={xMin} onChange={e => setXMin(Number(e.target.value))}
            className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7] font-mono" />
        </div>
        <div className="flex-1">
          <label className="block text-xs text-[#888] mb-1">X Max</label>
          <input type="number" value={xMax} onChange={e => setXMax(Number(e.target.value))}
            className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] focus:outline-none focus:border-[#7c6af7] font-mono" />
        </div>
      </div>

      <button onClick={handlePlot} disabled={loading || !expression.trim()}
        className="px-5 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
        {loading ? 'Plotting...' : 'Plot'}
      </button>

      {result && (
        <div className="p-4 rounded-xl bg-[#252540] border border-[#2a2a40]">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-[#888]">
              <span className="font-mono text-[#e8e8e8]">{result.expression}</span>
              <span className="ml-2">[{result.x_range?.join(', ')}]</span>
            </p>
            <p className="text-[10px] text-[#666]">{result.points?.length} points</p>
          </div>
          {renderBarChart(result.points, result.y_min, result.y_max)}
          <div className="flex items-center justify-between mt-1 px-2">
            <span className="text-[10px] text-[#666]">y: {result.y_min?.toFixed(1)}</span>
            <span className="text-[10px] text-[#666]">y: {result.y_max?.toFixed(1)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function VoiceToCardsTab() {
  const [transcript, setTranscript] = useState('')
  const [count, setCount] = useState(5)
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    if (!transcript.trim()) return
    setLoading(true); setCards([])
    try {
      const resp = await fetch('/api/v2/util/voice-to-cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, count }),
      })
      const data = await resp.json()
      if (data.error) throw new Error(data.error)
      setCards(data.cards || [])
      if (!data.cards?.length) showToast('No flashcards could be extracted', 'info')
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 mb-2">
        <Mic size={18} className="text-[#7c6af7]" />
        <h2 className="text-base font-semibold text-[#e8e8e8]">Voice to Flashcards</h2>
      </div>
      <p className="text-xs text-[#666]">Paste a voice transcript and generate flashcards automatically.</p>
      <textarea
        value={transcript}
        onChange={e => setTranscript(e.target.value)}
        placeholder="Paste your voice transcript here..."
        rows={6}
        className="w-full px-4 py-3 text-sm rounded-xl bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] resize-none"
      />
      <div className="flex items-center gap-3">
        <label className="text-xs text-[#888]">Cards:</label>
        {[3, 5, 8, 10].map(n => (
          <button key={n} onClick={() => setCount(n)}
            className={`w-10 h-8 rounded-lg text-xs transition-all ${
              count === n
                ? 'bg-[#7c6af7] text-white'
                : 'bg-[#252540] border border-[#2a2a40] text-[#888]'
            }`}>
            {n}
          </button>
        ))}
      </div>
      <button onClick={handleGenerate} disabled={!transcript.trim() || loading}
        className="px-5 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
        {loading ? 'Generating...' : 'Generate Flashcards'}
      </button>

      {cards.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-[#888]">{cards.length} cards generated</p>
          {cards.map((card, i) => (
            <div key={i} className="p-4 rounded-xl bg-[#252540] border border-[#2a2a40]">
              <div className="flex items-start gap-3">
                <span className="text-xs text-[#7c6af7] font-bold mt-0.5">{i + 1}</span>
                <div className="flex-1 grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-[10px] text-[#666] uppercase mb-1">Front</p>
                    <p className="text-sm text-[#e8e8e8]">{card.front}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-[#666] uppercase mb-1">Back</p>
                    <p className="text-sm text-[#ccc]">{card.back}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
