import React, { useState, memo, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import MindMapWidget from './MindMapWidget'
import NapkinDiagram, { NAPKIN_TYPES } from './NapkinDiagram'
import { checkAnswer, getWeakTopics, transcribeAudio, suggestVisuals, generateDiagram } from '../services/api'
import { startTask, useBgTask } from '../services/tasks'
import { useStore } from '../store'
import { Copy, Check, ChevronDown, ChevronUp, Zap, Globe, Eye, Youtube, CheckCircle, Circle, Volume2, Loader, ShieldCheck, ShieldAlert, Sparkles, BookOpen, ExternalLink, Mic, MicOff } from 'lucide-react'

function isSafeUrl(url) {
  try {
    const u = new URL(url, window.location.origin)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

// ── Root message component ────────────────────────────────────────────────────

function Message({ msg, onSuggest }) {
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
        {isUser && (msg.docName || (msg.docNames && msg.docNames.length)) && (
          <div className="flex flex-wrap gap-1.5">
            {(msg.docNames || (msg.docName ? [msg.docName] : [])).map((name, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-[#666] bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-2.5 py-1">
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
            <span className="text-[#333]">·</span>
            <VoiceFollowUp onSuggest={onSuggest} />
            <span className="text-[#333]">·</span>
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
          <div className="w-full">
            <img src={msg.generatedImage} alt="ARIA generated"
              className="max-w-sm rounded-2xl border border-[#2a2a2a] shadow-xl" />
            {isSafeUrl(msg.generatedImage) && (
              <a href={msg.generatedImage} download="aria-image.png"
                className="text-xs text-[#555] hover:text-[#888] mt-1 block">
                ↓ Download image
              </a>
            )}
          </div>
        )}

        {/* Napkin-style visual (editable spec → SVG, inline in chat) */}
        {!isUser && msg.generatedDiagram?.type === 'napkin' && msg.generatedDiagram?.spec && (
          <NapkinDiagram spec={msg.generatedDiagram.spec} />
        )}

        {/* Specialist diagram (legacy validated SVG/mermaid) */}
        {!isUser && msg.generatedDiagram?.code && (
          <div className="w-full my-3">
            <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
              <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">
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
        {!isUser && msg.suggestions?.length > 0 && !msg.streaming && onSuggest && (
          <div className="w-full mt-2">
            <p className="text-[10px] text-[#555] uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Sparkles size={10} /> Keep exploring
            </p>
            <div className="flex flex-wrap gap-1.5">
              {msg.suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onSuggest(q)}
                  className="text-xs px-3 py-1.5 rounded-full bg-[#141414] border border-[#2a2a2a] text-[#888] hover:border-[#7c6af7]/50 hover:text-[#bbb] hover:bg-[#7c6af7]/5 transition-all text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

// ── SVG Diagram renderer — interactive, exportable, premium ──────────────────
function SvgDiagram({ code }) {
  const [scale, setScale] = React.useState(1)
  const [expanded, setExpanded] = React.useState(false)
  const sanitized = code.replace(/<script[\s\S]*?<\/script>/gi, '').trim()
  if (!sanitized.toLowerCase().startsWith('<svg')) {
    return (
      <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#ccc] leading-relaxed">{code}</code>
      </pre>
    )
  }
  const download = () => {
    const blob = new Blob([sanitized], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'aria-diagram.svg'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const Wrapper = expanded ? 'div' : 'div'
  return (
    <>
      <div className="bg-[#fafafa] rounded-b-xl border border-[#2a2a2a] border-t-0 p-3 relative group overflow-hidden">
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
          <span className="text-[10px] font-mono bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
          <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
          <button onClick={() => setExpanded(v => !v)} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center" title={expanded ? 'Collapse' : 'Fullscreen'}>{expanded ? '⤓' : '⤢'}</button>
          <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
        </div>
        <div className="flex items-center justify-center overflow-auto p-2" style={{ maxHeight: expanded ? '70vh' : 'auto' }}>
          <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-full [&>svg]:h-auto drop-shadow-[0_2px_8px_rgba(0,0,0,0.08)]" />
        </div>
        <div className="absolute bottom-2 left-3 text-[10px] font-mono tracking-wider text-[#9aa0a6] bg-white/90 backdrop-blur px-2 py-1 rounded-full border border-[#e8eaed]">ARIA diagram · pinch to zoom · drag to pan</div>
      </div>
      {expanded && <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20" onClick={() => setExpanded(false)} />}
      {expanded && (
        <div className="fixed inset-0 z-30 flex items-center justify-center p-4 sm:p-8 pointer-events-none">
          <div className="bg-[#fafafa] rounded-2xl shadow-2xl border border-[#2a2a2a] p-4 max-w-[90vw] max-h-[90vh] overflow-auto pointer-events-auto">
            <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }} dangerouslySetInnerHTML={{ __html: sanitized }} className="[&>svg]:max-w-none" />
          </div>
        </div>
      )}
    </>
  )
}

// ── Mermaid renderer — CDN, themed, interactive ─────────────────────────────
function MermaidDiagram({ code }) {
  const [svg, setSvg] = React.useState(null)
  const [error, setError] = React.useState(null)
  const [scale, setScale] = React.useState(1)
  React.useEffect(() => {
    let cancelled = false
    async function render() {
      try {
        if (!window.mermaid) {
          await new Promise((resolve, reject) => {
            const s = document.createElement('script')
            s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js'
            s.onload = resolve
            s.onerror = reject
            document.head.appendChild(s)
          })
          window.mermaid.initialize({
            startOnLoad: false,
            theme: 'base',
            securityLevel: 'strict',
            themeVariables: {
              primaryColor: '#7c6af7',
              primaryTextColor: '#e3e3e3',
              primaryBorderColor: '#3c4043',
              lineColor: '#9aa0a6',
              secondaryColor: '#1e1f20',
              tertiaryColor: '#2d2e30',
              background: '#131314',
              mainBkg: '#1e1f20',
              nodeBorder: '#7c6af7',
              clusterBkg: '#1e1f20',
              titleColor: '#e3e3e3',
              edgeLabelBackground: '#2d2e30',
            }
          })
        }
        const id = 'm' + Math.random().toString(36).slice(2, 9)
        const { svg } = await window.mermaid.render(id, code)
        if (!cancelled) setSvg(svg)
      } catch (e) {
        if (!cancelled) setError(String(e.message || e))
      }
    }
    render()
    return () => { cancelled = true }
  }, [code])
  if (error) {
    return (
      <pre className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-b-xl p-4 overflow-x-auto m-0">
        <code className="text-xs font-mono text-[#f87171] leading-relaxed">Mermaid error: {error}{"\n\n"}{code}</code>
      </pre>
    )
  }
  if (!svg) {
    return <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-b-xl p-8 text-center text-xs text-[#666] flex items-center justify-center gap-2"><span className="w-3 h-3 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" /> Rendering diagram…</div>
  }
  const download = () => {
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'aria-mermaid.svg'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <div className="bg-[#131314] rounded-b-xl border border-[#2a2a2a] border-t-0 p-3 relative group overflow-hidden">
      <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <button onClick={() => setScale(s => Math.max(0.6, s - 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">−</button>
        <span className="text-[10px] font-mono bg-[#1a1a1a] border border-[#2a2a2a] text-[#888] px-1.5 py-1 rounded-full min-w-[36px] text-center">{Math.round(scale*100)}%</span>
        <button onClick={() => setScale(s => Math.min(2.2, s + 0.15))} className="w-7 h-7 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#aaa] hover:text-white flex items-center justify-center text-xs">+</button>
        <button onClick={download} className="px-2.5 h-7 rounded-full bg-[#7c6af7] text-white text-[11px] font-medium hover:bg-[#6a59e0]">Download</button>
      </div>
      <div className="flex items-center justify-center overflow-auto p-2">
        <div style={{ transform: `scale(${scale})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }} dangerouslySetInnerHTML={{ __html: svg }} className="[&>svg]:max-w-full [&>svg]:h-auto" />
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
  const lower = (lang || '').toLowerCase()
  if (lower === 'svg') {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">diagram · svg</span>
          <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
            {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <SvgDiagram code={code} />
      </div>
    )
  }
  if (lower === 'mermaid') {
    return (
      <div className="my-3">
        <div className="flex items-center justify-between bg-[#161616] border border-[#2a2a2a] border-b-0 rounded-t-xl px-3 py-1.5">
          <span className="text-[10px] text-[#555] font-mono uppercase tracking-wider">diagram · mermaid</span>
          <button onClick={copy} className="text-[#555] hover:text-[#aaa] transition-colors p-0.5">
            {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
          </button>
        </div>
        <MermaidDiagram code={code} />
      </div>
    )
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
    web_search:      { icon: <Globe size={12} />, label: 'Google Search', color: 'text-blue-400' },
    cross_check:     { icon: <Globe size={12} />, label: 'Google Cross-Check', color: 'text-green-400' },
    vision:          { icon: <Eye size={12} />,   label: 'Image Analysis',     color: 'text-purple-400' },
    youtube:         { icon: <Youtube size={12} />, label: 'YouTube Transcript', color: 'text-red-400' },
    todo:            { icon: <CheckCircle size={12} />, label: 'Todo Added', color: 'text-green-400' },
    todos:           { icon: <BookOpen size={12} />, label: 'Your Todos', color: 'text-amber-400' },
    worksheet:       { icon: <BookOpen size={12} />, label: 'Worksheet', color: 'text-purple-400' },
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
      {extras.audio_script                 && <InlineAudioScript script={extras.audio_script} />}
      {(extras.quiz || extras.exam_sim || extras.practice_quiz) && <InlineMistakeBank onDrill={drill} />}
    </div>
  )
}

function InlineMethods({ methods }) {
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

function InlineAudioScript({ script }) {
  if (!script) return null
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl p-4">
      <span className="text-xs font-semibold text-[#7c6af7] block mb-2">🎧 Audio Overview</span>
      <p className="text-xs text-[#888] whitespace-pre-wrap leading-relaxed">{script.slice(0, 800)}{script.length>800?'…':''}</p>
      <p className="text-[10px] text-[#555] mt-2">Tap Listen below to hear it</p>
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
    }).catch(() => setWeak([])).finally(() => setLoading(false))
  }, [])
  if (loading) return <div className="text-[11px] text-[#555]">Checking mistake bank…</div>
  if (!weak || weak.length === 0) return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-3">
      <p className="text-xs text-[#666]">No weak topics yet — keep quizzing and ARIA will track gaps via <span className="text-[#7c6af7]">find_knowledge_gaps()</span>.</p>
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
    // Mistake bank: auto-log to profile (advanced_study_service find_knowledge_gaps uses profile weak_areas)
    try {
      // fire-and-forget, subject inferred from label or general
      const subj = (label || 'general').toLowerCase().replace(/[^a-z]/g, '') || 'general'
      checkAnswer(subj, correct).catch(() => {})
      checkAnswer('general', correct).catch(() => {})
    } catch {}
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

// ── Inline Worksheet ──────────────────────────────────────────────────────────

function InlineWorksheet({ markdown }) {
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
    const a = document.createElement('a'); a.href = url; a.download = 'worksheet.md'; a.click()
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
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-[#141414] border-b border-[#2a2a2a]">
        <span className="text-xs font-semibold text-[#7c6af7]">📄 Worksheet</span>
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

function VerificationBadge({ verification }) {
  const { verified, notes } = verification
  if (verified) {
    return (
      <div className="flex items-start gap-1.5 text-xs text-green-400/90 bg-green-500/8 border border-green-500/20 rounded-lg px-3 py-1.5">
        <ShieldCheck size={13} className="flex-shrink-0 mt-0.5" />
        <span>Fact-checked against web sources — no errors found{notes ? ` · ${notes}` : ''}</span>
      </div>
    )
  }
  return (
    <div className="flex items-start gap-1.5 text-xs text-amber-400/90 bg-amber-500/8 border border-amber-500/20 rounded-lg px-3 py-1.5">
      <ShieldAlert size={13} className="flex-shrink-0 mt-0.5" />
      <span>Fact-check flag: {notes || 'some claims may need verification'}</span>
    </div>
  )
}

// ── Citations panel (source-grounded references) ──────────────────────────────

function CitationsPanel({ citations, sources }) {
  const [expanded, setExpanded] = useState(false)
  if (!citations?.length) return null

  // Group citations by source
  const grouped = {}
  citations.forEach(c => {
    const key = `${c.source_type}-${c.source_url || c.source_title}`
    if (!grouped[key]) {
      grouped[key] = {
        type: c.source_type,
        title: c.source_title,
        url: c.source_url,
        count: 0,
      }
    }
    grouped[key].count++
  })

  const unique = Object.values(grouped).sort((a, b) => b.count - a.count)

  return (
    <div className="border border-[#222] rounded-xl overflow-hidden text-xs">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[#161616] transition-colors">
        <BookOpen size={12} className="text-[#7c6af7]" />
        <span className="text-[#666]">{citations.length} source{citations.length > 1 ? 's' : ''} cited</span>
        <span className="ml-auto text-[#444]">{expanded ? <ChevronUp size={11}/> : <ChevronDown size={11}/>}</span>
      </button>
      {expanded && (
        <div className="bg-[#111] border-t border-[#222] px-3 py-2 max-h-48 overflow-y-auto">
          {unique.map((src, i) => (
            <div key={i} className="mb-2 pb-2 border-b border-[#1a1a1a] last:border-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-[#444] font-mono bg-[#1a1a1a] rounded px-1.5 py-0.5">
                  {src.type}
                </span>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noreferrer" className="text-[#7c6af7] hover:underline flex items-center gap-1">
                    {src.title || 'Source'} <ExternalLink size={9} />
                  </a>
                ) : (
                  <span className="text-[#888]">{src.title || 'Source'}</span>
                )}
                <span className="text-[10px] text-[#444] ml-auto">{src.count}x</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Voice follow-up (STT) — Ask ARIA aloud without typing ───────────────────

function VoiceFollowUp({ onSuggest }) {
  const [recording, setRecording] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')
  const recorderRef = React.useRef(null)
  const chunksRef = React.useRef([])

  const start = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 500) { setError('No audio'); setRecording(false); return }
        setProcessing(true)
        try {
          const data = await transcribeAudio(blob, typeof navigator !== 'undefined' ? navigator.language : undefined)
          const txt = (data?.transcript || data?.text || '').trim()
          if (txt && onSuggest) onSuggest(txt)
          else if (!txt) setError(data?.language && !String(data.language).startsWith('en') ? `Heard ${data.language} but got no text — try again, closer` : 'Heard nothing')
        } catch (e) {
          setError('Transcribe failed')
        } finally {
          setProcessing(false)
          setRecording(false)
        }
      }
      recorderRef.current = rec
      rec.start()
      setRecording(true)
    } catch (e) {
      setError('Mic denied')
    }
  }
  const stop = () => {
    try { recorderRef.current?.stop() } catch {}
  }

  if (error) return (
    <button onClick={() => setError('')} className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1">
      <MicOff size={11} /> {error} — retry?
    </button>
  )
  if (processing) return (
    <span className="flex items-center gap-1 text-[11px] text-[#666]"><Loader size={11} className="animate-spin" /> Transcribing…</span>
  )
  if (recording) return (
    <button onClick={stop} className="flex items-center gap-1.5 text-[11px] text-red-400 hover:text-red-300 animate-pulse">
      <MicOff size={11} /> Stop recording
    </button>
  )
  return (
    <button onClick={start} className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors">
      <Mic size={11} /> Ask aloud
    </button>
  )
}

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    } catch (e) {
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
    } catch (e) {
      if (!mountedRef.current) return
      if (e?.name !== 'AbortError') setError(e.message || 'Could not create visual')
    } finally {
      if (mountedRef.current) setGenerating(null)
    }
  }

  return (
    <div className="w-full">
      <button onClick={start}
        className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors">
        {bg?.status === 'running' && !open
          ? <><Loader size={11} className="animate-spin" /> Drawing in background…</>
          : <><Sparkles size={11} /> {open ? 'Hide visuals' : (savedSpec || spec ? 'View visual' : 'Visualize')}</>}
      </button>
      {open && (
        <div className="mt-2 w-full bg-[#141414] border border-[#2a2a2a] rounded-2xl p-3">
          {loading && (
            <p className="text-[11px] text-[#666] flex items-center gap-2">
              <Loader size={11} className="animate-spin" /> Finding the best visuals…
            </p>
          )}
          {!loading && !spec && (
            <>
              <p className="text-[10px] text-[#555] uppercase tracking-wider mb-2">
                {options?.length ? 'Pick a style — like Napkin AI' : 'Pick a visual type'}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(options || NAPKIN_TYPES.map(t => ({ type: t.id, label: `${t.label} — ${t.hint}` }))).map(o => (
                  <button key={o.type} onClick={() => pick(o.type)} disabled={generating}
                    className="text-[11px] px-3 py-1.5 rounded-full bg-[#1e1f20] border border-[#2a2a2a] text-[#aaa] hover:border-[#7c6af7]/60 hover:text-white transition-all disabled:opacity-50">
                    {generating === o.type ? 'Drawing…' : `✨ ${o.label}${o.recommended ? ' ★' : ''}`}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-[#444] mt-2">Tip: highlight part of my answer first to visualise just that bit.</p>
            </>
          )}
          {!loading && spec && (
            <>
              <button onClick={() => setSpec(null)} className="text-[11px] text-[#666] hover:text-[#aaa] mb-1">← try another style</button>
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

function ListenButton({ text }) {
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(false)

  const play = async () => {
    if (playing) return
    setPlaying(true)
    setError(false)
    try {
      const resp = await fetch('/api/voice/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.slice(0, 3500) }),
      })
      if (!resp.ok) throw new Error('TTS failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => { URL.revokeObjectURL(url); setPlaying(false) }
      audio.onerror = () => { URL.revokeObjectURL(url); setPlaying(false); setError(true) }
      await audio.play()
    } catch {
      setPlaying(false)
      setError(true)
    }
  }

  if (error) return (
    <button onClick={() => setError(false)}
      className="text-[10px] text-[#555] hover:text-[#888] flex items-center gap-1">
      <Volume2 size={11} /> Listen unavailable
    </button>
  )

  return (
    <button onClick={play} disabled={playing}
      className="flex items-center gap-1.5 text-[11px] text-[#666] hover:text-[#a89bf8] transition-colors disabled:opacity-60">
      {playing ? <Loader size={11} className="animate-spin" /> : <Volume2 size={11} />}
      {playing ? 'Speaking…' : 'Listen'}
    </button>
  )
}

export default memo(Message)
