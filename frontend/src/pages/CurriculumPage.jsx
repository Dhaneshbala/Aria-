import { useState, useEffect } from 'react'
import { BookOpen, Search, ChevronDown, ChevronRight, GraduationCap, Layers, ArrowRight } from 'lucide-react'
import { showToast } from '../components/Toast'

const AGE_RANGE = Array.from({ length: 15 }, (_, i) => i + 4)

export default function CurriculumPage() {
  const [stages, setStages] = useState({})
  const [klas, setKlas] = useState({})
  const [age, setAge] = useState(12)
  const [selectedKla, setSelectedKla] = useState('')
  const [subjectData, setSubjectData] = useState(null)
  const [hscSubjects, setHscSubjects] = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [progression, setProgression] = useState(null)
  const [progressionKla, setProgressionKla] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadInitial() }, [])

  const loadInitial = async () => {
    setLoading(true)
    try {
      const [s, k, h] = await Promise.all([
        fetch('/api/v2/curriculum/stages').then(r => r.json()),
        fetch('/api/v2/curriculum/klas').then(r => r.json()),
        fetch('/api/v2/curriculum/hsc').then(r => r.json()),
      ])
      setStages(s)
      setKlas(k)
      setHscSubjects(h)
      const firstKla = Object.keys(k)[0]
      if (firstKla) setSelectedKla(firstKla)
    } catch (e) {
      showToast('Failed to load curriculum data', 'error')
    }
    setLoading(false)
  }

  useEffect(() => {
    if (selectedKla) loadSubjectContent()
  }, [selectedKla, age])

  const loadSubjectContent = async () => {
    if (!selectedKla) return
    const stageForAge = getStageForAge(age)
    try {
      const data = await fetch(`/api/v2/curriculum/subject/${selectedKla}/stage/${stageForAge}`).then(r => r.json())
      setSubjectData(data)
    } catch (e) {
      setSubjectData(null)
    }
  }

  const getStageForAge = (a) => {
    if (a <= 5) return 'ES1'
    if (a <= 7) return 'S1'
    if (a <= 9) return 'S2'
    if (a <= 11) return 'S3'
    if (a <= 14) return 'S4'
    if (a <= 16) return 'S5'
    return 'S6'
  }

  const getStageName = (code) => stages[code]?.name || code

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const data = await fetch(`/api/v2/curriculum/search?q=${encodeURIComponent(searchQuery)}`).then(r => r.json())
      setSearchResults(data)
    } catch (e) {
      showToast('Search failed', 'error')
      setSearchResults([])
    }
    setSearching(false)
  }

  const loadProgression = async (kla) => {
    if (progressionKla === kla && progression) {
      setProgression(null)
      setProgressionKla('')
      return
    }
    setProgressionKla(kla)
    try {
      const data = await fetch(`/api/v2/curriculum/progression/${kla}`).then(r => r.json())
      setProgression(data)
    } catch (e) {
      showToast('Failed to load progression', 'error')
      setProgression(null)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const stageForAge = getStageForAge(age)

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto w-full px-4 py-6 page-enter">
        <div className="flex items-center gap-2 mb-6">
          <BookOpen size={20} className="text-[#7c6af7]" />
          <h1 className="text-lg font-semibold text-[#e8e8e8]">NSW Curriculum Explorer</h1>
        </div>

        {/* Age Selector */}
        <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-4">
          <label className="block text-xs text-[#888] mb-2">Select Age</label>
          <div className="flex items-center gap-4">
            <input
              type="range" min={4} max={18} value={age}
              onChange={e => setAge(Number(e.target.value))}
              className="flex-1 accent-[#7c6af7]"
            />
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-[#7c6af7]">{age}</span>
              <span className="text-xs text-[#666]">years</span>
            </div>
          </div>
          <p className="text-xs text-[#666] mt-2">
            Stage: <span className="text-[#e8e8e8]">{getStageName(stageForAge)}</span> ({stageForAge})
          </p>
        </div>

        {/* Subject Selector */}
        <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-4">
          <label className="block text-xs text-[#888] mb-2">Key Learning Area</label>
          <div className="relative">
            <select
              value={selectedKla}
              onChange={e => setSelectedKla(e.target.value)}
              className="w-full appearance-none bg-[#252540] border border-[#2a2a40] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7] cursor-pointer"
            >
              {Object.entries(klas).map(([key, kla]) => (
                <option key={key} value={key}>{kla.name} ({kla.code})</option>
              ))}
            </select>
            <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#666] pointer-events-none" />
          </div>
        </div>

        {/* Subject Content & Outcomes */}
        {subjectData && (
          <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-4">
            <div className="flex items-center gap-2 mb-3">
              <Layers size={16} className="text-[#7c6af7]" />
              <span className="text-sm font-semibold text-[#e8e8e8]">
                {klas[selectedKla]?.name} — {getStageName(stageForAge)}
              </span>
            </div>

            {subjectData.content?.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-[#888] mb-2 uppercase tracking-wide">Content Areas</p>
                <div className="space-y-2">
                  {subjectData.content.map((c, i) => (
                    <div key={i} className="flex items-start gap-2.5 p-3 rounded-xl bg-[#252540]">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#7c6af7] mt-1.5 flex-shrink-0" />
                      <p className="text-sm text-[#ccc]">{c}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {subjectData.outcomes?.length > 0 && (
              <div>
                <p className="text-xs text-[#888] mb-2 uppercase tracking-wide">Outcomes</p>
                <div className="flex flex-wrap gap-1.5">
                  {subjectData.outcomes.map((o, i) => (
                    <span key={i} className="px-2.5 py-1 rounded-lg bg-[#7c6af7]/10 border border-[#7c6af7]/20 text-xs text-[#a89bf8] font-mono">
                      {o}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {(!subjectData.content || subjectData.content.length === 0) && (!subjectData.outcomes || subjectData.outcomes.length === 0) && (
              <p className="text-xs text-[#555] text-center py-4">No content available for this subject/stage combination</p>
            )}
          </div>
        )}

        {/* Search */}
        <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-4">
          <label className="block text-xs text-[#888] mb-2">Search Curriculum</label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#666]" />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Search topics, keywords..."
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-[#252540] border border-[#2a2a40] text-sm text-[#e8e8e8] placeholder-[#555] outline-none focus:border-[#7c6af7]"
              />
            </div>
            <button onClick={handleSearch} disabled={searching || !searchQuery.trim()}
              className="px-4 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
              {searching ? '...' : 'Search'}
            </button>
          </div>
          {searchResults.length > 0 && (
            <div className="mt-3 space-y-2 max-h-60 overflow-y-auto">
              {searchResults.map((r, i) => (
                <div key={i} className="p-3 rounded-xl bg-[#252540] border border-[#2a2a40]">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 rounded bg-[#7c6af7]/15 text-[#a89bf8] text-[10px] font-medium">{r.kla}</span>
                    <span className="text-[10px] text-[#666]">{r.stage}</span>
                  </div>
                  <p className="text-sm text-[#ccc]">{r.content}</p>
                  {r.outcomes?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {r.outcomes.slice(0, 5).map((o, j) => (
                        <span key={j} className="text-[10px] font-mono text-[#666]">{o}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {searchQuery && !searching && searchResults.length === 0 && (
            <p className="text-xs text-[#555] mt-3 text-center">No results found</p>
          )}
        </div>

        {/* Learning Progression */}
        <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-4">
          <label className="block text-xs text-[#888] mb-2">Learning Progression</label>
          <div className="relative mb-3">
            <select
              value={progressionKla}
              onChange={e => loadProgression(e.target.value)}
              className="w-full appearance-none bg-[#252540] border border-[#2a2a40] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] outline-none focus:border-[#7c6af7] cursor-pointer"
            >
              <option value="">Select a subject to view progression</option>
              {Object.entries(klas).map(([key, kla]) => (
                <option key={key} value={key}>{kla.name}</option>
              ))}
            </select>
            <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#666] pointer-events-none" />
          </div>
          {progression && Object.keys(progression).length > 0 && (
            <div className="space-y-3">
              {Object.entries(progression).map(([stage, data]) => (
                <div key={stage} className="p-3 rounded-xl bg-[#252540] border border-[#2a2a40]">
                  <div className="flex items-center gap-2 mb-2">
                    <ArrowRight size={12} className="text-[#7c6af7]" />
                    <span className="text-xs font-semibold text-[#e8e8e8]">{data.stage_name}</span>
                    <span className="text-[10px] text-[#666]">({stage})</span>
                  </div>
                  {data.content?.length > 0 && (
                    <div className="space-y-1 ml-5">
                      {data.content.map((c, i) => (
                        <p key={i} className="text-xs text-[#aaa]">• {c}</p>
                      ))}
                    </div>
                  )}
                  {data.outcomes?.length > 0 && (
                    <div className="flex flex-wrap gap-1 ml-5 mt-2">
                      {data.outcomes.slice(0, 6).map((o, i) => (
                        <span key={i} className="text-[10px] font-mono text-[#555]">{o}</span>
                      ))}
                      {data.outcomes.length > 6 && (
                        <span className="text-[10px] text-[#555]">+{data.outcomes.length - 6} more</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {progressionKla && progression && Object.keys(progression).length === 0 && (
            <p className="text-xs text-[#555] text-center py-4">No progression data available</p>
          )}
        </div>

        {/* HSC Subjects */}
        {Object.keys(hscSubjects).length > 0 && (
          <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="flex items-center gap-2 mb-3">
              <GraduationCap size={16} className="text-[#f59e0b]" />
              <span className="text-sm font-semibold text-[#e8e8e8]">HSC Subjects (Stage 6)</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(hscSubjects).map(([code, subj]) => (
                <div key={code} className="p-2.5 rounded-xl bg-[#252540] border border-[#2a2a40]">
                  <p className="text-xs font-medium text-[#e8e8e8]">{subj.name}</p>
                  <p className="text-[10px] text-[#666] mt-0.5">{code}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
