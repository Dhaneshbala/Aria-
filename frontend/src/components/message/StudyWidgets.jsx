/** Structured extras rendered inline in chat (quiz, flashcards, methods, worksheet…). Extracted from Message.jsx. */
import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import MindMapWidget from '../MindMapWidget'
import { checkAnswer, getWeakTopics, bulkAddSrCards } from '../../services/api'
import { showToast } from '../Toast'
import { isSafeUrl } from './shared'
import { Globe, Eye, Youtube, CheckCircle, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
export function ToolResult({ tool }) {
  const [open, setOpen] = useState(false)
  const META = {
    web_search:      { icon: <Globe size={12} />, label: 'Google Search', color: 'text-blue-400' },
    cross_check:     { icon: <Globe size={12} />, label: 'Google Cross-Check', color: 'text-green-400' },
    vision:          { icon: <Eye size={12} />,   label: 'Image Analysis',     color: 'text-purple-400' },
    youtube:         { icon: <Youtube size={12} />, label: 'YouTube Transcript', color: 'text-red-400' },
    todo:            { icon: <CheckCircle size={12} />, label: 'Todo Added', color: 'text-green-400' },
    todos:           { icon: <BookOpen size={12} />, label: 'Your Todos', color: 'text-amber-400' },
    worksheet:       { icon: <BookOpen size={12} />, label: 'Worksheet', color: 'text-purple-400' },
    cheatsheet:      { icon: <BookOpen size={12} />, label: 'Cheat Sheet', color: 'text-amber-400' },
  }
  const meta = META[tool.tool] || { icon: '🔧', label: tool.tool, color: 'text-[#888]' }

  return (
    <div className="border border-[#222] rounded-xl overflow-hidden text-xs">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[#161616] transition-colors">
        <span className={meta.color}>{meta.icon}</span>
        <span className="text-[#666]">{meta.label}</span>
        <span className="ml-auto text-[#444]">{open ? <ChevronUp size={11}/> : <ChevronDown size={11}/>}</span>
      </button>
      {open && (
        <div className="bg-[#111] border-t border-[#222] px-3 py-2 max-h-48 overflow-y-auto">
          {tool.tool === 'web_search' && Array.isArray(tool.content) && tool.content.map((r, i) => (
            <div key={i} className="mb-2 pb-2 border-b border-[#1a1a1a] last:border-0">
              {isSafeUrl(r.url) ? <a href={r.url} target="_blank" rel="noreferrer" className="text-[#7c6af7] hover:underline block">{r.title}</a> : <span className="text-[#7c6af7] block">{r.title}</span>}
              <p className="text-[#555] mt-0.5 leading-relaxed">{r.snippet}</p>
            </div>
          ))}
          {tool.tool === 'cross_check' && Array.isArray(tool.content) && tool.content.map((r, i) => (
            <div key={i} className="mb-2 pb-2 border-b border-[#1a1a1a] last:border-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-[#444] font-mono bg-[#1a1a1a] rounded px-1.5 py-0.5">[{i + 1}]</span>
                {isSafeUrl(r.url) ? <a href={r.url} target="_blank" rel="noreferrer" className="text-green-400 font-medium hover:underline">{r.title}</a> : <span className="text-green-400 font-medium">{r.title}</span>}
              </div>
              <p className="text-[#555] mt-0.5 leading-relaxed">{r.snippet}</p>
            </div>
          ))}
          {tool.tool === 'vision' && (
            <p className="text-[#777] whitespace-pre-wrap leading-relaxed">{tool.content}</p>
          )}
          {tool.tool === 'youtube' && tool.content && (
            <div>
              <p className="text-[#aaa] font-medium">{tool.content.title}</p>
              <p className="text-[#555] mt-1 leading-relaxed line-clamp-4">{tool.content.transcript?.slice(0, 400)}…</p>
            </div>
          )}
          {tool.tool === 'todo' && tool.content && (
            <div className="text-[#aaa]">
              <p className="font-medium text-green-400">{tool.content.subject}: {tool.content.task}</p>
              <p className="text-[#666] mt-1">Due {tool.content.due_date || '—'} · {tool.content.estimated_mins}m · {tool.content.priority}</p>
            </div>
          )}
          {tool.tool === 'todos' && Array.isArray(tool.content) && (
            <div className="space-y-1">
              {tool.content.length === 0 ? <p className="text-[#666]">All caught up!</p> : tool.content.map((t, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-[#1a1a1a] last:border-0">
                  <span className="text-[#aaa] truncate">{t.subject}: {t.task}</span>
                  <span className="text-[10px] text-[#666] ml-2">{t.due_date || ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Extras panel — renders ALL structured content inline ──────────────────────

export function ExtrasPanel({ extras, onSuggest }) {
  if (!extras) return null
  const drill = (topic) => onSuggest && onSuggest(`Quiz me on ${topic} — hard, 5 questions. Drill my mistakes.`)
  return (
    <div className="space-y-3 w-full mt-1">
      {extras.quiz?.length > 0            && <InlineQuiz questions={extras.quiz} label="Quiz" onDrill={drill} />}
      {extras.exam_sim?.length > 0        && <InlineQuiz questions={extras.exam_sim} label="Exam Simulation (Timed)" onDrill={drill} />}
      {extras.practice_quiz?.length > 0   && <InlineQuiz questions={extras.practice_quiz} label="Practice Questions" onDrill={drill} />}
      {extras.flashcards?.length > 0      && <InlineFlashcards cards={extras.flashcards} label="Flashcards" />}
      {extras.mindmap                      && <InlineMindMap data={extras.mindmap} />}
      {extras.methods?.length > 0         && <InlineMethods methods={extras.methods} />}
      {extras.worksheet                    && <InlineWorksheet markdown={extras.worksheet} />}
      {extras.cheatsheet                   && <InlineWorksheet markdown={extras.cheatsheet} title="⚡ Cheat Sheet — print me for the bus" fileName="cheatsheet.md" />}
      {extras.audio_script                 && <InlineAudioScript script={extras.audio_script} />}
      {(extras.quiz || extras.exam_sim || extras.practice_quiz) && <InlineMistakeBank onDrill={drill} />}
    </div>
  )
}

export function InlineMethods({ methods }) {
  const [revealed, setRevealed] = useState(1)
  if (!methods?.length) return null
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">🧮 Step-by-step — {methods.length} methods</span>
        <span className="text-xs text-[#555]">{revealed}/{methods.length} shown</span>
      </div>
      <div className="space-y-3">
        {methods.slice(0, revealed).map((m, i) => (
          <div key={i} className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-3">
            <p className="text-xs font-semibold text-[#e8e8e8] mb-1">Method {m.method}</p>
            <p className="text-xs text-[#aaa] whitespace-pre-wrap leading-relaxed">{m.content}</p>
          </div>
        ))}
      </div>
      {revealed < methods.length && (
        <button onClick={() => setRevealed(r => r + 1)}
          className="mt-3 w-full text-xs py-2 rounded-xl bg-[#7c6af7]/15 text-[#a89bf8] hover:bg-[#7c6af7]/25 transition-colors">
          Show next step → ({revealed + 1}/{methods.length})
        </button>
      )}
      {revealed === methods.length && methods.length > 1 && (
        <p className="text-[11px] text-[#666] mt-2 text-center">All methods shown — pick your favorite!</p>
      )}
    </div>
  )
}

export function InlineAudioScript({ script }) {
  if (!script) return null
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🎧 Audio Overview</span>
      <p className="text-xs text-[#888] whitespace-pre-wrap leading-relaxed">{script.slice(0, 800)}{script.length>800?'…':''}</p>
      <p className="text-[10px] text-[#555] mt-2">Tap Listen below to hear it</p>
    </div>
  )
}

export function InlineMistakeBank({ onDrill }) {
  const [weak, setWeak] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    getWeakTopics().then(d => {
      // API returns {weak_topics: [{topic, accuracy}] } or array
      const list = Array.isArray(d) ? d : (d?.weak_topics || d?.weak_areas || [])
      setWeak(list.slice(0, 3))
    }).catch(() => setWeak([])).finally(() => setLoading(false))
  }, [])
  if (loading) return <div className="text-[11px] text-[#555]">Checking mistake bank…</div>
  if (!weak || weak.length === 0) return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-3">
      <p className="text-xs text-[#666]">No weak topics yet — keep quizzing and Study Buddy will track gaps via <span className="text-[#7c6af7]">find_knowledge_gaps()</span>.</p>
    </div>
  )
  return (
    <div className="bg-[#1a1a1a] border border-amber-500/20 rounded-2xl p-3">
      <p className="text-xs font-semibold text-amber-400 mb-2">📚 Mistake bank — weak topics (from study_intel)</p>
      <div className="space-y-1.5">
        {weak.map((w, i) => (
          <div key={i} className="flex items-center justify-between bg-[#141414] border border-[#2a2a2a] rounded-lg px-3 py-2">
            <div>
              <p className="text-xs text-[#e8e8e8]">{w.topic || w.subject || w.name || 'Topic ' + (i+1)}</p>
              <p className="text-[10px] text-[#666]">{typeof w.accuracy === 'number' ? Math.round(w.accuracy*100)+'% accuracy' : (w.accuracy || '')} {w.attempts ? `· ${w.attempts} attempts` : ''}</p>
            </div>
            <button onClick={() => onDrill && onDrill(w.topic || w.subject || 'general')}
              className="text-[11px] px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-400 hover:bg-amber-500/25">Drill →</button>
          </div>
        ))}
      </div>
      <button onClick={() => onDrill && onDrill(weak[0]?.topic || 'general')}
        className="mt-2 w-full text-xs py-2 rounded-xl bg-[#7c6af7] text-white hover:bg-[#6a59e0]">1-tap drill my mistakes → Quiz on {weak[0]?.topic || 'weakest'}</button>
    </div>
  )
}

// ── Inline Quiz + Mistake Bank ───────────────────────────────────────────────

export function InlineQuiz({ questions, label }) {
  const [idx, setIdx] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const [answers, setAnswers] = useState([])
  const [savedWrong, setSavedWrong] = useState(false)
  const LETTERS = ['A', 'B', 'C', 'D']
  const q = questions[idx]

  const pick = (i) => {
    if (selected !== null) return
    setSelected(i)
    const correct = LETTERS[i] === q.correct
    if (correct) setScore(s => s + 1)
    setAnswers(a => [...a, { correct, question: q.question, options: q.options, correctIdx: q.correct, explanation: q.explanation }])
    try {
      const subj = (label || 'general').toLowerCase().replace(/[^a-z]/g, '') || 'general'
      checkAnswer(subj, correct).catch(() => {})
      checkAnswer('general', correct).catch(() => {})
    } catch {}
  }

  const next = () => {
    if (idx < questions.length - 1) { setIdx(i => i + 1); setSelected(null) }
    else setDone(true)
  }

  const saveWrongAsFlashcards = async () => {
    const wrong = answers.filter(a => !a.correct)
    if (!wrong.length) return
    try {
      const cards = wrong.map(a => ({
        front: a.question,
        back: `${a.options[LETTERS.indexOf(a.correctIdx)]}\n\n${a.explanation || ''}`,
      }))
      await bulkAddSrCards(cards, (label || 'general').toLowerCase().replace(/[^a-z]/g, '') || 'general')
      setSavedWrong(true)
      showToast(`Saved ${cards.length} flashcard${cards.length > 1 ? 's' : ''} for review`, 'success', 2500)
    } catch (e) {
      showToast('Failed to save flashcards', 'error')
    }
  }

  if (done) return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 text-center">
      <div className="text-2xl mb-1">{score === questions.length ? '🏆' : score >= questions.length / 2 ? '👏' : '📚'}</div>
      <p className="text-[#e8e8e8] font-semibold">{score}/{questions.length} correct</p>
      <p className="text-xs text-[#666] mt-1">
        {score === questions.length ? 'Perfect! Brilliant work!' :
         score >= questions.length * 0.7 ? 'Great job!' : 'Keep practising — you\'ll get there!'}
      </p>
      <div className="flex gap-2 mt-3 justify-center">
        <button onClick={() => { setIdx(0); setSelected(null); setScore(0); setDone(false); setAnswers([]); setSavedWrong(false) }}
          className="text-xs px-4 py-1.5 rounded-full bg-[#7c6af7]/20 text-[#a89bf8] hover:bg-[#7c6af7]/30 transition-colors">
          Try Again
        </button>
        {score < questions.length && !savedWrong && (
          <button onClick={saveWrongAsFlashcards}
            className="text-xs px-4 py-1.5 rounded-full bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 transition-colors">
            Save wrong answers as flashcards
          </button>
        )}
        {savedWrong && (
          <span className="text-xs px-4 py-1.5 rounded-full bg-green-500/10 text-green-400">✓ Saved to flashcards</span>
        )}
      </div>
    </div>
  )

  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">📝 {label}</span>
        <span className="text-xs text-[#555]">{idx + 1}/{questions.length} · Score: {score}</span>
      </div>
      {/* Progress bar */}
      <div className="w-full bg-[#2a2a2a] rounded-full h-0.5 mb-3">
        <div className="bg-[#7c6af7] h-0.5 rounded-full transition-all" style={{ width: `${((idx) / questions.length) * 100}%` }} />
      </div>
      <p className="text-sm text-[#e8e8e8] mb-3">{q.question}</p>
      <div className="space-y-2">
        {q.options.map((opt, i) => (
          <button key={i} onClick={() => pick(i)}
            disabled={selected !== null}
            className={`w-full text-left text-xs px-3 py-2.5 rounded-xl border transition-all ${
              selected === null
                ? 'border-[#2a2a2a] hover:border-[#7c6af7]/50 hover:bg-[#7c6af7]/5 text-[#aaa]'
                : LETTERS[i] === q.correct
                  ? 'border-green-500 bg-green-500/10 text-green-300'
                  : selected === i
                    ? 'border-red-500 bg-red-500/10 text-red-400'
                    : 'border-[#1a1a1a] text-[#444]'
            }`}>
            <span className="font-mono opacity-60 mr-2">{LETTERS[i]})</span>{opt}
          </button>
        ))}
      </div>
      {selected !== null && q.explanation && (
        <div className="mt-3 px-3 py-2 bg-[#0f0f0f] border border-[#2a2a2a] rounded-xl text-xs text-[#888]">
          💡 {q.explanation.trim()}
        </div>
      )}
      {selected !== null && (
        <button onClick={next}
          className="mt-3 w-full text-xs py-2 rounded-xl bg-[#7c6af7]/15 text-[#a89bf8] hover:bg-[#7c6af7]/25 transition-colors">
          {idx < questions.length - 1 ? 'Next Question →' : 'See Results →'}
        </button>
      )}
    </div>
  )
}

// ── Inline Flashcards ─────────────────────────────────────────────────────────

export function InlineFlashcards({ cards, label }) {
  const [idx, setIdx] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [known, setKnown] = useState(new Set())
  const [saved, setSaved] = useState(false)
  const card = cards[idx]

  const markKnown = () => {
    setKnown(k => new Set([...k, idx]))
    setFlipped(false)
    setIdx(i => (i + 1) % cards.length)
  }

  const saveAllToSR = async () => {
    try {
      const cardsToSave = cards.map(c => ({ front: c.front, back: c.back }))
      await bulkAddSrCards(cardsToSave, (label || 'general').toLowerCase().replace(/[^a-z]/g, '') || 'general')
      setSaved(true)
      showToast(`${cards.length} flashcard${cards.length > 1 ? 's' : ''} saved for review`, 'success', 2500)
    } catch (e) {
      showToast('Failed to save flashcards', 'error')
    }
  }

  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">🃏 {label}</span>
        <span className="text-xs text-[#555]">{idx + 1}/{cards.length} · {known.size} known</span>
      </div>
      {/* Card */}
      <div
        onClick={() => setFlipped(!flipped)}
        className={`min-h-20 flex flex-col items-center justify-center text-center p-4 rounded-xl cursor-pointer border transition-all ${
          flipped
            ? 'bg-[#7c6af7]/8 border-[#7c6af7]/30'
            : 'bg-[#141414] border-[#2a2a2a] hover:border-[#7c6af7]/30'
        } ${known.has(idx) ? 'opacity-40' : ''}`}
      >
        <span className="text-[10px] text-[#444] uppercase tracking-wider mb-2">
          {flipped ? 'Answer' : 'Question — click to flip'}
        </span>
        <p className="text-sm text-[#e8e8e8]">{flipped ? card.back : card.front}</p>
      </div>
      <div className="flex gap-2 mt-3">
        <button onClick={() => { setIdx(i => (i - 1 + cards.length) % cards.length); setFlipped(false) }}
          className="flex-1 text-xs py-2 rounded-xl bg-[#2a2a2a] text-[#777] hover:text-[#e8e8e8] transition-colors">← Prev</button>
        {flipped && (
          <button onClick={markKnown}
            className="flex-1 text-xs py-2 rounded-xl bg-green-500/15 text-green-400 hover:bg-green-500/25 transition-colors">
            ✓ Got it
          </button>
        )}
        <button onClick={() => { setIdx(i => (i + 1) % cards.length); setFlipped(false) }}
          className="flex-1 text-xs py-2 rounded-xl bg-[#2a2a2a] text-[#777] hover:text-[#e8e8e8] transition-colors">Next →</button>
      </div>
      <div className="mt-3 pt-3 border-t border-[#2a2a2a]">
        {saved ? (
          <span className="text-xs text-green-400">✓ Saved to spaced repetition</span>
        ) : (
          <button onClick={saveAllToSR}
            className="text-xs px-3 py-1.5 rounded-full bg-[#7c6af7]/15 text-[#a89bf8] hover:bg-[#7c6af7]/25 transition-colors">
            Save all {cards.length} cards to flashcard deck
          </button>
        )}
      </div>
    </div>
  )
}

// ── Inline Mind Map ───────────────────────────────────────────────────────────

export function InlineMindMap({ data }) {
  if (!data) return null
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-3">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🕸 Mind Map — {data.center}</span>
      <MindMapWidget data={data} compact={true} showDownload={true} />
    </div>
  )
}

// ── Inline Worksheet ──────────────────────────────────────────────────────────

export function InlineWorksheet({ markdown, title = '📄 Worksheet', fileName = 'worksheet.md' }) {
  const [expanded, setExpanded] = useState(true)
  const handlePrint = () => {
    const w = window.open('', '_blank')
    if (!w) return
    w.document.write(`<html><head><title>Worksheet</title><style>body{font-family:Inter,system-ui;padding:32px;max-width:800px;margin:auto;line-height:1.6}h1,h2{color:#1a1a1a}pre{background:#f5f5f5;padding:12px;border-radius:8px;overflow:auto}@media print{button{display:none}}</style></head><body><pre style="white-space:pre-wrap;font-family:inherit">${markdown.replace(/</g,'&lt;')}</pre><button onclick="window.print()" style="margin-top:16px;padding:8px 16px;background:#7c6af7;color:white;border:none;border-radius:8px;cursor:pointer">Print</button></body></html>`)
    w.document.close()
  }
  const handleCopy = () => navigator.clipboard.writeText(markdown)
  const handleDownload = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = fileName; a.click()
    URL.revokeObjectURL(url)
  }
  const handlePDF = async () => {
    const { jsPDF } = await import('jspdf')
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    const margin = 40
    const pageW = doc.internal.pageSize.getWidth()
    const pageH = doc.internal.pageSize.getHeight()
    const maxW = pageW - margin * 2
    let y = margin

    // Title
    doc.setFont('helvetica', 'bold'); doc.setFontSize(16)
    doc.text('Worksheet', margin, y); y += 22
    doc.setFont('helvetica', 'normal'); doc.setFontSize(9)
    doc.setTextColor(100); doc.text(`Generated by Study Buddy  •  ${new Date().toLocaleDateString()}`, margin, y); y += 18
    doc.setTextColor(0)
    doc.setDrawColor(200); doc.line(margin, y, pageW - margin, y); y += 14

    // Body - simple markdown stripping + wrapping
    const lines = markdown.split('\n')
    for (let raw of lines) {
      let line = raw.trim()
      if (!line) { y += 6; continue }
      // Headings
      const h = line.match(/^(#{1,3})\s+(.*)/)
      if (h) {
        const size = h[1].length === 1 ? 13 : h[1].length === 2 ? 11 : 10
        doc.setFont('helvetica', 'bold'); doc.setFontSize(size)
        const txt = h[2].replace(/\*\*/g, '')
        const wrapped = doc.splitTextToSize(txt, maxW)
        if (y + wrapped.length * 14 > pageH - margin) { doc.addPage(); y = margin }
        doc.text(wrapped, margin, y); y += wrapped.length * 14 + 4
        doc.setFont('helvetica', 'normal'); doc.setFontSize(9)
        continue
      }
      // Strip markdown bold/italic
      line = line.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1').replace(/`([^`]+)`/g, '$1')
      doc.setFont('helvetica', 'normal'); doc.setFontSize(9)
      const wrapped = doc.splitTextToSize(line, maxW)
      const hNeeded = wrapped.length * 12 + 2
      if (y + hNeeded > pageH - margin) { doc.addPage(); y = margin }
      doc.text(wrapped, margin, y); y += hNeeded
    }
    doc.save('worksheet.pdf')
  }
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-[#141414] border-b border-[#2a2a2a]">
        <span className="text-xs font-semibold text-[#7c6af7]">{title}</span>
        <div className="flex items-center gap-1.5">
          <button onClick={handleCopy} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">Copy</button>
          <button onClick={handleDownload} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">MD</button>
          <button onClick={handlePDF} className="text-[11px] px-3 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">PDF</button>
          <button onClick={handlePrint} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">Print</button>
          <button onClick={() => setExpanded(!expanded)} className="ml-1 p-1 text-[#555] hover:text-[#aaa]">{expanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}</button>
        </div>
      </div>
      {expanded && (
        <div className="p-4 max-h-[500px] overflow-y-auto prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{markdown}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

// ── Verification badge (2nd-model fact check) ─────────────────────────────────
