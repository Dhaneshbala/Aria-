import { useState } from 'react'
import { MessageCircleHeart, Bug, Send, CheckCircle2 } from 'lucide-react'
import { sendFeedback } from '../services/auth'

/**
 * Help & feedback (Section 13A). Reports land in the server-side
 * feedback table and surface in the admin dashboard — the message
 * content never leaves ARIA's own database.
 */
export default function HelpPage() {
  const [kind, setKind] = useState('feedback') // feedback | issue
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await sendFeedback(kind, message)
      setSent(true)
      setMessage('')
    } catch (err) {
      setError(err.message || 'Could not send — try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter overflow-y-auto h-full max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <MessageCircleHeart size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Help & feedback</h1>
      </div>

      {sent ? (
        <div className="bg-[#141414] border border-aria-border rounded-xl p-6 text-center">
          <CheckCircle2 size={28} className="text-green-400 mx-auto mb-2" />
          <p className="text-sm text-[#e8e8e8]">Thank you — your report is recorded.</p>
          <p className="text-[10px] text-[#777] mt-1">
            The administrator sees it in the admin dashboard and can mark it resolved.
          </p>
          <button onClick={() => setSent(false)}
            className="mt-4 px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#e8e8e8]">
            Send another
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="bg-[#141414] border border-aria-border rounded-xl p-4 space-y-3">
          <div className="flex gap-2">
            {[
              { id: 'feedback', label: 'Feedback / idea', icon: MessageCircleHeart },
              { id: 'issue', label: 'Something is broken', icon: Bug },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setKind(id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs transition-colors ${
                  kind === id ? 'bg-[#004a77] text-[#c2e7ff]' : 'bg-[#2d2e30] text-[#9aa0a6] hover:text-[#e8e8e8]'
                }`}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>

          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={6}
            placeholder={
              kind === 'issue'
                ? 'What happened? What did you expect? (Never paste passwords or private notes here.)'
                : 'What would make ARIA better for your studying?'
            }
            className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] placeholder-[#555] focus:border-[#5f6368] outline-none resize-y"
          />
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-[#555]">
              Stored on the ARIA server only — visible to the administrator.
            </p>
            <button
              type="submit"
              disabled={busy || message.trim().length < 5}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#7c6af7] hover:bg-[#6a58e0] disabled:opacity-40 text-white text-xs font-medium transition-colors"
            >
              <Send size={13} /> {busy ? 'Sending…' : 'Send'}
            </button>
          </div>
          {error && <p className="text-xs text-red-300">{error}</p>}
        </form>
      )}
    </div>
  )
}
