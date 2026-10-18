import React, { useState, memo, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import MindMapWidget from './MindMapWidget'
import NapkinDiagram, { NAPKIN_TYPES } from './NapkinDiagram'
import { checkAnswer, getWeakTopics, suggestVisuals, generateDiagram, bulkAddSrCards } from '../services/api'
import { showToast } from './Toast'
import { startTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { ChevronDown, ChevronUp, Zap, Sparkles, Loader } from 'lucide-react'
import { SvgDiagram, MermaidDiagram, CodeBlock } from './message/CodeBlock'
import { ToolResult } from './message/ToolResult'
import { VerificationBadge, CitationsPanel } from './message/Trust'
import { VoiceFollowUp, ListenButton } from './message/Voice'
import ZoomableImage from './message/ZoomableImage'

const FOLLOW_UPS = {
  explain:  ['Quiz me on this', 'Show me a mind map', 'Give me a practice question'],
  math:     ['Show me another method', 'Make it harder', 'Quiz me on this'],
  science:  ['Draw a diagram', 'Quiz me on this', 'Give me a real-world example'],
  history:  ['Make a timeline', 'Quiz me on this', 'Compare with another event'],
  coding:   ['Debug this code', 'Show me another example', 'Make a quiz on this'],
  quiz:     ['Make it harder', 'Try another topic', 'Review my mistakes'],
  default:  ['Quiz me on this', 'Make a mind map', 'Explain differently'],
}

function getFollowUps(content) {
  const lower = (content || '').toLowerCase()
  if (lower.includes('quiz') || lower.includes('question')) return FOLLOW_UPS.quiz
  if (lower.includes('explain') || lower.includes('what is') || lower.includes('how does')) return FOLLOW_UPS.explain
  if (lower.includes('math') || lower.includes('equation') || lower.includes('calculate') || lower.includes('algebra')) return FOLLOW_UPS.math
  if (lower.includes('science') || lower.includes('biology') || lower.includes('chemistry') || lower.includes('physics')) return FOLLOW_UPS.science
  if (lower.includes('history') || lower.includes('war') || lower.includes('revolution')) return FOLLOW_UPS.history
  if (lower.includes('code') || lower.includes('function') || lower.includes('python') || lower.includes('javascript')) return FOLLOW_UPS.coding
  return FOLLOW_UPS.default
}
// ── Root message component ────────────────────────────────────────────────────

function Message({ msg, onSuggest, onRetry }) {
  const isUser = msg.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} mb-6`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
        isUser
          ? 'bg-[#7c6af7]/20 text-[#a89bf8] border border-[#7c6af7]/20'
          : 'bg-gradient-to-br from-[#7c6af7] to-[#4f46e5] shadow-lg shadow-[#7c6af7]/20'
      }`}>
        {isUser ? 'You' : <Zap size={14} className="text-white" />}
      </div>

      <div className={`max-w-[85%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>

        {/* User bubble */}
        {isUser && (
          <div className="bg-[#7c6af7]/12 border border-[#7c6af7]/15 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-[#e8e8e8] whitespace-pre-wrap">
            {msg.content}
          </div>
        )}

        {/* Uploaded image preview */}
        {isUser && msg.imagePreview && (
          <ZoomableImage src={msg.imagePreview} alt={msg.docName ? `Uploaded: ${msg.docName}` : 'Uploaded image'}
            className="max-w-xs rounded-xl border border-aria-border" />
        )}
        {isUser && (msg.docName || (msg.docNames && msg.docNames.length)) && (
          <div className="flex flex-wrap gap-1.5">
            {(msg.docNames || (msg.docName ? [msg.docName] : [])).map((name, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-[#888] bg-[#1a1a1a] border border-aria-border rounded-lg px-2.5 py-1">
                📄 {name}
              </div>
            ))}
          </div>
        )}

        {/* AI markdown response */}
        {!isUser && (
          <div className={`prose text-sm text-[#d0d0d0] w-full ${msg.streaming ? 'cursor' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={{
                code({ className, children }) {
                  const text = String(children)
                  const lang = (className || '').replace('language-', '')
                  // react-markdown v9 removed the `inline` prop — detect inline
                  // code instead: fenced code has a language class or newlines.
                  if (!className && !text.includes('\n')) {
                    return (
                      <code className="bg-[#2a2a2a] px-1 py-0.5 rounded text-[#e8e8e8] text-xs font-mono">
                        {children}
                      </code>
                    )
                  }
                  return <CodeBlock code={text.replace(/\n$/, '')} lang={lang} />
                },
                table({ children }) {
                  return (
                    <div className="overflow-x-auto my-3">
                      <table className="min-w-full text-xs border-collapse">{children}</table>
                    </div>
                  )
                },
              }}
            >
              {msg.content || ''}
            </ReactMarkdown>
          </div>
        )}

        {/* Failure banner + Retry (connection errors) */}
        {!isUser && msg.failed && !msg.streaming && (
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className="text-red-400 font-medium">Message failed</span>
            {msg.retryPayload && onRetry && (
              <button
                onClick={() => onRetry(msg.retryPayload)}
                className="px-3 py-1 rounded-lg bg-[#7c6af7] hover:bg-[#6a59e0] text-white font-medium transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* Verification badge (2nd-model fact check) */}
        {!isUser && msg.verification && !msg.streaming && (
          <VerificationBadge verification={msg.verification} />
        )}

        {/* Citations panel (source-grounded references) */}
        {!isUser && msg.citations?.length > 0 && !msg.streaming && (
          <CitationsPanel citations={msg.citations} sources={msg.sources} />
        )}

        {/* Listen + Voice follow-up (TTS + STT) + Visualize (Napkin-style) */}
        {!isUser && msg.content?.length > 30 && !msg.streaming && (
          <div className="flex items-center gap-2 flex-wrap">
            <ListenButton text={msg.content} />
            <span className="text-[#777]">·</span>
            <VoiceFollowUp onSuggest={onSuggest} />
            <span className="text-[#777]">·</span>
            <VisualizeButton text={msg.content} msgId={msg.id} savedSpec={msg.visualSpec} />
          </div>
        )}

        {/* Tool results (collapsible) */}
        {!isUser && msg.tools?.length > 0 && (
          <div className="space-y-1.5 w-full">
            {msg.tools.map((tool, i) => <ToolResult key={i} tool={tool} />)}
          </div>
        )}

        {/* Generated image from Stable Diffusion */}
        {!isUser && msg.generatedImage && (
          <ZoomableImage src={msg.generatedImage} alt="ARIA generated image"
            className="max-w-sm rounded-2xl border border-aria-border shadow-xl" />
        )}

        {/* Napkin-style visual (editable spec → SVG, inline in chat) */}
        {!isUser && msg.generatedDiagram?.type === 'napkin' && msg.generatedDiagram?.spec && (
          <NapkinDiagram spec={msg.generatedDiagram.spec} />
        )}

        {/* Specialist diagram (legacy validated SVG/mermaid) */}
        {!isUser && msg.generatedDiagram?.code && (
          <div className="w-full my-3">
            <div className="flex items-center justify-between bg-[#161616] border border-aria-border border-b-0 rounded-t-xl px-3 py-1.5">
              <span className="text-[10px] text-[#888] font-mono uppercase tracking-wider">
                diagram · {msg.generatedDiagram.type === 'mermaid' ? 'mermaid' : 'svg'} · specialist
              </span>
            </div>
            {msg.generatedDiagram.type === 'mermaid'
              ? <MermaidDiagram code={msg.generatedDiagram.code} />
              : <SvgDiagram code={msg.generatedDiagram.code} />}
          </div>
        )}

        {/* ALL STRUCTURED EXTRAS — rendered inline in chat */}
        {!isUser && msg.extras && <ExtrasPanel extras={msg.extras} onSuggest={onSuggest} />}

        {/* Follow-up suggestions (NotebookLM-style) */}
        {!isUser && !msg.streaming && onSuggest && (
          <div className="w-full mt-2">
            {(msg.suggestions?.length > 0) ? (
              <>
                <p className="text-[10px] text-[#888] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Sparkles size={10} /> Keep exploring
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {msg.suggestions.map((q, i) => (
                    <button key={i} onClick={() => onSuggest(q)}
                      className="text-xs px-3 py-1.5 rounded-full bg-[#141414] border border-aria-border text-[#888] hover:border-[#7c6af7]/50 hover:text-[#bbb] hover:bg-[#7c6af7]/5 transition-all text-left">
                      {q}
                    </button>
                  ))}
                </div>
              </>
            ) : msg.content && msg.content.length > 50 ? (
              <>
                <p className="text-[10px] text-[#888] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Sparkles size={10} /> What next?
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {getFollowUps(msg.content).map((q, i) => (
                    <button key={i} onClick={() => onSuggest(q)}
                      className="text-xs px-3 py-1.5 rounded-full bg-[#141414] border border-aria-border text-[#888] hover:border-[#7c6af7]/50 hover:text-[#bbb] hover:bg-[#7c6af7]/5 transition-all text-left">
                      {q}
                    </button>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        )}

      </div>
    </div>
  )
}
// ── Extras panel — renders ALL structured content inline ──────────────────────

function ExtrasPanel({ extras, onSuggest }) {
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

function InlineMethods({ methods }) {
  const [revealed, setRevealed] = useState(1)
  if (!methods?.length) return null
  return (
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">🧮 Step-by-step — {methods.length} methods</span>
        <span className="text-xs text-[#888]">{revealed}/{methods.length} shown</span>
      </div>
      <div className="space-y-3">
        {methods.slice(0, revealed).map((m, i) => (
          <div key={i} className="bg-[#141414] border border-aria-border rounded-xl p-3">
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
        <p className="text-[11px] text-[#888] mt-2 text-center">All methods shown — pick your favorite!</p>
      )}
    </div>
  )
}

function InlineAudioScript({ script }) {
  if (!script) return null
  return (
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-4">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🎧 Audio Overview</span>
      <p className="text-xs text-[#888] whitespace-pre-wrap leading-relaxed">{script.slice(0, 800)}{script.length>800?'…':''}</p>
      <p className="text-[10px] text-[#888] mt-2">Tap Listen below to hear it</p>
    </div>
  )
}

function InlineMistakeBank({ onDrill }) {
  const [weak, setWeak] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    getWeakTopics().then(d => {
      // API returns {weak_topics: [{topic, accuracy}] } or array
      const list = Array.isArray(d) ? d : (d?.weak_topics || d?.weak_areas || [])
      setWeak(list.slice(0, 3))
    }).catch((e) => { console.warn('weak topics failed', e); setWeak([]) }).finally(() => setLoading(false))
  }, [])
  if (loading) return <div className="text-[11px] text-[#888]">Checking mistake bank…</div>
  if (!weak || weak.length === 0) return (
    <div className="bg-[#141414] border border-aria-border rounded-xl p-3">
      <p className="text-xs text-[#888]">No weak topics yet — keep quizzing and ARIA will track gaps via <span className="text-[#7c6af7]">find_knowledge_gaps()</span>.</p>
    </div>
  )
  return (
    <div className="bg-[#1a1a1a] border border-amber-500/20 rounded-2xl p-3">
      <p className="text-xs font-semibold text-amber-400 mb-2">📚 Mistake bank — weak topics (from study_intel)</p>
      <div className="space-y-1.5">
        {weak.map((w, i) => (
          <div key={i} className="flex items-center justify-between bg-[#141414] border border-aria-border rounded-lg px-3 py-2">
            <div>
              <p className="text-xs text-[#e8e8e8]">{w.topic || w.subject || w.name || 'Topic ' + (i+1)}</p>
              <p className="text-[10px] text-[#888]">{typeof w.accuracy === 'number' ? Math.round(w.accuracy*100)+'% accuracy' : (w.accuracy || '')} {w.attempts ? `· ${w.attempts} attempts` : ''}</p>
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

function InlineQuiz({ questions, label }) {
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
      const detail = {
        question: q.question,
        correct_answer: q.options[LETTERS.indexOf(q.correct)] || '',
        given_answer: q.options[i] || '',
        topic: label || '',
      }
      checkAnswer(subj, correct, detail).catch((e) => console.warn('checkAnswer failed', e))
      // 'general' echo is for the profile only — no mistake payload, or the
      // mistake book double-counts the same miss.
      checkAnswer('general', correct).catch((e) => console.warn('checkAnswer failed', e))
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
    } catch {
      showToast('Failed to save flashcards', 'error')
    }
  }

  if (done) return (
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-4 text-center">
      <div className="text-2xl mb-1">{score === questions.length ? '🏆' : score >= questions.length / 2 ? '👏' : '📚'}</div>
      <p className="text-[#e8e8e8] font-semibold">{score}/{questions.length} correct</p>
      <p className="text-xs text-[#888] mt-1">
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
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">📝 {label}</span>
        <span className="text-xs text-[#888]">{idx + 1}/{questions.length} · Score: {score}</span>
      </div>
      {/* Progress bar */}
      <div className="w-full bg-[#2a2a2a] rounded-full h-0.5 mb-3">
        <div className="bg-[#7c6af7] h-0.5 rounded-full transition-all" style={{ width: `${((idx) / questions.length) * 100}%` }} />
      </div>
      <p className="text-sm text-[#e8e8e8] mb-3">{q.question}</p>
      <p aria-live="assertive" className="sr-only">
        {selected === null ? '' :
          LETTERS[selected] === q.correct ? 'Correct.' : `Incorrect. The correct answer was ${q.correct}, ${q.options[LETTERS.indexOf(q.correct)]}`}
      </p>
      <div className="space-y-2">
        {q.options.map((opt, i) => (
          <button key={i} onClick={() => pick(i)}
            disabled={selected !== null}
            className={`w-full text-left text-xs px-3 py-2.5 rounded-xl border transition-all ${
              selected === null
                ? 'border-aria-border hover:border-[#7c6af7]/50 hover:bg-[#7c6af7]/5 text-[#aaa]'
                : LETTERS[i] === q.correct
                  ? 'border-green-500 bg-green-500/10 text-green-300'
                  : selected === i
                    ? 'border-red-500 bg-red-500/10 text-red-400'
                    : 'border-[#1a1a1a] text-[#888]'
            }`}>
            <span className="font-mono opacity-60 mr-2">{LETTERS[i]})</span>{opt}
            {selected !== null && LETTERS[i] === q.correct && (
              <span className="float-right text-green-400" aria-hidden="true">✓</span>
            )}
            {selected === i && LETTERS[i] !== q.correct && (
              <span className="float-right text-red-400" aria-hidden="true">✗</span>
            )}
          </button>
        ))}
      </div>
      {selected !== null && q.explanation && (
        <div className="mt-3 px-3 py-2 bg-[#0f0f0f] border border-aria-border rounded-xl text-xs text-[#888]">
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

function InlineFlashcards({ cards, label }) {
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
    } catch {
      showToast('Failed to save flashcards', 'error')
    }
  }

  return (
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">🃏 {label}</span>
        <span className="text-xs text-[#888]">{idx + 1}/{cards.length} · {known.size} known</span>
      </div>
      {/* Card */}
      <div
        onClick={() => setFlipped(!flipped)}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setFlipped(f => !f) } }}
        aria-label="Flashcard — press Enter or Space to flip"
        className={`min-h-20 flex flex-col items-center justify-center text-center p-4 rounded-xl cursor-pointer border transition-all ${
          flipped
            ? 'bg-[#7c6af7]/8 border-[#7c6af7]/30'
            : 'bg-[#141414] border-aria-border hover:border-[#7c6af7]/30'
        } ${known.has(idx) ? 'opacity-40' : ''}`}
      >
        <span className="text-[10px] text-[#888] uppercase tracking-wider mb-2">
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
      <div className="mt-3 pt-3 border-t border-aria-border">
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

function InlineMindMap({ data }) {
  if (!data) return null
  return (
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl p-3">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🕸 Mind Map — {data.center}</span>
      <MindMapWidget data={data} compact={true} showDownload={true} />
    </div>
  )
}

// ── Inline Worksheet ──────────────────────────────────────────────────────────

function InlineWorksheet({ markdown, title = '📄 Worksheet', fileName = 'worksheet.md' }) {
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
    doc.setTextColor(100); doc.text(`Generated by ARIA  •  ${new Date().toLocaleDateString()}`, margin, y); y += 18
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
    <div className="bg-[#1a1a1a] border border-aria-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-[#141414] border-b border-aria-border">
        <span className="text-xs font-semibold text-[#7c6af7]">{title}</span>
        <div className="flex items-center gap-1.5">
          <button onClick={handleCopy} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">Copy</button>
          <button onClick={handleDownload} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">MD</button>
          <button onClick={handlePDF} className="text-[11px] px-3 py-1 rounded-full bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors">PDF</button>
          <button onClick={handlePrint} className="text-[11px] px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[#888] hover:text-white transition-colors">Print</button>
          <button onClick={() => setExpanded(!expanded)} className="ml-1 p-1 text-[#888] hover:text-[#aaa]">{expanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}</button>
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

// ── Visualize (Napkin-style) — turn any answer into an editable visual ──────
// No new page: pick from 3 suggested visual types, rendered inline below.

function VisualizeButton({ text, msgId, savedSpec }) {
  const taskKey = `viz-${msgId || 'x'}`
  const bg = useBgTask(taskKey)
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState(null)
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(null)
  // Spec may have landed in the store while we were on another page.
  const [spec, setSpec] = useState(savedSpec || null)
  const [error, setError] = useState('')
  const mountedRef = React.useRef(true)
  React.useEffect(() => () => { mountedRef.current = false }, [])

  // Adopt a background result that finished while we were away.
  React.useEffect(() => {
    if (!spec && savedSpec) {
      setSpec(savedSpec)
      setGenerating(null)
      // Fresh background completion (not a reload) — reveal it automatically.
      if (bg?.status === 'done') setOpen(true)
    }
    else if ((bg?.status === 'error' || bg?.status === 'cancelled') && generating) {
      setGenerating(null)
      if (bg.status === 'error' && bg.error) setError(bg.error)
    }

  }, [bg?.status, savedSpec])

  const plain = (md) => String(md || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#*_>`|]/g, '')
    .replace(/\$\$/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  const start = async () => {
    if (open) { setOpen(false); return }
    setError('')
    // Already have a visual (e.g. finished in the background) — just show it.
    if (spec || savedSpec) { setSpec(spec || savedSpec); setOpen(true); return }
    // Napkin behaviour: visualise the SELECTED text if the user highlighted
    // part of this answer, else the whole answer.
    let sel = ''
    try {
      sel = window.getSelection()?.toString().trim() || ''
    } catch {}
    const src = (sel.length > 20 ? sel : plain(text)).slice(0, 1200)
    if (src.length < 20) { setError('Not enough text to visualise'); return }
    setSource(src)
    setOpen(true)
    setLoading(true)
    try {
      const data = await suggestVisuals(src)
      if (!mountedRef.current) return
      if (data?.error) throw new Error(data.error)
      setOptions(data?.options || null)
      if (data?.preview && !data?.options) setSpec(data.preview)
    } catch {
      // Suggest is heuristic — still offer all types on failure
      if (mountedRef.current) setOptions(null)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  const pick = async (type) => {
    setGenerating(type)
    setError('')
    try {
      // Background-safe: leaving chat won't stop it — the spec lands in
      // this message via the store even when this component is gone.
      const data = await startTask(taskKey, {
        label: 'Visual',
        page: '/chat',
        topic: source.slice(0, 40),
        run: (signal) => generateDiagram(source, type, signal),
        onDone: (d) => {
          if (d?.error) throw new Error(d.error)
          if (d?.spec) useStore.getState().updateMessage(msgId, { visualSpec: d.spec })
          else throw new Error('No visual returned')
        },
      })
      if (!mountedRef.current) return
      if (data?.error) throw new Error(data.error)
      if (data?.spec) setSpec(data.spec)
      else throw new Error('No visual returned')
    } catch {
      if (!mountedRef.current) return
      if (e?.name !== 'AbortError') setError(e.message || 'Could not create visual')
    } finally {
      if (mountedRef.current) setGenerating(null)
    }
  }

  return (
    <div className="w-full">
      <button onClick={start}
        className="flex items-center gap-1.5 text-[11px] text-[#888] hover:text-[#a89bf8] transition-colors">
        {bg?.status === 'running' && !open
          ? <><Loader size={11} className="animate-spin" /> Drawing in background…</>
          : <><Sparkles size={11} /> {open ? 'Hide visuals' : (savedSpec || spec ? 'View visual' : 'Visualize')}</>}
      </button>
      {open && (
        <div className="mt-2 w-full bg-[#141414] border border-aria-border rounded-2xl p-3">
          {loading && (
            <p className="text-[11px] text-[#888] flex items-center gap-2">
              <Loader size={11} className="animate-spin" /> Finding the best visuals…
            </p>
          )}
          {!loading && !spec && (
            <>
              <p className="text-[10px] text-[#888] uppercase tracking-wider mb-2">
                {options?.length ? 'Pick a style — like Napkin AI' : 'Pick a visual type'}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(options || NAPKIN_TYPES.map(t => ({ type: t.id, label: `${t.label} — ${t.hint}` }))).map(o => (
                  <button key={o.type} onClick={() => pick(o.type)} disabled={generating}
                    className="text-[11px] px-3 py-1.5 rounded-full bg-aria-surface border border-aria-border text-[#aaa] hover:border-[#7c6af7]/60 hover:text-white transition-all disabled:opacity-50">
                    {generating === o.type ? 'Drawing…' : `✨ ${o.label}${o.recommended ? ' ★' : ''}`}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-[#888] mt-2">Tip: highlight part of my answer first to visualise just that bit.</p>
            </>
          )}
          {!loading && spec && (
            <>
              <button onClick={() => setSpec(null)} className="text-[11px] text-[#888] hover:text-[#aaa] mb-1">← try another style</button>
              <NapkinDiagram spec={spec} />
            </>
          )}
          {error && <p className="text-[11px] text-amber-400 mt-2">{error}</p>}
        </div>
      )}
    </div>
  )
}

// ── Listen button (local TTS) ─────────────────────────────────────────────────


export default memo(Message)
