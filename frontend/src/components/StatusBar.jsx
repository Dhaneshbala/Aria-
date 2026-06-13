import { useStore } from '../store'

const INTENT_LABELS = {
  chat:             null,
  image_analysis:   '👁 Vision',
  quiz:             '📝 Quiz',
  exam_mode:        '📋 Exam',
  flashcard:        '🃏 Flashcards',
  mindmap:          '🕸 Mind Map',
  study_plan:       '📅 Study Plan',
  notes:            '📒 Notes',
  worksheet_solver: '✏️ Worksheet',
  youtube:          '▶ YouTube',
  web_search:       '🔍 Search',
  image_gen:        '🎨 Image Gen',
  math:             '➗ Maths',
  summary:          '📋 Summary',
  explain:          '💡 Explain',
  doc_chat:         '📄 Document',
}

export default function StatusBar() {
  const { ollamaStatus, currentIntents, config, isStreaming } = useStore()

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-b border-[#1e1e1e] bg-[#111] text-xs min-h-[34px]">
      {/* Ollama status dot */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <div className={`w-1.5 h-1.5 rounded-full ${
          ollamaStatus === 'ok'       ? 'bg-green-400' :
          ollamaStatus === 'error'    ? 'bg-red-400' :
                                        'bg-yellow-400 animate-pulse'
        }`} />
        <span className="text-[#3a3a3a]">
          {ollamaStatus === 'ok'    ? (config.reasoning_model || 'Ollama') :
           ollamaStatus === 'error' ? 'Ollama offline — run: ollama serve' :
                                      'Connecting...'}
        </span>
      </div>

      {/* Streaming dots */}
      {isStreaming && (
        <div className="flex items-center gap-1.5 text-[#7c6af7]">
          <div className="flex gap-0.5 items-end h-3">
            {[0, 1, 2].map(i => (
              <div key={i}
                className="w-0.5 rounded-full bg-[#7c6af7] animate-bounce"
                style={{ height: `${6 + i * 2}px`, animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
          <span>Thinking</span>
        </div>
      )}

      {/* Active intent badges */}
      <div className="flex gap-1.5 flex-wrap">
        {currentIntents.map(intent => {
          const label = INTENT_LABELS[intent]
          if (!label) return null
          return (
            <span key={intent}
              className="px-2 py-0.5 rounded-full bg-[#7c6af7]/10 text-[#7c6af7] border border-[#7c6af7]/20">
              {label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
