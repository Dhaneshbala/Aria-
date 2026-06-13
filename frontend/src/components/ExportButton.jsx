import { useState } from 'react'
import { Download, ChevronDown } from 'lucide-react'

/**
 * ExportButton — exports the current conversation.
 * Formats: Markdown (.md) or JSON (.json)
 */
export default function ExportButton({ messages, conversationId }) {
  const [open, setOpen] = useState(false)

  if (!messages?.length) return null

  const exportMarkdown = () => {
    const lines = [`# ARIA Conversation\n`, `**ID:** ${conversationId || 'new'}\n`, `**Date:** ${new Date().toLocaleString()}\n\n---\n`]
    for (const msg of messages) {
      if (msg.role === 'user') {
        lines.push(`## You\n\n${msg.content}\n`)
        if (msg.docName) lines.push(`*[Document: ${msg.docName}]*\n`)
      } else if (msg.role === 'assistant') {
        lines.push(`## ARIA\n\n${msg.content}\n`)
        if (msg.extras?.quiz?.length) {
          lines.push(`\n### Quiz\n`)
          msg.extras.quiz.forEach((q, i) => {
            lines.push(`**Q${i + 1}:** ${q.question}\n`)
            q.options.forEach((o, j) => lines.push(`- ${'ABCD'[j]}) ${o}\n`))
            lines.push(`**Answer:** ${q.correct}\n`)
          })
        }
        if (msg.extras?.flashcards?.length) {
          lines.push(`\n### Flashcards\n`)
          msg.extras.flashcards.forEach(c => lines.push(`**${c.front}** — ${c.back}\n`))
        }
      }
      lines.push('\n')
    }
    download(lines.join('\n'), `aria-chat-${Date.now()}.md`, 'text/markdown')
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
        timestamp: m.timestamp || null,
      })),
    }
    download(JSON.stringify(data, null, 2), `aria-chat-${Date.now()}.json`, 'application/json')
    setOpen(false)
  }

  const download = (content, filename, type) => {
    const blob = new Blob([content], { type })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
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
          <div className="absolute right-0 top-full mt-1 z-20 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden shadow-xl w-40">
            <button
              onClick={exportMarkdown}
              className="w-full text-left px-4 py-2.5 text-xs text-[#aaa] hover:bg-[#2a2a2a] hover:text-[#e8e8e8] transition-colors flex items-center gap-2"
            >
              <span className="text-[#7c6af7] font-mono text-xs">.md</span>
              Markdown
            </button>
            <button
              onClick={exportJSON}
              className="w-full text-left px-4 py-2.5 text-xs text-[#aaa] hover:bg-[#2a2a2a] hover:text-[#e8e8e8] transition-colors flex items-center gap-2"
            >
              <span className="text-yellow-400 font-mono text-xs">{'{}'}</span>
              JSON
            </button>
          </div>
        </>
      )}
    </div>
  )
}
