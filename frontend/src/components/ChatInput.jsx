import { useState, useRef, useCallback } from 'react'
import { Send, Paperclip, Mic, MicOff, X, Image, FileText } from 'lucide-react'
import { transcribeAudio } from '../services/api'

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [attachedImage, setAttachedImage] = useState(null)
  const [attachedDoc, setAttachedDoc] = useState(null)
  const [recording, setRecording] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef()
  const imageInputRef = useRef()
  const docInputRef = useRef()
  const mediaRecorderRef = useRef()
  const chunksRef = useRef([])

  const handleSend = () => {
    if (!text.trim() && !attachedImage && !attachedDoc) return
    onSend({ text: text.trim(), image: attachedImage, document: attachedDoc })
    setText('')
    setAttachedImage(null)
    setAttachedDoc(null)
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

  const handleDocFile = (file) => {
    if (!file) return
    const allowed = ['.pdf', '.docx', '.doc', '.pptx', '.xlsx', '.txt', '.csv', '.md', '.zip']
    const ok = allowed.some(ext => file.name.toLowerCase().endsWith(ext))
    if (ok) setAttachedDoc(file)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (!file) return
    if (file.type.startsWith('image/')) handleImageFile(file)
    else handleDocFile(file)
  }, [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunksRef.current = []
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(t => t.stop())
        try {
          const result = await transcribeAudio(blob)
          if (result.transcript) setText(t => t + (t ? ' ' : '') + result.transcript)
        } catch {}
      }
      mr.start()
      mediaRecorderRef.current = mr
      setRecording(true)
    } catch {}
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setRecording(false)
  }

  return (
    <div
      className={`relative ${dragOver ? 'ring-1 ring-[#7c6af7]' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      {dragOver && (
        <div className="absolute inset-0 bg-[#7c6af7]/10 border-2 border-dashed border-[#7c6af7]/50 rounded-2xl flex items-center justify-center text-[#a89bf8] text-sm pointer-events-none z-10">
          Drop image or document here
        </div>
      )}

      {/* Attachments preview */}
      {(attachedImage || attachedDoc) && (
        <div className="flex gap-2 mb-2 px-1">
          {attachedImage && (
            <AttachmentChip
              icon={<Image size={12} />}
              name={attachedImage.name}
              preview={URL.createObjectURL(attachedImage)}
              onRemove={() => setAttachedImage(null)}
            />
          )}
          {attachedDoc && (
            <AttachmentChip
              icon={<FileText size={12} />}
              name={attachedDoc.name}
              onRemove={() => setAttachedDoc(null)}
            />
          )}
        </div>
      )}

      <div className="flex items-end gap-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl px-3 py-2 focus-within:border-[#7c6af7]/50 transition-colors">
        {/* Attach image */}
        <button
          onClick={() => imageInputRef.current.click()}
          className="flex-shrink-0 p-1.5 text-[#555] hover:text-[#aaa] transition-colors"
          title="Attach image"
        >
          <Image size={18} />
        </button>
        <input ref={imageInputRef} type="file" accept="image/*" className="hidden"
          onChange={e => handleImageFile(e.target.files[0])} />

        {/* Attach document */}
        <button
          onClick={() => docInputRef.current.click()}
          className="flex-shrink-0 p-1.5 text-[#555] hover:text-[#aaa] transition-colors"
          title="Attach document"
        >
          <Paperclip size={18} />
        </button>
        <input ref={docInputRef} type="file"
          accept=".pdf,.docx,.doc,.pptx,.xlsx,.txt,.csv,.md,.zip"
          className="hidden" onChange={e => handleDocFile(e.target.files[0])} />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything — maths, science, history, coding..."
          rows={1}
          disabled={disabled}
          className="flex-1 bg-transparent text-sm text-[#e8e8e8] placeholder-[#444] resize-none outline-none max-h-40 py-1"
          style={{ height: 'auto', minHeight: '24px' }}
          onInput={e => {
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
          }}
        />

        {/* Voice */}
        <button
          onClick={recording ? stopRecording : startRecording}
          className={`flex-shrink-0 p-1.5 transition-colors ${recording ? 'text-red-400 animate-pulse' : 'text-[#555] hover:text-[#aaa]'}`}
          title={recording ? 'Stop recording' : 'Voice input'}
        >
          {recording ? <MicOff size={18} /> : <Mic size={18} />}
        </button>

        {/* Send */}
        <button
          onClick={handleSend}
          disabled={disabled || (!text.trim() && !attachedImage && !attachedDoc)}
          className="flex-shrink-0 p-1.5 rounded-lg bg-[#7c6af7] text-white disabled:opacity-30 hover:bg-[#6a59e0] transition-colors"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}

function AttachmentChip({ icon, name, preview, onRemove }) {
  return (
    <div className="flex items-center gap-1.5 bg-[#2a2a2a] rounded-lg px-2 py-1 text-xs text-[#aaa]">
      {preview && <img src={preview} className="w-4 h-4 rounded object-cover" alt="" />}
      {!preview && icon}
      <span className="max-w-24 truncate">{name}</span>
      <button onClick={onRemove} className="text-[#555] hover:text-[#f87171]">
        <X size={11} />
      </button>
    </div>
  )
}
