import { useState, useEffect } from 'react'
import { getConfig, saveConfig, getModels, getHealth, clearAllMemory } from '../services/api'
import { Settings, Server, Cpu, HardDrive, RefreshCw, Check, Trash2, Zap, Info } from 'lucide-react'
import { useStore } from '../store'

// M4 MacBook Air recommended models with disk/RAM info
const RECOMMENDED = [
  { name: 'qwen2.5-coder:7b', ram: '7 GB', disk: '4.7 GB', role: 'coding', note: '⭐ Best for coding questions' },
  { name: 'qwen3:8b',      ram: '8 GB',  disk: '5.2 GB', role: 'reasoning', note: '⭐ Best for M4 16GB' },
  { name: 'qwen3:4b',      ram: '4 GB',  disk: '2.6 GB', role: 'reasoning', note: 'Faster, less accurate' },
  { name: 'llama3.2:3b',   ram: '3 GB',  disk: '2.0 GB', role: 'fallback',  note: 'Fastest option' },
  { name: 'qwen2.5vl:3b',  ram: '4 GB',  disk: '2.2 GB', role: 'vision',    note: '⭐ Best vision for M4 16GB' },
  { name: 'qwen2.5vl:7b',  ram: '7 GB',  disk: '4.7 GB', role: 'vision',    note: 'Higher quality, tight on RAM' },
  { name: 'moondream2',    ram: '3 GB',  disk: '1.8 GB', role: 'vision',    note: 'Lightweight vision' },
]

