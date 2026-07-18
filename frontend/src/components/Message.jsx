import React, { useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import MindMapWidget from './MindMapWidget'
import { Copy, Check, ChevronDown, ChevronUp, Zap, Globe, Eye, Youtube, CheckCircle, Circle } from 'lucide-react'

// ── Root message component ────────────────────────────────────────────────────

function Message({ msg }) {
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
          <img src={msg.imagePreview} alt="Uploaded"
            className="max-w-xs rounded-xl border border-[#2a2a2a]" />
        )}
        {isUser && msg.docName && (
          <div className="flex items-center gap-1.5 text-xs text-[#666] bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-2.5 py-1">
            📄 {msg.docName}
          </div>
        )}

        {/* AI markdown response */}
        {!isUser && (
          <div className={`prose text-sm text-[#d0d0d0] w-full ${msg.streaming ? 'cursor' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={{
                code({ node, inline, className, children }) {
                  const lang = (className || '').replace('language-', '')
                  if (inline) return (
                    <code className="bg-[#2a2a2a] px-1 py-0.5 rounded text-[#e8e8e8] text-xs font-mono">
                      {children}
                    </code>
                  )
                  return <CodeBlock code={String(children).replace(/\n$/, '')} lang={lang} />
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

        {/* Tool results (collapsible) */}
        {!isUser && msg.tools?.length > 0 && (
          <div className="space-y-1.5 w-full">
            {msg.tools.map((tool, i) => <ToolResult key={i} tool={tool} />)}
          </div>
        )}

        {/* Generated image from Stable Diffusion */}
        {!isUser && msg.generatedImage && (
          <div className="w-full">
            <img src={msg.generatedImage} alt="ARIA generated"
              className="max-w-sm rounded-2xl border border-[#2a2a2a] shadow-xl" />
            <a href={msg.generatedImage} download="aria-image.png"
              className="text-xs text-[#555] hover:text-[#888] mt-1 block">
              ↓ Download image
            </a>
          </div>
        )}

        {/* ALL STRUCTURED EXTRAS — rendered inline in chat */}
        {!isUser && msg.extras && <ExtrasPanel extras={msg.extras} />}

      </div>
    </div>
  )
}

// ── Code block with copy ──────────────────────────────────────────────────────

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="my-3">
      <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
        <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">{lang || 'code'}</span>
        <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
          {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
        </button>
      </div>
      <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#ccc] leading-relaxed">{code}</code>
      </pre>
    </div>
  )
}

// ── Tool result (web search, vision, youtube) ─────────────────────────────────

function ToolResult({ tool }) {
  const [open, setOpen] = useState(false)
  const META = {
    web_search: { icon: <Globe size={12} />, label: 'Web Search Results', color: 'text-blue-400' },
    vision:     { icon: <Eye size={12} />,   label: 'Image Analysis',     color: 'text-purple-400' },
    youtube:    { icon: <Youtube size={12} />, label: 'YouTube Transcript', color: 'text-red-400' },
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
              <a href={r.url} target="_blank" rel="noreferrer" className="text-[#7c6af7] hover:underline block">{r.title}</a>
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
        </div>
      )}
    </div>
  )
}

// ── Extras panel — renders ALL structured content inline ──────────────────────

function ExtrasPanel({ extras }) {
  if (!extras) return null
  return (
    <div className="space-y-3 w-full mt-1">
      {extras.quiz?.length > 0            && <InlineQuiz questions={extras.quiz} label="Quiz" />}
      {extras.practice_quiz?.length > 0   && <InlineQuiz questions={extras.practice_quiz} label="Practice Questions" />}
      {extras.flashcards?.length > 0      && <InlineFlashcards cards={extras.flashcards} label="Flashcards" />}
      {extras.auto_flashcards?.length > 0 && <InlineFlashcards cards={extras.auto_flashcards} label="Auto-generated Flashcards" />}
      {extras.mindmap                      && <InlineMindMap data={extras.mindmap} />}
      {extras.study_plan?.length > 0      && <InlineStudyPlan plan={extras.study_plan} />}
    </div>
  )
}

// ── Inline Quiz ───────────────────────────────────────────────────────────────

function InlineQuiz({ questions, label }) {
  const [idx, setIdx] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const [answers, setAnswers] = useState([])
  const LETTERS = ['A', 'B', 'C', 'D']
  const q = questions[idx]

  const pick = (i) => {
    if (selected !== null) return
    setSelected(i)
    const correct = LETTERS[i] === q.correct
    if (correct) setScore(s => s + 1)
    setAnswers(a => [...a, correct])
  }

  const next = () => {
    if (idx < questions.length - 1) { setIdx(i => i + 1); setSelected(null) }
    else setDone(true)
  }

  if (done) return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4 text-center">
      <div className="text-2xl mb-1">{score === questions.length ? '🏆' : score >= questions.length / 2 ? '👏' : '📚'}</div>
      <p className="text-[#e8e8e8] font-semibold">{score}/{questions.length} correct</p>
      <p className="text-xs text-[#666] mt-1">
        {score === questions.length ? 'Perfect! Brilliant work!' :
         score >= questions.length * 0.7 ? 'Great job!' : 'Keep practising — you\'ll get there!'}
      </p>
      <button onClick={() => { setIdx(0); setSelected(null); setScore(0); setDone(false); setAnswers([]) }}
        className="mt-3 text-xs px-4 py-1.5 rounded-full bg-[#7c6af7]/20 text-[#a89bf8] hover:bg-[#7c6af7]/30 transition-colors">
        Try Again
      </button>
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

function InlineFlashcards({ cards, label }) {
  const [idx, setIdx] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [known, setKnown] = useState(new Set())
  const card = cards[idx]

  const markKnown = () => {
    setKnown(k => new Set([...k, idx]))
    setFlipped(false)
    setIdx(i => (i + 1) % cards.length)
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
    </div>
  )
}

// ── Inline Mind Map ───────────────────────────────────────────────────────────

function InlineMindMap({ data }) {
  if (!data) return null
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-3">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🕸 Mind Map — {data.center}</span>
      <MindMapWidget data={data} compact={true} showDownload={true} />
    </div>
  )
}

// ── Inline Study Plan ─────────────────────────────────────────────────────────

function InlineStudyPlan({ plan }) {
  const [checked, setChecked] = useState({})
  if (!plan?.length) return null

  const total = plan.reduce((s, d) => s + (d.tasks?.length || 0), 0)
  const done  = Object.values(checked).filter(Boolean).length

  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-[#7c6af7]">📅 Study Plan</span>
        <span className="text-xs text-[#555]">{done}/{total} tasks</span>
      </div>
      <div className="w-full bg-[#2a2a2a] rounded-full h-0.5 mb-3">
        <div className="bg-green-500 h-0.5 rounded-full transition-all"
          style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
      </div>
      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {plan.map((day, di) => (
          <div key={di} className="bg-[#141414] rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-[#e8e8e8]">Day {day.day}: {day.title}</p>
              <span className="text-[10px] text-[#444]">{day.time_minutes}min</span>
            </div>
            <div className="space-y-1.5">
              {(day.tasks || []).map((task, ti) => {
                const key = `${di}-${ti}`
                const isDone = checked[key]
                return (
                  <button key={ti} onClick={() => setChecked(c => ({ ...c, [key]: !c[key] }))}
                    className="w-full flex items-center gap-2 text-left">
                    {isDone
                      ? <CheckCircle size={13} className="text-green-400 flex-shrink-0" />
                      : <Circle size={13} className="text-[#333] flex-shrink-0" />}
                    <span className={`text-xs ${isDone ? 'text-[#444] line-through' : 'text-[#888]'}`}>{task}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default memo(Message)
