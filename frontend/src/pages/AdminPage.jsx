import { useState, useEffect } from 'react'
import { getConfig, saveConfig, getModels, getHealth, getVoiceStatus, clearAllMemory, createBackup, listBackups, downloadBackup, deleteBackup, restoreBackup, pullModel, unloadModel } from '../services/api'
import { showToast } from '../components/Toast'
import ConfirmModal from '../components/ui/ConfirmModal'
import { Settings, Server, Cpu, HardDrive, RefreshCw, Check, Trash2, Zap, Info } from 'lucide-react'
import { useStore } from '../store'

// 16 GB MacBook Air recommended models — single generation model + embedding
const RECOMMENDED = [
  { name: 'gemma4:e4b-mlx',    ram: '5-6 GB', disk: '5-6 GB', role: 'main',      note: '⭐ Main model — chat, reasoning, coding, vision, planning' },
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
  const [voice, setVoice] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [confirm, setConfirm] = useState(null) // {title, body, confirmLabel, run}
  const { setConfig: setStoreConfig, uiPrefs, setUiPrefs } = useStore()

  useEffect(() => {
    getConfig().then(setConfig).catch(() => {})
    getModels().then(d => setModels(d.models || [])).catch(() => {})
    getHealth().then(setHealth).catch(() => {})
    getVoiceStatus().then(setVoice).catch(() => {})
  }, [])

  const refresh = () => {
    getHealth().then(setHealth).catch(() => {})
    getModels().then(d => setModels(d.models || [])).catch(() => {})
    getVoiceStatus().then(setVoice).catch(() => {})
  }

  // Day 48: one-line voice summary for System Status (null-safe pre-load)
  const voiceDesc = (() => {
    if (!voice) return 'Loading voice engines…'
    const engines = voice.tts_engines || {}
    const piper = Object.entries(engines).filter(([, e]) => e === 'piper').map(([c]) => c)
    const cache = voice.tts_cache
    const cacheBit = cache ? ` · TTS cache ${cache.entries}/${cache.max_entries}` : ''
    if (!piper.length) return `macOS voices only — run fetch_piper_voices.py for neural TTS${cacheBit}`
    return `Neural: ${piper.join(', ')} · macOS fallback for the rest${cacheBit}`
  })()

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
    setClearing(true)
    try {
      await clearAllMemory()
      showToast('Memory cleared successfully.', 'success')
    } catch {}
    setClearing(false)
    setConfirm(null)
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
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">gemma4:e4b-mlx</p>
            <p className="text-[10px] text-[#555] mt-0.5">Main (multimodal)</p>
            <p className="text-[10px] text-[#444]">5-6 GB · Vision+Chat+Code</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-[#7c6af7] font-semibold">nomic-embed-text</p>
            <p className="text-[10px] text-[#555] mt-0.5">Embedding</p>
            <p className="text-[10px] text-[#444]">274 MB · Memory/RAG only</p>
          </div>
          <div className="bg-[#0f0f0f] rounded-lg p-2">
            <p className="text-xs text-green-400 font-semibold">Pollinations.ai</p>
            <p className="text-[10px] text-[#555] mt-0.5">Image Gen</p>
            <p className="text-[10px] text-[#444]">Free · No CPU Or GPU</p>
          </div>
        </div>
        <p className="text-[10px] text-[#444] mt-2 text-center">
          Gemma handles chat, reasoning, math, coding, vision & planning — one model, no swapping. Nomic only for embeddings.
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
          <StatusRow label="Voice"
            ok
            desc={voiceDesc} />
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

      {/* Model selection — single main model */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">AI Models — Single Model Setup</h3>
          <span className="text-[10px] text-[#444] ml-auto">Gemma does everything</span>
        </div>
        <div className="space-y-4">
          <ModelPicker
            label="Main Model"
            desc="Handles chat, reasoning, tutoring, math, coding, vision, planning — multimodal"
            value={config.model || config.reasoning_model || 'gemma4:e4b-mlx'}
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
            <summary className="text-xs text-[#666] cursor-pointer hover:text-[#888]">Advanced — legacy model overrides (optional)</summary>
            <div className="space-y-4 mt-3">
              <ModelPicker
                label="Vision Model (optional override)"
                desc="Override only if you have a specialist vision model — otherwise uses Main model"
                value={config.vision_model || config.model || 'gemma4:e4b-mlx'}
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
        <p className="text-[10px] text-[#555] mt-3">Legacy Qwen/Llama models still work if installed, but are not required. Changing Main Model updates all roles at once.</p>
      </div>

      {/* Accessibility */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <Settings size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Display &amp; Accessibility</h3>
        </div>
        <p className="text-[10px] text-[#555] mb-3">
          Adjust text size and contrast to make Study Buddy easier to read. Settings save automatically.
        </p>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-[#666] mb-1 block">Text size</label>
            <div className="flex gap-2">
              {[['sm', 'Small'], ['md', 'Medium'], ['lg', 'Large']].map(([val, label]) => (
                <button key={val}
                  onClick={() => setUiPrefs({ fontSize: val })}
                  className={`flex-1 py-2 rounded-lg text-xs transition-colors ${
                    uiPrefs.fontSize === val
                      ? 'bg-[#7c6af7] text-white'
                      : 'bg-[#1e1e1e] border border-[#2a2a2a] text-[#777] hover:text-[#aaa]'
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
                : 'bg-[#1e1e1e] border border-[#2a2a2a] text-[#777] hover:text-[#aaa]'
            }`}>
            {uiPrefs.contrast ? '✓ High contrast: ON' : 'High contrast: OFF'}
          </button>
        </div>
      </div>

      {/* Image generation */}
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <HardDrive size={14} className="text-[#7c6af7]" />
          <h3 className="text-sm font-medium text-[#e8e8e8]">Image Generation</h3>
        </div>
        <div className="bg-green-500/8 border border-green-500/20 rounded-lg p-3">
          <p className="text-xs text-green-400 font-medium mb-1">✅ Pollinations.ai (recommended for M4)</p>
          <p className="text-[10px] text-[#555]">
            Free · No GPU needed · No disk space · No install · Uses internet
          </p>
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
        <button onClick={() => setConfirm({
          title: 'Clear all memory?',
          body: 'This clears all conversation memory and study profiles. This cannot be undone.',
          confirmLabel: 'Clear everything',
          run: handleClearMemory,
        })} disabled={clearing}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/8 border border-red-500/15 text-red-400 hover:bg-red-500/15 text-xs transition-colors disabled:opacity-50">
          <Trash2 size={13} />
          {clearing ? 'Clearing...' : 'Clear All Memory & Profiles'}
        </button>
      </div>

      {/* Backup / Restore */}
      <AdminBackupSection />

      {/* Model Management */}
      <AdminModelSection models={models} installed={models} />

      {/* Save */}
      <button onClick={save} disabled={saving}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-60 transition-colors">
        {saved ? <><Check size={14} /> Saved!</> : saving ? 'Saving...' : 'Save Settings'}
      </button>
      <ConfirmModal
        open={confirm !== null}
        title={confirm?.title || 'Are you sure?'}
        body={confirm?.body || ''}
        confirmLabel={confirm?.confirmLabel || 'Confirm'}
        onConfirm={() => confirm?.run?.()}
        onCancel={() => setConfirm(null)}
      />
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

function AdminBackupSection() {
  const [backups, setBackups] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [confirm, setConfirm] = useState(null) // {title, body, confirmLabel, run}
  const fileRef = useState(null)

  useEffect(() => {
    listBackups().then(b => setBackups(Array.isArray(b) ? b : b?.backups || [])).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    setCreating(true)
    try {
      await createBackup(false)
      showToast('Backup created', 'success', 2500)
      const b = await listBackups()
      setBackups(Array.isArray(b) ? b : b?.backups || [])
    } catch (e) { showToast('Backup failed: ' + e.message, 'error') }
    setCreating(false)
  }

  const handleRestore = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setConfirm({
      title: 'Restore backup?',
      body: 'Restore will overwrite current data. Continue?',
      confirmLabel: 'Restore',
      run: async () => {
        setConfirm(null)
        setRestoring(true)
        try {
          await restoreBackup(file)
          showToast('Restored! Refresh the page.', 'success', 5000)
        } catch (err) { showToast('Restore failed: ' + err.message, 'error') }
        setRestoring(false)
      },
    })
  }

  const handleDelete = async (name) => {
    setConfirm({
      title: `Delete backup "${name}"?`,
      body: 'The backup file will be permanently removed.',
      confirmLabel: 'Delete',
      run: async () => {
        setConfirm(null)
        try {
          await deleteBackup(name)
          setBackups(prev => prev.filter(b => (b.name || b.filename) !== name))
          showToast('Backup deleted', 'success', 2500)
        } catch (e) { showToast('Delete failed', 'error') }
      },
    })
  }

  return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
      <h3 className="text-sm font-medium text-[#e8e8e8] mb-2">Backup & Restore</h3>
      <p className="text-xs text-[#444] mb-3">Save or restore all your data (conversations, flashcards, settings)</p>
      <div className="flex gap-2 mb-3">
        <button onClick={handleCreate} disabled={creating}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#7c6af7]/15 text-[#a89bf8] hover:bg-[#7c6af7]/25 text-xs transition-colors disabled:opacity-50">
          {creating ? 'Creating…' : 'Create Backup'}
        </button>
        <label className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#2a2a2a] text-[#9aa0a6] hover:text-white text-xs cursor-pointer transition-colors">
          {restoring ? 'Restoring…' : 'Restore from file'}
          <input type="file" className="hidden" accept=".zip" onChange={handleRestore} disabled={restoring} />
        </label>
      </div>
      {loading ? (
        <p className="text-xs text-[#555]">Loading backups…</p>
      ) : backups.length > 0 ? (
        <div className="space-y-1.5">
          {backups.slice(0, 5).map((b, i) => {
            const name = b.name || b.filename || `backup-${i}`
            const size = b.size ? `${(b.size / 1024 / 1024).toFixed(1)} MB` : ''
            const date = b.created || b.date || ''
            return (
              <div key={name} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0f0f0f] border border-[#1e1e1e]">
                <span className="text-xs text-[#aaa] flex-1 truncate">{name}</span>
                {size && <span className="text-[10px] text-[#555]">{size}</span>}
                {date && <span className="text-[10px] text-[#444]">{new Date(date).toLocaleDateString()}</span>}
                <a href={`${window.location.origin}/api/backup/download/${encodeURIComponent(name)}`}
                  className="text-[10px] text-[#8ab4f8] hover:underline">Download</a>
                <button onClick={() => handleDelete(name)} className="text-[10px] text-[#555] hover:text-red-400">×</button>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-xs text-[#444]">No backups yet</p>
      )}
      <ConfirmModal
        open={confirm !== null}
        title={confirm?.title || 'Are you sure?'}
        body={confirm?.body || ''}
        confirmLabel={confirm?.confirmLabel || 'Confirm'}
        onConfirm={() => confirm?.run?.()}
        onCancel={() => setConfirm(null)}
      />
    </div>
  )
}

function AdminModelSection({ models, installed }) {
  const [pulling, setPulling] = useState(null)
  const [pullProgress, setPullProgress] = useState('')
  const [unloading, setUnloading] = useState(null)

  const handlePull = async (name) => {
    setPulling(name)
    setPullProgress('Starting download…')
    try {
      await pullModel(name)
      showToast(`${name} downloaded`, 'success', 3000)
      setPullProgress('')
    } catch (e) { showToast('Pull failed: ' + e.message, 'error'); setPullProgress('') }
    setPulling(null)
  }

  const handleUnload = async (name) => {
    setUnloading(name)
    try {
      await unloadModel(name)
      showToast(`${name} unloaded from RAM`, 'success', 2500)
    } catch (e) { showToast('Unload failed: ' + e.message, 'error') }
    setUnloading(null)
  }

  const installedNames = installed.map(m => m.name || m)

  return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 mb-4">
      <h3 className="text-sm font-medium text-[#e8e8e8] mb-2">Model Management</h3>
      <p className="text-xs text-[#444] mb-3">Download new models or free up RAM</p>
      <div className="space-y-1.5">
        {RECOMMENDED.map(m => {
          const isInstalled = installedNames.includes(m.name)
          const isPulling = pulling === m.name
          return (
            <div key={m.name} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0f0f0f] border border-[#1e1e1e]">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-[#aaa] font-mono truncate">{m.name}</p>
                <p className="text-[10px] text-[#444]">{m.ram} RAM · {m.disk} disk</p>
              </div>
              {isInstalled ? (
                <button onClick={() => handleUnload(m.name)} disabled={unloading === m.name}
                  className="text-[10px] px-2 py-1 rounded-full bg-[#2a2a2a] text-[#9aa0a6] hover:text-white transition-colors disabled:opacity-50">
                  {unloading === m.name ? '…' : 'Unload'}
                </button>
              ) : (
                <button onClick={() => handlePull(m.name)} disabled={isPulling}
                  className="text-[10px] px-2 py-1 rounded-full bg-[#8ab4f8]/15 text-[#8ab4f8] hover:bg-[#8ab4f8]/25 transition-colors disabled:opacity-50">
                  {isPulling ? pullProgress || 'Pulling…' : 'Pull'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
