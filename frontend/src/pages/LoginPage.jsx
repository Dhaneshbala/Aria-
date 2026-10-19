import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { LogIn, UserPlus, ShieldCheck, AlertTriangle } from 'lucide-react'
import { login, register, setToken } from '../services/auth'
import { useStore } from '../store'

/**
 * The sign-in / sign-up page (Section 13). Shown only when the backend
 * runs in accounts mode and no valid session exists. Local mode never
 * routes here — the family keeps exactly its open behaviour.
 */
export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const setAuth = useStore(s => s.setAuth)
  const [tab, setTab] = useState('login') // login | register
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const from = location.state?.from || '/'

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const me = tab === 'login'
        ? await login(username.trim().toLowerCase(), password)
        : await register(username.trim().toLowerCase(), password, displayName.trim())
      setToken(me.token)
      setAuth(me)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full w-full flex items-center justify-center bg-[#0b0b0b] px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-[#7c6af7]/15 flex items-center justify-center mx-auto mb-3">
            <ShieldCheck size={22} className="text-[#a89bf8]" />
          </div>
          <h1 className="text-lg font-semibold text-[#e8e8e8]">Sign in to ARIA</h1>
          <p className="text-xs text-[#888] mt-1">
            Your chats, notes and progress stay private to your account.
          </p>
        </div>

        <div className="flex gap-1 mb-4 bg-[#141414] border border-[#2a2a2a] rounded-full p-1">
          {[
            { id: 'login', label: 'Sign in', icon: LogIn },
            { id: 'register', label: 'New account', icon: UserPlus },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { setTab(id); setError('') }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-medium transition-colors ${
                tab === id ? 'bg-[#2d2e30] text-[#c2e7ff]' : 'text-[#9aa0a6] hover:text-[#e8e8e8]'
              }`}
            >
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="bg-[#141414] border border-[#2a2a2a] rounded-2xl p-4 space-y-3">
          {tab === 'register' && (
            <label className="block">
              <span className="text-[11px] text-[#9aa0a6]">Display name (optional)</span>
              <input
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                autoComplete="name"
                className="mt-1 w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none"
              />
            </label>
          )}
          <label className="block">
            <span className="text-[11px] text-[#9aa0a6]">Username</span>
            <input
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="mt-1 w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none"
            />
          </label>
          <label className="block">
            <span className="text-[11px] text-[#9aa0a6]">Password</span>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              required
              className="mt-1 w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none"
            />
            {tab === 'register' && (
              <span className="text-[10px] text-[#777] mt-1 block">
                At least 10 characters with letters and digits.
              </span>
            )}
          </label>

          {error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2">
              <AlertTriangle size={14} className="text-red-400 shrink-0 mt-0.5" />
              <p className="text-xs text-red-300 break-words">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full py-2.5 rounded-full bg-[#7c6af7] hover:bg-[#6a58e0] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {busy ? 'Please wait…' : tab === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="text-[10px] text-[#666] text-center mt-4">
          New accounts are always student accounts. Admin accounts can only be
          created by the operator on the server.
        </p>
      </div>
    </div>
  )
}
