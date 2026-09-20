/**
 * Message — chat bubble shell (user + assistant markdown, tools, visuals, extras).
 * Sub-components live in message/ (Diagrams, CodeBlocks, StudyWidgets,
 * TrustPanels, VoiceVisual); shared helpers in message/shared.js.
 */
import React, { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import NapkinDiagram from './NapkinDiagram'
import { SvgDiagram, MermaidDiagram } from './message/Diagrams'
import { CopyMessageButton, CodeBlock } from './message/CodeBlocks'
import { ToolResult, ExtrasPanel } from './message/StudyWidgets'
import { VerificationBadge, CitationsPanel } from './message/TrustPanels'
import { VoiceFollowUp, VisualizeButton, ListenButton } from './message/VoiceVisual'
import { isSafeUrl, getFollowUps } from './message/shared'
import { Zap, Sparkles } from 'lucide-react'

// ── Root message component ────────────────────────────────────────────────────

function Message({ msg, onSuggest }) {
  const isUser = msg.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} mb-6`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ring-1 ${
        isUser
          ? 'bg-aria-accent/15 text-aria-accent-light border border-aria-accent/20 ring-aria-accent/10'
          : 'bg-gradient-to-br from-aria-accent to-[#4f46e5] shadow-lg shadow-aria-accent/20 ring-white/10'
      }`}>
        {isUser ? 'You' : <Zap size={14} className="text-white" />}
      </div>

      <div className={`max-w-[85%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>

        {/* User bubble — $10B: subtle glass, premium radius */}
        {isUser && (
          <div className="bg-aria-accent/10 border border-aria-accent/15 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-aria-text whitespace-pre-wrap backdrop-blur-sm shadow-card">
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

        {/* AI markdown response — premium prose */}
        {!isUser && (
          <div className="relative group">
            <div className={`prose text-sm text-aria-text-soft w-full leading-relaxed ${msg.streaming ? 'cursor' : ''}`}>
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
                    return <CodeBlock code={String(children).replace(/\n$/, '')} lang={lang} defer={msg.streaming} />
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
            {/* Copy response button */}
            {!msg.streaming && msg.content && (
              <CopyMessageButton content={msg.content} />
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
            <img src={msg.generatedImage} alt="Study Buddy generated"
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
        {!isUser && !msg.streaming && onSuggest && (
          <div className="w-full mt-2">
            {(msg.suggestions?.length > 0) ? (
              <>
                <p className="text-[10px] text-[#555] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Sparkles size={10} /> Keep exploring
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {msg.suggestions.map((q, i) => (
                    <button key={i} onClick={() => onSuggest(q)}
                      className="text-xs px-3 py-1.5 rounded-full bg-[#141414] border border-[#2a2a2a] text-[#888] hover:border-[#7c6af7]/50 hover:text-[#bbb] hover:bg-[#7c6af7]/5 transition-all text-left">
                      {q}
                    </button>
                  ))}
                </div>
              </>
            ) : msg.content && msg.content.length > 50 ? (
              <>
                <p className="text-[10px] text-[#555] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                  <Sparkles size={10} /> What next?
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {getFollowUps(msg.content).map((q, i) => (
                    <button key={i} onClick={() => onSuggest(q)}
                      className="text-xs px-3 py-1.5 rounded-full bg-[#141414] border border-[#2a2a2a] text-[#888] hover:border-[#7c6af7]/50 hover:text-[#bbb] hover:bg-[#7c6af7]/5 transition-all text-left">
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

// ── SVG Diagram renderer — interactive, exportable, premium ──────────────────

export default memo(Message)
