/** Fact-check badge + source-citation panel. Extracted from Message.jsx. */
import { useState } from 'react'
import { ShieldCheck, ShieldAlert, BookOpen, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
export function VerificationBadge({ verification }) {
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

export function CitationsPanel({ citations, sources }) {
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

// ── Voice follow-up (STT) — Ask Study Buddy aloud without typing ───────────────────
