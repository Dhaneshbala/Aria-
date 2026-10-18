import { useState, useEffect } from 'react'
import { getConfig, saveConfig, getModels, getHealth, getDiagnostics, unloadModel, clearAllMemory, getUsageSummary } from '../services/api'
import { getWebVitals, clearWebVitals } from '../services/perf'
import { showToast } from '../components/Toast'
import { Settings, Server, Cpu, HardDrive, RefreshCw, Check, Trash2, Zap, BarChart3 } from 'lucide-react'
import { useStore } from '../store'

// 16 GB MacBook Air recommended models — single generation model + embedding
const RECOMMENDED = [
  { name: 'gemma3:12b',    ram: '8-10 GB', disk: '8.1 GB', role: 'main',      note: '⭐ Main model — chat, reasoning, coding, vision, planning' },
  { name: 'nomic-embed-text',  ram: '0.3 GB', disk: '274 MB', role: 'embedding', note: '⭐ Embedding — memory & RAG only (not for chat)' },
  // Legacy — kept available but not required for normal operation
  { name: 'qwen3:8b',          ram: '8 GB',   disk: '5.2 GB', role: 'reasoning', note: 'Legacy reasoning' },
  { name: 'qwen2.5vl:3b',      ram: '4 GB',   disk: '2.2 GB', role: 'vision',    note: 'Legacy vision' },
  { name: 'llama3.2:3b',       ram: '3 GB',   disk: '2.0 GB', role: 'fallback',  note: 'Legacy fallback' },
  { name: 'qwen2.5-coder:7b',  ram: '7 GB',   disk: '4.7 GB', role: 'coding',    note: 'Legacy coding' },
]

