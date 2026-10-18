import { useState } from 'react'
import { Globe, Eye, Youtube, CheckCircle, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { isSafeUrl } from './utils'

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
    cheatsheet:      { icon: <BookOpen size={12} />, label: 'Cheat Sheet', color: 'text-amber-400' },
  }
  const meta = META[tool.tool] || { icon: '🔧', label: tool.tool, color: 'text-[#888]' }

  return (
    <div className="border border-[#222] rounded-xl overflow-hidden text-xs">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[#161616] transition-colors">
        <span className={meta.color}>{meta.icon}</span>
        <span className="text-[#888]">{meta.label}</span>
        <span className="ml-auto text-[#888]">{open ? <ChevronUp size={11}/> : <ChevronDown size={11}/>}</span>
      </button>
      {open && (
        <div className="bg-[#111] border-t border-[#222] px-3 py-2 max-h-48 overflow-y-auto">
          {tool.tool === 'web_search' && Array.isArray(tool.content) && tool.content.map((r, i) => (
            <div key={i} className="mb-2 pb-2 border-b border-[#1a1a1a] last:border-0">
              {isSafeUrl(r.url) ? <a href={r.url} target="_blank" rel="noreferrer" className="text-[#7c6af7] hover:underline block">{r.title}</a> : <span className="text-[#7c6af7] block">{r.title}</span>}
              <p className="text-[#888] mt-0.5 leading-relaxed">{r.snippet}</p>
            </div>
          ))}
          {tool.tool === 'cross_check' && Array.isArray(tool.content) && tool.content.map((r, i) => (
            <div key={i} className="mb-2 pb-2 border-b border-[#1a1a1a] last:border-0">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-[#888] font-mono bg-[#1a1a1a] rounded px-1.5 py-0.5">[{i + 1}]</span>
                {isSafeUrl(r.url) ? <a href={r.url} target="_blank" rel="noreferrer" className="text-green-400 font-medium hover:underline">{r.title}</a> : <span className="text-green-400 font-medium">{r.title}</span>}
              </div>
              <p className="text-[#888] mt-0.5 leading-relaxed">{r.snippet}</p>
            </div>
          ))}
          {tool.tool === 'vision' && (
            <p className="text-[#777] whitespace-pre-wrap leading-relaxed">{tool.content}</p>
          )}
          {tool.tool === 'youtube' && tool.content && (
            <div>
              <p className="text-[#aaa] font-medium">{tool.content.title}</p>
              <p className="text-[#888] mt-1 leading-relaxed line-clamp-4">{tool.content.transcript?.slice(0, 400)}…</p>
            </div>
          )}
          {tool.tool === 'todo' && tool.content && (
            <div className="text-[#aaa]">
              <p className="font-medium text-green-400">{tool.content.subject}: {tool.content.task}</p>
              <p className="text-[#888] mt-1">Due {tool.content.due_date || '—'} · {tool.content.estimated_mins}m · {tool.content.priority}</p>
            </div>
          )}
          {tool.tool === 'todos' && Array.isArray(tool.content) && (
            <div className="space-y-1">
              {tool.content.length === 0 ? <p className="text-[#888]">All caught up!</p> : tool.content.map((t, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-[#1a1a1a] last:border-0">
                  <span className="text-[#aaa] truncate">{t.subject}: {t.task}</span>
                  <span className="text-[10px] text-[#888] ml-2">{t.due_date || ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export { ToolResult }
