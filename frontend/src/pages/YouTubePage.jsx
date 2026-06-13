import { useState } from 'react'
import { processYouTube, generateQuiz, generateFlashcards } from '../services/api'
import { Youtube, FileText, BookOpen, CreditCard } from 'lucide-react'

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
    try {
      const data = await processYouTube(url)
      setResult(data)
    } catch (e) {
      setResult({ error: e.message })
    }
    setLoading(false)
  }

  const makeQuiz = async () => {
    if (!result?.title) return
    setLoadingExtra('quiz')
    const topic = `${result.title}: ${result.transcript?.slice(0, 300)}`
    try {
      const data = await generateQuiz(topic, 'medium', 5)
      setQuiz(data.questions)
      setTab('quiz')
    } catch {}
    setLoadingExtra('')
  }

  const makeFlashcards = async () => {
    if (!result?.title) return
    setLoadingExtra('flashcards')
    const topic = `${result.title}: ${result.transcript?.slice(0, 500)}`
    try {
      const data = await generateFlashcards(topic, 8)
      setFlashcards(data.cards)
      setTab('flashcards')
    } catch {}
    setLoadingExtra('')
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <Youtube size={20} className="text-red-400" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">YouTube Analyser</h1>
      </div>

      <div className="flex gap-2 mb-6">
        <input
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && process()}
          placeholder="Paste a YouTube URL..."
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50"
        />
        <button onClick={process} disabled={!url.trim() || loading}
          className="px-5 py-2.5 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40">
          Analyse
        </button>
      </div>

      {loading && (
        <div className="flex flex-col items-center py-12 gap-3">
          <div className="w-8 h-8 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-[#888] text-sm">Fetching transcript...</p>
        </div>
      )}

      {result?.error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-400">
          {result.error}
          <p className="text-xs mt-1 text-red-400/60">Make sure the video has captions/subtitles enabled.</p>
        </div>
      )}

      {result && !result.error && (
        <div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 mb-4">
            <h2 className="text-[#e8e8e8] font-medium">{result.title}</h2>
            <p className="text-xs text-[#555] mt-1">{result.duration_minutes} min · <a href={result.url} target="_blank" rel="noreferrer" className="text-[#7c6af7] hover:underline">Watch on YouTube</a></p>
          </div>

          {/* Actions */}
          <div className="flex gap-2 mb-4">
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
          <div className="flex gap-1 mb-4 bg-[#1a1a1a] p-1 rounded-xl w-fit">
            {[
              ['transcript', <FileText size={13} />, 'Transcript'],
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

          {tab === 'transcript' && (
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 max-h-96 overflow-y-auto">
              <p className="text-sm text-[#aaa] leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
            </div>
          )}

          {tab === 'quiz' && quiz && (
            <div className="space-y-3">
              {quiz.map((q, i) => (
                <div key={i} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
                  <p className="text-sm text-[#e8e8e8] mb-2">Q{i+1}: {q.question}</p>
                  {q.options.map((opt, j) => (
                    <p key={j} className={`text-xs py-1 ${['A','B','C','D'][j] === q.correct ? 'text-green-400' : 'text-[#777]'}`}>
                      {['A','B','C','D'][j]}) {opt}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}

          {tab === 'flashcards' && flashcards && (
            <div className="grid grid-cols-2 gap-3">
              {flashcards.map((c, i) => (
                <div key={i} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-3">
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
