import { useState } from 'react'
import { Download, ChevronDown, Copy, Check } from 'lucide-react'

/**
 * ExportButton — exports the current conversation.
 * Formats: Markdown (.md), JSON (.json), or copy as text
 */
export default function ExportButton({ messages, conversationId }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!messages?.length) return null

  const buildMarkdown = () => {
    const lines = [`# ARIA Conversation\n`, `**ID:** ${conversationId || 'new'}\n`, `**Date:** ${new Date().toLocaleString()}\n\n---\n`]
    for (const msg of messages) {
      if (msg.role === 'user') {
        lines.push(`## You\n\n${msg.content}\n`)
        if (msg.docName) lines.push(`*[Document: ${msg.docName}]*\n`)
        if (msg.docNames?.length) msg.docNames.forEach(n => lines.push(`*[Document: ${n}]*\n`))
      } else if (msg.role === 'assistant') {
        lines.push(`## ARIA\n\n${msg.content}\n`)
        if (msg.extras?.quiz?.length) {
          lines.push(`\n### Quiz\n`)
          msg.extras.quiz.forEach((q, i) => {
            lines.push(`**Q${i + 1}:** ${q.question}\n`)
            q.options.forEach((o, j) => lines.push(`- ${'ABCD'[j]}) ${o}\n`))
            lines.push(`**Answer:** ${q.correct}\n\n`)
          })
        }
        if (msg.extras?.flashcards?.length) {
          lines.push(`\n### Flashcards\n`)
          msg.extras.flashcards.forEach(c => lines.push(`**${c.front}** — ${c.back}\n`))
        }
        if (msg.extras?.worksheet) {
          const ws = msg.extras.worksheet
          lines.push(`\n### Worksheet: ${ws.title || ''}\n`)
          if (ws.questions?.length) {
            ws.questions.forEach((q, i) => {
              lines.push(`**${i + 1}.** ${q.question}\n`)
              if (q.options) q.options.forEach((o, j) => lines.push(`  - ${'ABCD'[j]}) ${o}\n`))
              lines.push(`  *Answer:* ${q.answer}\n\n`)
            })
          }
        }
        if (msg.extras?.diagram) {
          lines.push(`\n### Diagram\n${msg.extras.diagram}\n`)
        }
        if (msg.verification) {
          const v = msg.verification
          const icon = v.status === 'verified' ? '✅' : v.status === 'questioned' ? '⚠️' : 'ℹ️'
          lines.push(`\n*${icon} Verification: ${v.summary || v.status}*\n`)
        }
      }
      lines.push('\n')
    }
    return lines.join('\n')
  }

  const exportMarkdown = () => {
    download(buildMarkdown(), `aria-chat-${Date.now()}.md`, 'text/markdown')
    setOpen(false)
  }

  const exportJSON = () => {
    const data = {
      conversation_id: conversationId,
      exported_at: new Date().toISOString(),
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
        extras: m.extras || null,
        verification: m.verification || null,
        timestamp: m.timestamp || null,
      })),
    }
    download(JSON.stringify(data, null, 2), `aria-chat-${Date.now()}.json`, 'application/json')
    setOpen(false)
  }

  const copyAsText = async () => {
    const text = buildMarkdown().replace(/[#*_`]/g, '').replace(/\n{3,}/g, '\n\n')
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
    setOpen(false)
  }

  const download = (content, filename, type) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-[#555] hover:text-[#aaa] px-2 py-1.5 rounded-lg hover:bg-[#1a1a1a] transition-colors"
      >
        <Download size={13} />
        Export
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden shadow-xl w-44">
            <button
              onClick={copyAsText}
              className="w-full text-left px-4 py-2.5 text-xs text-[#aaa] hover:bg-[#2a2a2a] hover:text-[#e8e8e8] transition-colors flex items-center gap-2"
            >
              {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
              {copied ? 'Copied!' : 'Copy as text'}
            </button>
            <div className="border-t border-[#2a2a2a]" />
            <button
              onClick={exportMarkdown}
              className="w-full text-left px-4 py-2.5 text-xs text-[#aaa] hover:bg-[#2a2a2a] hover:text-[#e8e8e8] transition-colors flex items-center gap-2"
            >
              <span className="text-[#7c6af7] font-mono text-xs">.md</span>
              Download Markdown
            </button>
            <button
              onClick={exportJSON}
              className="w-full text-left px-4 py-2.5 text-xs text-[#aaa] hover:bg-[#2a2a2a] hover:text-[#e8e8e8] transition-colors flex items-center gap-2"
            >
              <span className="text-yellow-400 font-mono text-xs">{'{}'}</span>
              Download JSON
            </button>
          </div>
        </>
      )}
    </div>
  )
}
