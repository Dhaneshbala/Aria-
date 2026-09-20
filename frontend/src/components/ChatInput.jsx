import { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Send, Paperclip, X, Image, FileText, Brain, Zap, FastForward, PenLine, Shapes, Square, MessageCircleQuestion, Drama } from 'lucide-react'
import { useStore } from '../store'
import { getActiveAbort } from '../hooks/useChat'

const QUICK_SHOTS = [
  { icon: <FileText size={11} />, label: 'Solve worksheet', hint: 'Solve this worksheet and show your working' },
  { icon: <Shapes size={11} />, label: 'Explain diagram', hint: 'Explain this diagram step by step' },
  { icon: <PenLine size={11} />, label: 'Check handwriting', hint: 'Check my handwritten answer and give feedback' },
]

const ChatInput = forwardRef(function ChatInput({ onSend, disabled, text: controlledText, onTextChange, autoFocus }, ref) {
  const { mode, setMode, isStreaming } = useStore()
  const [draft, setDraft] = useState('')
  const [attachedImage, setAttachedImage] = useState(null)
  const [attachedDocs, setAttachedDocs] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef()
  const imageInputRef = useRef()
  const docInputRef = useRef()

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus()
  }, [autoFocus])

  const text = controlledText !== undefined ? controlledText : draft
  const setText = (updater) => {
    const next = typeof updater === 'function' ? updater(text) : updater
    if (controlledText !== undefined) onTextChange?.(next)
    else setDraft(next)
  }

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }))

  const SLASH_COMMANDS = {
    '/quiz': 'Make a quiz on',
    '/flashcard': 'Make flashcards on',
    '/flashcards': 'Make flashcards on',
    '/note': 'Create study notes on',
    '/notes': 'Create study notes on',
    '/cheat': 'Create a cheat sheet on',
    '/cheatsheet': 'Create a cheat sheet on',
    '/mindmap': 'Draw a mind map of',
    '/timeline': 'Make a timeline for',
    '/summary': 'Summarise',
    '/explain': 'Explain',
    '/clear': '__CLEAR__',
    '/help': '__HELP__',
  }

  const handleSend = () => {
    let msg = text.trim()
    if (!msg && !attachedImage && attachedDocs.length === 0) return

    // Slash command expansion
    const slashMatch = msg.match(/^\/(\w+)\s*(.*)/)
    if (slashMatch) {
      const [, cmd, rest] = slashMatch
      const expansion = SLASH_COMMANDS['/' + cmd]
      if (expansion === '__CLEAR__') {
        onSend({ text: '/clear', command: 'clear' })
        setText(''); setAttachedImage(null); setAttachedDocs([])
        return
      }
      if (expansion === '__HELP__') {
        onSend({ text: 'List all available slash commands', command: 'help' })
        setText(''); setAttachedImage(null); setAttachedDocs([])
        return
      }
      if (expansion) {
        msg = rest.trim() ? `${expansion} ${rest.trim()}` : expansion
      }
    }

    if (attachedDocs.length > 1) {
      onSend({ text: msg, image: attachedImage, documents: attachedDocs })
    } else {
      onSend({ text: msg, image: attachedImage, document: attachedDocs[0] || null })
    }
    setText('')
    setAttachedImage(null)
    setAttachedDocs([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleImageFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return
    setAttachedImage(file)
  }

  const handleQuickShot = (hint) => {
    setText(hint)
    imageInputRef.current.click()
  }

  const handleDocFile = (file) => {
    if (!file) return
    const allowed = ['.pdf', '.docx', '.doc', '.pptx', '.xlsx', '.txt', '.csv', '.md', '.zip']
    const ok = allowed.some(ext => file.name.toLowerCase().endsWith(ext))
    if (ok) setAttachedDocs(prev => {
      if (prev.length >= 10) return prev
      if (prev.some(f => f.name === file.name && f.size === file.size)) return prev
      return [...prev, file]
    })
  }

  const handleDocFiles = (files) => {
    const list = Array.from(files || [])
    list.forEach(handleDocFile)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files || [])
    if (files.length === 0) return
    // handle all dropped files — images vs docs
    files.forEach(file => {
      if (file.type.startsWith('image/')) handleImageFile(file)
      else handleDocFile(file)
    })
  }, [])

  return (
    <div
      className={`relative ${dragOver ? 'ring-1 ring-[#8ab4f8]' : ''} w-full`}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      {dragOver && (
        <div className="absolute inset-0 bg-[#8ab4f8]/10 border-2 border-dashed border-[#8ab4f8]/50 rounded-[28px] flex items-center justify-center text-[#8ab4f8] text-sm pointer-events-none z-10">
          Drop image or document here
        </div>
      )}

      {/* Quick photo shortcuts — Gemini shows chips above input, kept subtle */}
      {!attachedImage && attachedDocs.length === 0 && text.length === 0 && (
        <div className="flex gap-1.5 mb-2 px-1 overflow-x-auto scrollbar-hide">
          {QUICK_SHOTS.map(s => (
            <button key={s.label} onClick={() => handleQuickShot(s.hint)}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#1e1f20] border border-[#2d2e30] text-xs text-[#9aa0a6] hover:text-[#e3e3e3] hover:bg-[#2d2e30] transition-colors">
              {s.icon} {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Attachments preview — Gemini chip style */}
      {(attachedImage || attachedDocs.length > 0) && (
        <div className="flex gap-2 mb-3 px-1 flex-wrap">
          {attachedImage && (
            <AttachmentChip
              icon={<Image size={12} />}
              name={attachedImage.name}
              file={attachedImage}
              onRemove={() => setAttachedImage(null)}
            />
          )}
          {attachedDocs.map((doc, idx) => (
            <AttachmentChip
              key={`${doc.name}-${idx}`}
              icon={<FileText size={12} />}
              name={doc.name}
              onRemove={() => setAttachedDocs(prev => prev.filter((_, i) => i !== idx))}
            />
          ))}
        </div>
      )}

      {/* $10B pill — premium glass, soft shadow */}
      <div className="gemini-pill-input px-4 pt-3 pb-2.5 flex flex-col gap-2 shadow-card hover:shadow-card-hover transition-shadow">
        {/* Textarea — Gemini single-line that expands */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? "Study Buddy is thinking..." : "Ask Study Buddy"}
          aria-label="Ask Study Buddy"
          rows={1}
          className="w-full bg-transparent text-[16px] leading-6 text-[#e3e3e3] placeholder-[#9aa0a6] resize-none outline-none max-h-40 py-1"
          style={{ height: 'auto', minHeight: '24px' }}
          onInput={e => {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
          }}
        />

        {/* Bottom toolbar inside pill — Gemini style */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-1.5">
            {/* Add */}
            <button
              onClick={() => imageInputRef.current.click()}
              className="w-8 h-8 rounded-full hover:bg-[#35363a] flex items-center justify-center text-[#9aa0a6] hover:text-[#e3e3e3] transition-colors"
              title="Add image"
              aria-label="Add image"
            >
              <Image size={18} />
            </button>
            <input ref={imageInputRef} type="file" accept="image/*" className="hidden"
              onChange={e => handleImageFile(e.target.files[0])} />

            <button
              onClick={() => docInputRef.current.click()}
              className="w-8 h-8 rounded-full hover:bg-[#35363a] flex items-center justify-center text-[#9aa0a6] hover:text-[#e3e3e3] transition-colors"
              title={attachedDocs.length > 0 ? `Add more files (${attachedDocs.length}/10)` : "Add files (PDFs, docs - up to 10)"}
              aria-label="Attach files"
            >
              <Paperclip size={18} />
            </button>
            <input ref={docInputRef} type="file" multiple
              accept=".pdf,.docx,.doc,.pptx,.xlsx,.txt,.csv,.md,.zip"
              className="hidden" onChange={e => { handleDocFiles(e.target.files); e.target.value = '' }} />

            {/* Tools — collapses mode toggles like Gemini “Tools” */}
            <div className="flex items-center gap-1 ml-1 pl-2 border-l border-[#3c4043]">
              <button
                onClick={() => setMode(mode === 'think' ? 'normal' : 'think')}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${mode === 'think' ? 'bg-[#8ab4f8] text-[#062e6f]' : 'bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e3e3e3]'}`}
                title="Thinking — deeper reasoning"
              >
                <span className="flex items-center gap-1"><Brain size={12} /> Think</span>
              </button>
              <button
                onClick={() => setMode(mode === 'socratic' ? 'normal' : 'socratic')}
                className={`p-1.5 rounded-full transition-colors ${mode === 'socratic' ? 'text-[#fbbc04] bg-[#fbbc04]/15' : 'text-[#9aa0a6] hover:text-[#e3e3e3] hover:bg-[#2d2e30]'}`}
                title="Socratic"
              >
                <MessageCircleQuestion size={14} />
              </button>
              <button
                onClick={() => setMode(mode === 'hype' ? 'normal' : 'hype')}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${mode === 'hype' ? 'bg-orange-500 text-white' : 'bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e3e3e3]'}`}
                title="Hype tutor — maximum energy explanations"
              >
                <span className="flex items-center gap-1">🔥 Hype</span>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Stop */}
            {isStreaming && (
              <button
                onClick={() => { const c = getActiveAbort(); if (c) c.abort() }}
                className="w-8 h-8 rounded-full bg-[#5f6368] hover:bg-[#5f6368]/80 flex items-center justify-center text-white transition-colors"
                title="Stop"
                aria-label="Stop generating"
              >
                <Square size={12} className="fill-current" />
              </button>
            )}

            {/* Send — Gemini blue pill */}
            <button
              onClick={handleSend}
              disabled={disabled || (!text.trim() && !attachedImage && attachedDocs.length === 0)}
              aria-label="Send message"
              className="w-9 h-9 rounded-full bg-[#8ab4f8] text-[#062e6f] disabled:bg-[#2d2e30] disabled:text-[#5f6368] hover:bg-[#aecbfa] disabled:hover:bg-[#2d2e30] flex items-center justify-center transition-colors shrink-0"
            >
              <Send size={16} className={text.trim() || attachedImage || attachedDocs.length > 0 ? 'translate-x-[1px]' : ''} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
})

function AttachmentChip({ icon, name, file, onRemove }) {
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    if (file && file.type?.startsWith('image/')) {
      const url = URL.createObjectURL(file)
      setPreview(url)
      return () => URL.revokeObjectURL(url)
    }
  }, [file])

  return (
    <div className="flex items-center gap-1.5 bg-[#2d2e30] border border-[#3c4043] rounded-full px-3 py-1.5 text-xs text-[#e3e3e3]">
      {preview && <img src={preview} className="w-5 h-5 rounded-full object-cover" alt="" />}
      {!preview && <span className="text-[#9aa0a6]">{icon}</span>}
      <span className="max-w-24 truncate">{name}</span>
      <button onClick={onRemove} aria-label={`Remove ${name}`} className="ml-1 w-5 h-5 rounded-full hover:bg-[#35363a] flex items-center justify-center text-[#9aa0a6] hover:text-[#f28b82]">
        <X size={11} />
      </button>
    </div>
  )
}

export default ChatInput
