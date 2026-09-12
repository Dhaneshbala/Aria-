import { useState, useEffect } from 'react'
import { processYouTube, generateQuiz, generateFlashcards } from '../services/api'
import { useStore } from '../store'
import { showToast } from '../components/Toast'
import { Youtube, FileText, BookOpen, CreditCard, Info, ExternalLink } from 'lucide-react'

export default function YouTubePage() {
  const { studyTools, setStudyTool } = useStore()
  const saved = studyTools.youtube
  const [url, setUrl] = useState(saved.url || '')
  const [result, setResult] = useState(saved.result || null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('summary')
  const [quiz, setQuiz] = useState(saved.quiz || null)
  const [flashcards, setFlashcards] = useState(saved.flashcards || null)
  const [loadingExtra, setLoadingExtra] = useState('')

  // Auto-persist to store
  useEffect(() => {
    setStudyTool('youtube', { result, quiz, flashcards, url })
  }, [result, quiz, flashcards, url])

  const process = async () => {
    if (!url.trim()) return
    setLoading(true)
    setResult(null)
    setQuiz(null)
    setFlashcards(null)
    setTab('summary')
    try {
      const data = await processYouTube(url)
      setResult(data)
      if (data.error) {
        showToast(data.error, 'error')
      }
    } catch (e) {
      setResult({ error: e.message })
      showToast('Failed to process video: ' + e.message, 'error')
    }
    setLoading(false)
  }

  const makeQuiz = async () => {
    if (!result?.title) return
    setLoadingExtra('quiz')
    // Use transcript if available, otherwise use title + description
    const context = result.transcript
      ? `${result.title}: ${result.transcript.slice(0, 500)}`
      : `${result.title}. ${result.channel ? 'By ' + result.channel + '. ' : ''}${result.description || ''}`
    try {
      const data = await generateQuiz(context, 'medium', 5)
      setQuiz(data.questions)
      setTab('quiz')
    } catch (e) {
      showToast('Failed to generate quiz: ' + e.message, 'error')
    }
    setLoadingExtra('')
  }

  const makeFlashcards = async () => {
    if (!result?.title) return
    setLoadingExtra('flashcards')
    const context = result.transcript
      ? `${result.title}: ${result.transcript.slice(0, 500)}`
      : `${result.title}. ${result.channel ? 'By ' + result.channel + '. ' : ''}${result.description || ''}`
    try {
      const data = await generateFlashcards(context, 8)
      setFlashcards(data.cards)
      setTab('flashcards')
    } catch (e) {
      showToast('Failed to generate flashcards: ' + e.message, 'error')
    }
    setLoadingExtra('')
  }

  return (
    <div className="w-full min-h-full px-6 lg:px-10 py-8 page-enter">
      <div className="w-full">
        <div className="flex items-center gap-2 mb-2">
          <Youtube size={22} className="text-red-400" />
          <h1 className="text-2xl font-normal text-[#e3e3e3] tracking-tight">YouTube Analyser</h1>
        </div>
        <p className="text-sm text-[#9aa0a6] mb-8">
          Paste any YouTube URL — works with or without captions
        </p>

        <div className="flex gap-3 mb-8 w-full">
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && process()}
            placeholder="Paste a YouTube URL..."
            className="flex-1 bg-[#1e1f20] border border-[#2d2e30] rounded-full px-5 py-3.5 text-[15px] text-[#e3e3e3] placeholder-[#9aa0a6] outline-none focus:border-[#8ab4f8] focus:bg-[#2d2e30]"
          />
          <button onClick={process} disabled={!url.trim() || loading}
            className="px-7 py-3.5 rounded-full bg-[#8ab4f8] hover:bg-[#aecbfa] text-[#062e6f] text-sm font-medium disabled:opacity-40 disabled:bg-[#2d2e30] disabled:text-[#5f6368] transition-colors shrink-0">
            {loading ? 'Analysing...' : 'Analyse'}
          </button>
        </div>
      </div>
      <div className="w-full">

      {loading && (
        <div className="flex flex-col items-center py-12 gap-3">
          <div className="w-8 h-8 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Analysing video...</p>
        </div>
      )}

      {result?.error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-400">
          {result.error}
        </div>
      )}

      {result && !result.error && (
        <div className="space-y-4">
          {/* Video info card — Gemini dark cards */}
          <div className="bg-[#1e1f20] border border-[#2d2e30] rounded-2xl p-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center flex-shrink-0">
                <Youtube size={18} className="text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-[#e3e3e3] font-medium text-[15px]">{result.title}</h2>
                <p className="text-xs text-[#9aa0a6] mt-1">
                  {result.channel && <>{result.channel} · </>}
                  {result.duration_minutes > 0 && <>{result.duration_minutes} min · </>}
                  <a href={result.url} target="_blank" rel="noreferrer"
                    className="text-[#8ab4f8] hover:underline inline-flex items-center gap-1">
                    Watch on YouTube <ExternalLink size={10} />
                  </a>
                </p>
              </div>
            </div>

            {/* Status — captions vs AI inference */}
            <div className="mt-3 flex items-start gap-2 bg-[#1e1f20] border border-[#2d2e30] rounded-lg px-3 py-2.5">
              <Info size={13} className={`${result.has_transcript ? 'text-green-400' : 'text-[#8ab4f8]'} mt-0.5 flex-shrink-0`} />
              <p className="text-xs leading-relaxed text-[#9aa0a6]">
                {result.fallback === 'audio'
                  ? 'Analysed via audio transcription (no captions needed) — summary & quiz below are from spoken content.'
                  : result.has_transcript && result.ai_summary
                    ? 'Analysed — transcript found + AI summary generated.'
                    : result.has_transcript
                      ? 'Captions found — analysis from transcript.'
                      : 'No captions — AI inferred overview from title/description/tags. Quiz & flashcards still work.'}
              </p>
            </div>
            {result.ai_summary && (
              <div className="mt-3 bg-[#131314] border border-[#2d2e30] rounded-xl p-4">
                <p className="text-xs font-medium text-[#8ab4f8] mb-2">AI Analysis</p>
                <p className="text-sm text-[#e3e3e3] leading-relaxed whitespace-pre-wrap">{result.ai_summary}</p>
              </div>
            )}

            {/* Description */}
            {result.description && (
              <div className="mt-3">
                <p className="text-xs text-[#444] mb-1 font-medium">Description:</p>
                <p className="text-xs text-[#666] leading-relaxed whitespace-pre-wrap line-clamp-4">
                  {result.description}
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button onClick={makeQuiz} disabled={loadingExtra === 'quiz'}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors">
              <BookOpen size={13} />
              {loadingExtra === 'quiz' ? 'Generating...' : 'Generate Quiz'}
            </button>
            <button onClick={makeFlashcards} disabled={loadingExtra === 'flashcards'}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#888] hover:text-[#e8e8e8] hover:border-[#7c6af7]/50 transition-colors">
              <CreditCard size={13} />
              {loadingExtra === 'flashcards' ? 'Generating...' : 'Flashcards'}
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 bg-[#111] border border-[#1e1e1e] p-1 rounded-xl w-fit">
            {[
              ...(result.transcript ? [['transcript', 'Transcript']] : []),
              ['summary', 'Summary'],
              ...(quiz ? [['quiz', 'Quiz']] : []),
              ...(flashcards ? [['flashcards', 'Flashcards']] : []),
            ].map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  tab === id ? 'bg-[#7c6af7] text-white' : 'text-[#888] hover:text-[#e8e8e8]'
                }`}>
                {id === 'transcript' ? <FileText size={13} /> : id === 'summary' ? <Info size={13} /> : id === 'quiz' ? <BookOpen size={13} /> : <CreditCard size={13} />}
                {label}
              </button>
            ))}
          </div>

          {/* Tab: Transcript */}
          {tab === 'transcript' && result.transcript && (
            <div className="bg-[#1e1f20] border border-[#2d2e30] rounded-2xl p-5 max-h-96 overflow-y-auto">
              <p className="text-sm text-[#e3e3e3] leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
            </div>
          )}

          {/* Tab: Summary (always available — works without captions) */}
          {tab === 'summary' && (
            <div className="bg-[#1e1f20] border border-[#2d2e30] rounded-2xl p-5 space-y-3">
              <h3 className="text-sm font-medium text-[#e3e3e3]">Video Summary</h3>
              {result.ai_summary ? (
                <p className="text-sm text-[#e3e3e3] leading-relaxed whitespace-pre-wrap">{result.ai_summary}</p>
              ) : (
                <div className="space-y-2 text-sm text-[#aaa] leading-relaxed">
                  <p><span className="text-[#8ab4f8] font-medium">Title:</span> {result.title}</p>
                  {result.channel && <p><span className="text-[#8ab4f8] font-medium">Channel:</span> {result.channel}</p>}
                  {result.duration_minutes > 0 && <p><span className="text-[#8ab4f8] font-medium">Duration:</span> {result.duration_minutes} minutes</p>}
                  {result.description && (
                    <div>
                      <p className="text-[#8ab4f8] font-medium mb-1">Description:</p>
                      <p className="text-[#9aa0a6] whitespace-pre-wrap">{result.description}</p>
                    </div>
                  )}
                  {result.has_transcript && result.transcript && (
                    <div>
                      <p className="text-[#8ab4f8] font-medium mb-1">Transcript excerpt:</p>
                      <p className="text-[#9aa0a6]">{result.transcript.slice(0, 500)}...</p>
                    </div>
                  )}
                </div>
              )}
              <div className="flex flex-wrap gap-2 pt-3 border-t border-[#2d2e30]">
                <button onClick={makeQuiz} className="px-3 py-1.5 rounded-full bg-[#8ab4f8] text-[#062e6f] text-xs font-medium hover:bg-[#aecbfa]">Quiz from video</button>
                <button onClick={makeFlashcards} className="px-3 py-1.5 rounded-full bg-[#2d2e30] text-[#e3e3e3] text-xs hover:bg-[#35363a]">Flashcards</button>
              </div>
            </div>
          )}

          {/* Tab: Quiz */}
          {tab === 'quiz' && quiz && (
            <div className="space-y-3">
              {quiz.map((q, i) => (
                <div key={i} className="bg-[#1e1f20] border border-[#2d2e30] rounded-2xl p-5">
                  <p className="text-sm text-[#e8e8e8] mb-2">Q{i+1}: {q.question}</p>
                  {q.options.map((opt, j) => (
                    <p key={j} className={`text-xs py-1 ${['A','B','C','D'][j] === q.correct ? 'text-green-400 font-medium' : 'text-[#777]'}`}>
                      {['A','B','C','D'][j]}) {opt}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Tab: Flashcards — full width grid */}
          {tab === 'flashcards' && flashcards && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {flashcards.map((c, i) => (
                <div key={i} className="bg-[#1e1f20] border border-[#2d2e30] rounded-2xl p-4">
                  <p className="text-xs text-[#7c6af7] mb-1">Q</p>
                  <p className="text-xs text-[#e8e8e8] mb-2">{c.front}</p>
                  <p className="text-xs text-[#888] border-t border-[#2a2a2a] pt-2">{c.back}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  )
}