export default function AdminPage() {
  const [config, setConfig] = useState({})
  const [models, setModels] = useState([])
  const [health, setHealth] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [clearing, setClearing] = useState(false)
  const { setConfig: setStoreConfig } = useStore()

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {})
    getModels().then(d => setModels(d.models || [])).catch(() => {})
    getHealth().then(setHealth).catch(() => {})
  }, [])

  const refresh = () => {
    getHealth().then(setHealth).catch(() => {})
    getModels().then(d => setModels(d.models || [])).catch(() => {})
  }

  const save = async () => {
    setSaving(true)
    try {
      const result = await saveConfig(config)
      setStoreConfig(result)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {}
    setSaving(false)
  }

  const handleClearMemory = async () => {
    if (!window.confirm('Clear all conversation memory and study profiles? This cannot be undone.')) return
    setClearing(true)
    try {
      await clearAllMemory()
      alert('Memory cleared successfully.')
    } catch {}
    setClearing(false)
  }

  const modelNames = models.map(m => m.name || m)
  const totalDisk = models.reduce((sum, m) => sum + (m.size_gb || 0), 0)

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter overflow-y-auto h-full">
      <div className="flex items-center gap-2 mb-6">
        <Settings size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Admin Settings</h1>
      </div>

      {/* M4 Hardware info banner */}
      <div className="bg-[#7c6af7]/8 border border-[#7c6af7]/20 rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap size={14} className="text-[#7c6af7]" />
          <span className="text-xs font-semibold text-[#a89bf8]">Optimised for MacBook Air M4 16 GB</span>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">qwen3:8b</p>
            <p className="text-[10px] text-[#555] mt-0.5">Reasoning</p>
            <p className="text-[10px] text-[#444]">5.2 GB · 8 GB RAM</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">qwen2.5vl:3b</p>
            <p className="text-[10px] text-[#555] mt-0.5">Vision</p>
            <p className="text-[10px] text-[#444]">2.2 GB · 4 GB RAM</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-green-400 font-semibold">Pollinations.ai</p>
            <p className="text-[10px] text-[#555] mt-0.5">Image Gen</p>
            <p className="text-[10px] text-[#444]">Free · No CPU Or GPU</p>
          </div>
        </div>
        <p className="text-[10px] text-[#444] mt-2 text-center">
          Ollama uses Metal GPU automatically on Apple Silicon · One model loaded at a time
        </p>
      </div>

      {/* System health */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Server size={14} className="text-[#7c6af7]" />
            <h3 className="text-sm font-medium text-[#e8e8e8]">System Status</h3>
          </div>
          <button onClick={refresh} className="text-[#444] hover:text-[#888] transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
        <div className="space-y-2 mb-3">
          <StatusRow label="Ollama"
            ok={health?.ollama}
            desc={health?.ollama ? 'Running — Metal GPU active' : 'Not running — open Terminal and type: ollama serve'} />
          <StatusRow label="Pollinations.ai"
            ok={health?.pollinations !== false}
            desc="Free image generation — needs internet" />
        </div>
        {/* Installed models */}
        {models.length > 0 && (
          <div className="pt-3 border-t border-[#1e1e1e]">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] text-[#444] uppercase tracking-wider">Installed models</p>
              <p className="text-[10px] text-[#444]">~{totalDisk.toFixed(1)} GB used</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {models.map(m => (
                <div key={m.name || m}
                  className="flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full bg-[#1e1e1e] text-[#888]">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                  {m.name || m}
                  {m.size_gb ? <span className="text-[#444]">{m.size_gb}GB</span> : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Model selection */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">AI Models</h3>
          <span className="text-[10px] text-[#444] ml-auto">Only one loads at a time</span>
        </div>
        <div className="space-y-4">
          <ModelPicker
            label="Reasoning Model"
            desc="Used for chat, quiz, explanations, notes, study plans — everything"
            value={config.reasoning_model || 'qwen3:8b'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'reasoning')}
            onChange={v => setConfig(c => ({ ...c, reasoning_model: v }))}
          />
          <ModelPicker
            label="Vision Model"
            desc="Only loaded when you attach an image — reads worksheets, diagrams, handwriting"
            value={config.vision_model || 'qwen2.5vl:3b'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'vision')}
            onChange={v => setConfig(c => ({ ...c, vision_model: v }))}
          />
          <ModelPicker
            label="Fallback Model"
            desc="Used if reasoning model fails or is too slow"
            value={config.fallback_model || 'llama3.2:3b'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'fallback')}
            onChange={v => setConfig(c => ({ ...c, fallback_model: v }))}
          />
          <ModelPicker
            label="Coding Model"
            desc="Used when your son asks about Python, JavaScript, algorithms"
            value={config.coding_model || 'qwen2.5-coder:7b'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'coding')}
            onChange={v => setConfig(c => ({ ...c, coding_model: v }))}
/>
          <ModelPicker
           label="PowerPoint Model"
           desc="Used for generating presentations"
           value={config.pptx_model || 'qwen3:8b'}
           installed={modelNames}
           recommended={RECOMMENDED.filter(m => m.role === 'pptx')}
           onChange={v => setConfig(c => ({ ...c, pptx_model: v }))}
/>
        </div>
      </div>

      {/* Image generation */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <HardDrive size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Image Generation</h3>
        </div>
        <div className="bg-green-500/8 border border-green-500/20 rounded-lg p-3 mb-3">
          <p className="text-xs text-green-400 font-medium mb-1">✅ Pollinations.ai (recommended for M4)</p>
          <p className="text-[10px] text-[#555]">
            Free · No GPU needed · No disk space · No install · Uses internet
          </p>
        </div>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-[#666] mb-1 block">Image quality</label>
            <div className="flex gap-2">
              {[['flux', '🎨 High Quality'], ['turbo', '⚡ Fast']].map(([val, label]) => (
                <button key={val}
                  onClick={() => setConfig(c => ({ ...c, pollinations_model: val }))}
                  className={`flex-1 py-2 rounded-lg text-xs transition-colors ${
                    (config.pollinations_model || 'flux') === val
                      ? 'bg-[#7c6af7] text-white'
                      : 'bg-[#1e1e1e] border border-[#2a2a2a] text-[#777] hover:text-[#aaa]'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Student settings */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <h3 className="text-sm font-medium text-[#e8e8e8] mb-4">Student</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-[#666] mb-1.5 block">Name</label>
            <input value={config.student_name || ''}
              onChange={e => setConfig(c => ({ ...c, student_name: e.target.value }))}
              className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50" />
          </div>
          <div>
            <label className="text-xs text-[#666] mb-1.5 block">Age</label>
            <input type="number" value={config.student_age || 13}
              onChange={e => setConfig(c => ({ ...c, student_age: +e.target.value }))}
              className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50" />
          </div>
        </div>
      </div>

      {/* Feature toggles */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <h3 className="text-sm font-medium text-[#e8e8e8] mb-3">Features</h3>
        <div className="space-y-3">
          {[
            ['web_search_enabled', 'Web Search',     'Search the web for current info (needs internet)'],
            ['voice_enabled',      'Voice Input',    'Microphone speech-to-text'],
            ['memory_enabled',     'Memory',         'Remember past conversations (uses ~50MB disk)'],
            ['image_gen_enabled',  'Image Generation','Generate images via Pollinations.ai (needs internet)'],
          ].map(([key, label, desc]) => (
            <ToggleRow key={key}
              label={label} desc={desc}
              value={config[key] !== false}
              onChange={v => setConfig(c => ({ ...c, [key]: v }))} />
          ))}
        </div>
      </div>

      {/* Memory management */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <h3 className="text-sm font-medium text-[#e8e8e8] mb-2">Memory</h3>
        <p className="text-xs text-[#444] mb-3">
          Conversations and study progress are saved to <code className="text-[#666]">~/.aria_data/</code>
        </p>
        <button onClick={handleClearMemory} disabled={clearing}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/8 border border-red-500/15 text-red-400 hover:bg-red-500/15 text-xs transition-colors disabled:opacity-50">
          <Trash2 size={13} />
          {clearing ? 'Clearing...' : 'Clear All Memory & Profiles'}
        </button>
      </div>

      {/* Save */}
      <button onClick={save} disabled={saving}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-60 transition-colors">
        {saved ? <><Check size={14} /> Saved!</> : saving ? 'Saving...' : 'Save Settings'}
      </button>
    </div>
  )
}

function StatusRow({ label, ok, desc }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${ok ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
      <span className="text-xs text-[#aaa] w-32 flex-shrink-0">{label}</span>
      <span className="text-xs text-[#555]">{desc}</span>
    </div>
  )
}

function ModelPicker({ label, desc, value, installed, recommended, onChange }) {
  return (
    <div>
      <label className="text-xs text-[#888] font-medium block mb-0.5">{label}</label>
      <p className="text-[10px] text-[#444] mb-2">{desc}</p>
      <div className="space-y-1.5 mb-2">
        {recommended.map(m => (
          <button key={m.name} onClick={() => onChange(m.name)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-left transition-colors border ${
              value === m.name
                ? 'border-[#7c6af7]/50 bg-[#7c6af7]/8 text-[#a89bf8]'
                : 'border-[#1e1e1e] bg-[#0f0f0f] text-[#666] hover:border-[#2a2a2a] hover:text-[#aaa]'
            }`}>
            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${installed.some(i => i.includes(m.name.split(':')[0])) ? 'bg-green-400' : 'bg-[#333]'}`} />
            <span className="font-mono flex-1">{m.name}</span>
            <span className="text-[10px] opacity-60">{m.disk} disk · {m.ram} RAM</span>
            <span className="text-[10px] opacity-50">{m.note}</span>
          </button>
        ))}
      </div>
      {/* Manual input for other models */}
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder="or type any model name"
        className="w-full bg-[#0f0f0f] border border-[#1e1e1e] rounded-lg px-3 py-1.5 text-xs text-[#777] font-mono outline-none focus:border-[#7c6af7]/40 placeholder-[#333]" />
    </div>
  )
}

function ToggleRow({ label, desc, value, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-xs text-[#aaa]">{label}</p>
        <p className="text-[10px] text-[#444]">{desc}</p>
      </div>
      <button onClick={() => onChange(!value)}
        className={`w-10 h-5 rounded-full transition-colors relative flex-shrink-0 ${value ? 'bg-[#7c6af7]' : 'bg-[#2a2a2a]'}`}>
        <div className={`w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 transition-all ${value ? 'left-5' : 'left-0.5'}`} />
      </button>
    </div>
  )
}