export default function AdminPage() {
  const [config, setConfig] = useState({})
  const [models, setModels] = useState([])
  const [health, setHealth] = useState(null)
  const [memory, setMemory] = useState(null)
  const [unloading, setUnloading] = useState(false)
  const [vitals, setVitals] = useState(() => getWebVitals())
  const [usage, setUsage] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [apiToken, setApiToken] = useState(() => {
    try { return localStorage.getItem('aria_api_token') ? '••••••••' : '' } catch { return '' }
  })
  const [hasToken, setHasToken] = useState(() => {
    try { return !!localStorage.getItem('aria_api_token') } catch { return false }
  })

  const saveApiToken = () => {
    // '••••••••' placeholder means "keep what's saved" — only store real input
    if (apiToken && apiToken !== '••••••••') {
      try { localStorage.setItem('aria_api_token', apiToken) } catch {}
      setHasToken(true)
      showToast('Server password saved', 'success', 2500)
    } else if (hasToken) {
      showToast('Password unchanged', 'info', 2000)
    } else {
      showToast('Paste the server password first', 'error', 2500)
    }
    setApiToken('••••••••')
  }

  const clearApiToken = () => {
    try { localStorage.removeItem('aria_api_token') } catch {}
    setApiToken('')
    setHasToken(false)
    showToast('Server password removed', 'success', 2000)
  }
  const { setConfig: setStoreConfig, uiPrefs, setUiPrefs } = useStore()

  useEffect(() => {
    getConfig().then(setConfig).catch((e) => console.warn('admin config failed', e))
    getModels().then(d => setModels(d.models || [])).catch((e) => console.warn('admin models failed', e))
    getHealth().then(setHealth).catch((e) => console.warn('admin health failed', e))
    getUsageSummary(30).then(setUsage).catch((e) => console.warn('usage summary failed', e))
    refreshMemory()
  }, [])

  const refreshMemory = () => {
    getDiagnostics()
      .then(d => setMemory(d?.checks?.memory || null))
      .catch((e) => console.warn('admin memory failed', e))
  }

  const freeRam = async () => {
    setUnloading(true)
    try {
      const main = config.model || config.reasoning_model || 'gemma3:12b'
      const emb = config.embedding_model || 'nomic-embed-text'
      await unloadModel(main).catch(() => ({}))
      await unloadModel(emb).catch(() => ({}))
      showToast('AI models unloaded — ~8 GB freed', 'success', 3000)
      refreshMemory()
    } catch {
      showToast('Unload failed — is Ollama running?', 'error', 3000)
    }
    setUnloading(false)
  }

  const refresh = () => {
    getHealth().then(setHealth).catch((e) => console.warn('admin health failed', e))
    getModels().then(d => setModels(d.models || [])).catch((e) => console.warn('admin models failed', e))
  }

  const save = async () => {
    setSaving(true)
    try {
      const result = await saveConfig(config)
      setStoreConfig(result)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      console.warn('Save settings failed', e)
      showToast('Saving settings failed — check the backend is running', 'error')
    }
    setSaving(false)
  }

  const handleClearMemory = async () => {
    if (!window.confirm('Clear all conversation memory and study profiles? This cannot be undone.')) return
    setClearing(true)
    try {
      await clearAllMemory()
      showToast('Memory cleared successfully.', 'success')
    } catch (e) {
      console.warn('Clear memory failed', e)
      showToast('Could not clear memory — is the backend running?', 'error')
    }
    setClearing(false)
  }

  const modelNames = models.map(m => m.name || m)
  const totalDisk = models.reduce((sum, m) => sum + (m.size_gb || 0), 0)

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter overflow-y-auto h-full">
      <div className="flex items-center gap-2 mb-6">
        <Settings size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Admin Settings</h1>
      </div>

      {/* 16GB Hardware info banner */}
      <div className="bg-[#7c6af7]/8 border border-[#7c6af7]/20 rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap size={14} className="text-[#7c6af7]" />
          <span className="text-xs font-semibold text-[#a89bf8]">Optimised for MacBook Air M4 16 GB — Single Model</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">gemma3:12b</p>
            <p className="text-[10px] text-[#888] mt-0.5">Main (multimodal)</p>
            <p className="text-[10px] text-[#888]">8.1 GB · Vision+Chat+Code</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">nomic-embed-text</p>
            <p className="text-[10px] text-[#888] mt-0.5">Embedding</p>
            <p className="text-[10px] text-[#888]">274 MB · Memory/RAG only</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-green-400 font-semibold">Pollinations.ai</p>
            <p className="text-[10px] text-[#888] mt-0.5">Image Gen</p>
            <p className="text-[10px] text-[#888]">Free · No CPU Or GPU</p>
          </div>
        </div>
        <p className="text-[10px] text-[#888] mt-2 text-center">
          Gemma handles chat, reasoning, math, coding, vision & planning — one model, no swapping. Nomic only for embeddings.
        </p>
      </div>

      {/* System health */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Server size={14} className="text-[#7c6af7]" />
            <h3 className="text-sm font-medium text-[#e8e8e8]">System Status</h3>
          </div>
          <button onClick={refresh} className="text-[#888] hover:text-[#888] transition-colors">
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
              <p className="text-[10px] text-[#888] uppercase tracking-wider">Installed models</p>
              <p className="text-[10px] text-[#888]">~{totalDisk.toFixed(1)} GB used</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {models.map(m => (
                <div key={m.name || m}
                  className="flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full bg-[#1e1e1e] text-[#888]">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                  {m.name || m}
                  {m.size_gb ? <span className="text-[#888]">{m.size_gb}GB</span> : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Model selection — single main model */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">AI Models — Single Model Setup</h3>
          <span className="text-[10px] text-[#888] ml-auto">Gemma does everything</span>
        </div>
        <div className="space-y-4">
          <ModelPicker
            label="Main Model"
            desc="Handles chat, reasoning, tutoring, math, coding, vision, planning — multimodal"
            value={config.model || config.reasoning_model || 'gemma3:12b'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'main')}
            onChange={v => setConfig(c => ({ ...c, model: v, reasoning_model: v, vision_model: v, fallback_model: v, coding_model: v, pptx_model: v }))}
          />
          <ModelPicker
            label="Embedding Model"
            desc="ONLY for memory/RAG retrieval — tiny, never used for chat"
            value={config.embedding_model || 'nomic-embed-text'}
            installed={modelNames}
            recommended={RECOMMENDED.filter(m => m.role === 'embedding')}
            onChange={v => setConfig(c => ({ ...c, embedding_model: v }))}
          />
          <details className="pt-2">
            <summary className="text-xs text-[#888] cursor-pointer hover:text-[#888]">Advanced — legacy model overrides (optional)</summary>
            <div className="space-y-4 mt-3">
              <ModelPicker
                label="Vision Model (optional override)"
                desc="Override only if you have a specialist vision model — otherwise uses Main model"
                value={config.vision_model || config.model || 'gemma3:12b'}
                installed={modelNames}
                recommended={RECOMMENDED.filter(m => m.role === 'vision')}
                onChange={v => setConfig(c => ({ ...c, vision_model: v }))}
              />
              <ModelPicker
                label="Organizer Model (optional)"
                desc="File organizer — leave blank to use Main model"
                value={config.organizer_model || ''}
                installed={modelNames}
                recommended={RECOMMENDED.filter(m => m.role === 'reasoning')}
                onChange={v => setConfig(c => ({ ...c, organizer_model: v }))}
              />
            </div>
          </details>
        </div>
        <p className="text-[10px] text-[#888] mt-3">Legacy Qwen/Llama models still work if installed, but are not required. Changing Main Model updates all roles at once.</p>
      </div>

      {/* Accessibility */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <Settings size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Display &amp; Accessibility</h3>
        </div>
        <p className="text-[10px] text-[#888] mb-3">
          Adjust text size and contrast to make ARIA easier to read. Settings save automatically.
        </p>
        <div className="space-y-3">
          <div>
            <p className="text-xs text-[#888] mb-1">Text size</p>
            <div className="flex gap-2">
              {[['sm', 'Small'], ['md', 'Medium'], ['lg', 'Large']].map(([val, label]) => (
                <button key={val}
                  onClick={() => setUiPrefs({ fontSize: val })}
                  className={`flex-1 py-2 rounded-lg text-xs transition-colors ${
                    uiPrefs.fontSize === val
                      ? 'bg-[#7c6af7] text-white'
                      : 'bg-[#1e1e1e] border border-aria-border text-[#777] hover:text-[#aaa]'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => setUiPrefs({ contrast: !uiPrefs.contrast })}
            className={`w-full py-2 rounded-lg text-xs transition-colors ${
              uiPrefs.contrast
                ? 'bg-[#7c6af7] text-white'
                : 'bg-[#1e1e1e] border border-aria-border text-[#777] hover:text-[#aaa]'
            }`}>
            {uiPrefs.contrast ? '✓ High contrast: ON' : 'High contrast: OFF'}
          </button>
        </div>
      </div>

      {/* Image generation */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <HardDrive size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Image Generation</h3>
        </div>
        <div className="bg-green-500/8 border border-green-500/20 rounded-lg p-3">
          <p className="text-xs text-green-400 font-medium mb-1">✅ Pollinations.ai (recommended for M4)</p>
          <p className="text-[10px] text-[#888]">
            Free · No GPU needed · No disk space · No install · Uses internet
          </p>
        </div>
      </div>

      {/* Memory — the #1 crash cause on 16 GB Macs */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <Cpu size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Memory</h3>
          <button onClick={refreshMemory} aria-label="Refresh memory status"
            className="ml-auto p-1.5 rounded-full text-[#888] hover:text-[#aaa] hover:bg-[#1e1e1e] transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
        <p className="text-[10px] text-[#888] mb-3">
          {memory ? memory.message : 'Checking RAM pressure…'}
          {memory && memory.swap_percent != null && ` · swap ${memory.swap_percent}%`}
        </p>
        <button onClick={freeRam} disabled={unloading}
          className="w-full py-2 rounded-lg bg-[#1e1e1e] border border-aria-border text-xs text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors disabled:opacity-60">
          {unloading ? 'Unloading…' : 'Unload AI models (~8 GB)'}
        </button>
        <p className="text-[10px] text-[#888] mt-2">
          Models reload automatically on next use. Biggest RAM savers: fewer Chrome tabs,
          quit Slack/heavy apps while studying.
        </p>
      </div>

      {/* AI usage ledger — server-side accounting (last 30 days) */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <BarChart3 size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">AI Usage</h3>
          <span className="text-[10px] text-[#888] ml-auto">last 30 days</span>
        </div>
        {usage ? (
          <>
            <div className="grid grid-cols-3 gap-2 mb-2">
              <div className="bg-[#0f0f0f] border border-aria-border rounded-lg p-2 text-center">
                <div className="text-sm font-semibold text-[#e8e8e8]">{usage.totals?.requests ?? 0}</div>
                <div className="text-[10px] text-[#888]">Requests</div>
              </div>
              <div className="bg-[#0f0f0f] border border-aria-border rounded-lg p-2 text-center">
                <div className="text-sm font-semibold text-[#e8e8e8]">
                  {((usage.totals?.prompt_tokens ?? 0) + (usage.totals?.completion_tokens ?? 0)).toLocaleString()}
                </div>
                <div className="text-[10px] text-[#888]">Tokens</div>
              </div>
              <div className="bg-[#0f0f0f] border border-aria-border rounded-lg p-2 text-center">
                <div className="text-sm font-semibold text-[#e8e8e8]">
                  {usage.totals?.estimated_cost_usd > 0 ? `$${usage.totals.estimated_cost_usd.toFixed(2)}` : '$0'}
                </div>
                <div className="text-[10px] text-[#888]">Est. cost</div>
              </div>
            </div>
            <p className="text-[10px] text-[#888]">
              Token counts are reported by the model server (exact). Costs are estimates from
              config — local Ollama inference is free. Failures:{' '}
              {usage.totals?.failures ?? 0}
            </p>
          </>
        ) : (
          <p className="text-[10px] text-[#888]">No usage recorded yet — it fills in as ARIA answers.</p>
        )}
      </div>

      {/* Performance — real-device Web Vitals ring buffer */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <Zap size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Performance</h3>
          <button onClick={() => { clearWebVitals(); setVitals([]) }} aria-label="Clear performance data"
            className="ml-auto p-1.5 rounded-full text-[#888] hover:text-[#aaa] hover:bg-[#1e1e1e] transition-colors">
            <Trash2 size={13} />
          </button>
        </div>
        {vitals.length === 0 ? (
          <p className="text-[10px] text-[#888]">No measurements yet — browse the app and they appear here (LCP/INP/CLS).</p>
        ) : (
          <div className="space-y-1">
            {vitals.slice(-8).reverse().map((v, i) => (
              <div key={`${v.ts}-${i}`} className="flex items-center gap-2 text-[11px]">
                <span className="font-mono text-[#888] w-10">{v.name}</span>
                <span className="text-[#e8e8e8]">{v.value}{v.name === 'CLS' ? '' : 'ms'}</span>
                <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] ${
                  v.rating === 'good' ? 'bg-green-500/10 text-green-400'
                  : v.rating === 'needs-improvement' ? 'bg-amber-500/10 text-amber-400'
                  : 'bg-red-500/10 text-red-400'}`}>
                  {v.rating}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Remote access — server password for LAN/shared hosting */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <Server size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Remote Access</h3>
        </div>
        <p className="text-[10px] text-[#888] mb-3">
          Only needed when the backend sets <code className="font-mono">ARIA_API_TOKEN</code> and
          you connect over the network (not localhost). Stored in this browser only.
        </p>
            <label htmlFor="aria-server-password" className="text-xs text-[#888] mb-1.5 block">Server password</label>
        <div className="flex gap-2">
          <input
            type="password"
            value={apiToken}
            onChange={e => setApiToken(e.target.value)}
            onFocus={() => { if (apiToken === '••••••••') setApiToken('') }}
            placeholder={hasToken ? '•••••••• (saved)' : 'Paste server password'}
            aria-label="Server password"
            id="aria-server-password"
            className="flex-1 bg-[#0f0f0f] border border-aria-border rounded-lg px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50" />
          <button onClick={saveApiToken}
            className="px-4 py-2 rounded-lg bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-xs font-medium transition-colors">
            Save
          </button>
          {hasToken && (
            <button onClick={clearApiToken} aria-label="Remove saved server password"
              className="px-3 py-2 rounded-lg bg-[#1e1e1e] border border-aria-border text-[#777] hover:text-[#aaa] transition-colors">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Student settings — grade is the source of truth for grade-locking */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <h3 className="text-sm font-medium text-[#e8e8e8] mb-1">Student</h3>
        <p className="text-[10px] text-[#888] mb-4">
          🔒 ARIA is locked to this grade — chat, quizzes, worksheets and visuals are all built
          for it only. To see younger or older content, change the grade here first.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="aria-student-name" className="text-xs text-[#888] mb-1.5 block">Name</label>
            <input id="aria-student-name" value={config.student_name || ''}
              onChange={e => setConfig(c => ({ ...c, student_name: e.target.value }))}
              className="w-full bg-[#0f0f0f] border border-aria-border rounded-lg px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50" />
          </div>
          <div>
            <label htmlFor="aria-student-grade" className="text-xs text-[#888] mb-1.5 block">Grade</label>
            <select
              id="aria-student-grade"
              value={config.student_grade || 'Year 7'}
              onChange={e => {
                const year = parseInt(String(e.target.value).replace(/\D/g, ''), 10) || 7
                setConfig(c => ({ ...c, student_grade: `Year ${year}`, student_age: year + 6 }))
              }}
              className="w-full bg-[#0f0f0f] border border-aria-border rounded-lg px-3 py-2 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50">
              {Array.from({ length: 12 }, (_, i) => i + 1).map(y => (
                <option key={y} value={`Year ${y}`}>Year {y}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="text-[10px] text-[#888] mt-2">
          Age auto-syncs to grade (Year {parseInt(String(config.student_grade || 'Year 7').replace(/\D/g, ''), 10) || 7} ≈ age {(parseInt(String(config.student_grade || 'Year 7').replace(/\D/g, ''), 10) || 7) + 6}).
          Changing grade re-customises all of ARIA — save below to apply.
        </p>
      </div>

      {/* Feature toggles */}
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
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
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <h3 className="text-sm font-medium text-[#e8e8e8] mb-2">Memory</h3>
        <p className="text-xs text-[#888] mb-3">
          Conversations and study progress are saved to <code className="text-[#888]">~/.aria_data/</code>
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
      <span className="text-xs text-[#888]">{desc}</span>
    </div>
  )
}

function ModelPicker({ label, desc, value, installed, recommended, onChange }) {
  return (
    <div>
      <label className="text-xs text-[#888] font-medium block mb-0.5">{label}</label>
      <p className="text-[10px] text-[#888] mb-2">{desc}</p>
      <div className="space-y-1.5 mb-2">
        {recommended.map(m => (
          <button key={m.name} onClick={() => onChange(m.name)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-left transition-colors border ${
              value === m.name
                ? 'border-[#7c6af7]/50 bg-[#7c6af7]/8 text-[#a89bf8]'
                : 'border-[#1e1e1e] bg-[#0f0f0f] text-[#888] hover:border-aria-border hover:text-[#aaa]'
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
        <p className="text-[10px] text-[#888]">{desc}</p>
      </div>
      <button onClick={() => onChange(!value)}
        className={`w-10 h-5 rounded-full transition-colors relative flex-shrink-0 ${value ? 'bg-[#7c6af7]' : 'bg-[#2a2a2a]'}`}>
        <div className={`w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 transition-all ${value ? 'left-5' : 'left-0.5'}`} />
      </button>
    </div>
  )
}
