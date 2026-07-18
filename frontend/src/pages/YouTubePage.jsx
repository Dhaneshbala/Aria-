import { useState } from 'react'
import { processYouTube, generateQuiz, generateFlashcards } from '../services/api'
import { showToast } from '../components/Toast'
import { Youtube, FileText, BookOpen, CreditCard, Info, ExternalLink } from 'lucide-react'

export default function YouTubePage() {
  const [url, setUrl] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('summary')
  const [quiz, setQuiz] = useState(null)
  const [flashcards, setFlashcards] = useState(null)
  const [loadingExtra, setLoadingExtra] = useState('')

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
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-2">
        <Youtube size={20} className="text-red-400" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">YouTube Analyser</h1>
      </div>
      <p className="text-xs text-[#444] mb-6">
        Paste any YouTube URL — works with or without captions
      </p>

      <div className="flex gap-2 mb-6">
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && process()}
          placeholder="Paste a YouTube URL..."
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
        />
        <button onClick={process} disabled={!url.trim() || loading}
          className="px-5 py-2.5 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
          {loading ? 'Analysing...' : 'Analyse'}
        </button>
      </div>

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
          {/* Video info card */}
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center flex-shrink-0">
                <Youtube size={18} className="text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-[#e8e8e8] font-medium text-sm">{result.title}</h2>
                <p className="text-xs text-[#555] mt-0.5">
                  {result.channel && <>{result.channel} · </>}
                  {result.duration_minutes > 0 && <>{result.duration_minutes} min · </>}
                  <a href={result.url} target="_blank" rel="noreferrer"
                    className="text-[#7c6af7] hover:underline inline-flex items-center gap-1">
                    Watch on YouTube <ExternalLink size={10} />
                  </a>
                </p>
              </div>
            </div>

            {/* Transcript status */}
            {!result.has_transcript && (
              <div className="mt-3 flex items-start gap-2 bg-[#1a1a1a] rounded-lg px-3 py-2">
                <Info size={13} className="text-[#7c6af7] mt-0.5 flex-shrink-0" />
                <p className="text-xs text-[#666]">
                  No captions available for this video. Summary and study tools are generated from the
                  video title and description.
                </p>
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
              result.transcript && ['transcript', <FileText size={13} />, 'Transcript'],
              ['summary', <Info size={13} />, 'Summary'],
              quiz && ['quiz', <BookOpen size={13} />, 'Quiz'],
              flashcards && ['flashcards', <CreditCard size={13} />, 'Flashcards'],
            ].filter(Boolean).map(([id, icon, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  tab === id ? 'bg-[#7c6af7] text-white' : 'text-[#888] hover:text-[#e8e8e8]'
                }`}>
                {icon} {label}
              </button>
            ))}
          </div>

          {/* Tab: Transcript */}
          {tab === 'transcript' && result.transcript && (
            <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 max-h-96 overflow-y-auto">
              <p className="text-sm text-[#aaa] leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
            </div>
          )}

          {/* Tab: Summary (always available) */}
          {tab === 'summary' && (
            <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 space-y-3">
              <h3 className="text-sm font-medium text-[#e8e8e8]">Video Summary</h3>
              <div className="space-y-2 text-sm text-[#aaa] leading-relaxed">
                <p><span className="text-[#7c6af7] font-medium">Title:</span> {result.title}</p>
                {result.channel && <p><span className="text-[#7c6af7] font-medium">Channel:</span> {result.channel}</p>}
                {result.duration_minutes > 0 && <p><span className="text-[#7c6af7] font-medium">Duration:</span> {result.duration_minutes} minutes</p>}
                {result.description && (
                  <div>
                    <p className="text-[#7c6af7] font-medium mb-1">Description:</p>
                    <p className="text-[#888] whitespace-pre-wrap">{result.description}</p>
                  </div>
                )}
                {result.has_transcript && (
                  <div>
                    <p className="text-[#7c6af7] font-medium mb-1">Transcript excerpt:</p>
                    <p className="text-[#888]">{result.transcript.slice(0, 500)}...</p>
                  </div>
                )}
              </div>
              {!result.has_transcript && (
                <p className="text-xs text-[#444] border-t border-[#1e1e1e] pt-3">
                  Tip: Generate a Quiz or Flashcards above to create study materials from this video's content.
                </p>
              )}
            </div>
          )}

          {/* Tab: Quiz */}
          {tab === 'quiz' && quiz && (
            <div className="space-y-3">
              {quiz.map((q, i) => (
                <div key={i} className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4">
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

          {/* Tab: Flashcards */}
          {tab === 'flashcards' && flashcards && (
            <div className="grid grid-cols-2 gap-3">
              {flashcards.map((c, i) => (
                <div key={i} className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-3">
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
  )
}
