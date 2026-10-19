import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserCog, KeyRound, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { changePassword, deleteMe, logout, renameMe, setToken, clearToken } from '../services/auth'
import { useStore } from '../store'

/**
 * Account settings (Section 13A): rename, change password, delete
 * account. Everything posts to the backend; the browser never decides
 * anything about identity.
 */
export default function AccountPage() {
  const navigate = useNavigate()
  const user = useStore(s => s.authUser)
  const clearAuth = useStore(s => s.clearAuth)

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNew, setPwNew] = useState('')
  const [pwNew2, setPwNew2] = useState('')
  const [delPassword, setDelPassword] = useState('')
  const [delConfirm, setDelConfirm] = useState(false)
  const [msg, setMsg] = useState(null) // {type:'ok'|'err', text}
  const [busy, setBusy] = useState('')

  function ok(text) { setMsg({ type: 'ok', text }) }
  function bad(text) { setMsg({ type: 'err', text }) }

  async function saveProfile(e) {
    e.preventDefault()
    setBusy('profile')
    try {
      await renameMe(displayName)
      ok('Display name saved.')
    } catch (err) { bad(err.message) } finally { setBusy('') }
  }

  async function changePw(e) {
    e.preventDefault()
    if (pwNew !== pwNew2) return bad('New passwords do not match.')
    if (pwNew.length < 10 || !/[A-Za-z]/.test(pwNew) || !/[0-9]/.test(pwNew))
      return bad('New password: 10+ characters with letters and digits.')
    setBusy('pw')
    try {
      await changePassword(pwCurrent, pwNew)
      setPwCurrent(''); setPwNew(''); setPwNew2('')
      ok('Password changed.')
    } catch (err) { bad(err.message) } finally { setBusy('') }
  }

  async function doDelete(e) {
    e.preventDefault()
    setBusy('del')
    try {
      await deleteMe(delPassword)
      setToken('')
      clearAuth()
      navigate('/login', { replace: true })
    } catch (err) { bad(err.message) } finally { setBusy('') }
  }

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter overflow-y-auto h-full max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <UserCog size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Account</h1>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 rounded-xl px-3 py-2 mb-4 text-xs ${
          msg.type === 'ok'
            ? 'bg-green-500/10 border border-green-500/25 text-green-300'
            : 'bg-red-500/10 border border-red-500/25 text-red-300'
        }`}>
          {msg.type === 'ok' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
          {msg.text}
        </div>
      )}

      <section className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <h2 className="text-xs text-[#888] font-semibold mb-3">Profile</h2>
        <form onSubmit={saveProfile} className="flex gap-2 items-end">
          <label className="flex-1 block">
            <span className="text-[11px] text-[#9aa0a6]">Display name</span>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="mt-1 w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none"
            />
          </label>
          <button type="submit" disabled={busy === 'profile'}
            className="px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#e8e8e8] disabled:opacity-40">
            {busy === 'profile' ? 'Saving…' : 'Save'}
          </button>
        </form>
        <p className="text-[10px] text-[#555] mt-2">Signed in as {user?.username} · role: {user?.role}</p>
      </section>

      <section className="bg-[#141414] border border-aria-border rounded-xl p-4 mb-4">
        <h2 className="flex items-center gap-1.5 text-xs text-[#888] font-semibold mb-3">
          <KeyRound size={13} /> Change password
        </h2>
        <form onSubmit={changePw} className="space-y-2">
          <input type="password" placeholder="Current password" value={pwCurrent}
            onChange={e => setPwCurrent(e.target.value)} autoComplete="current-password"
            className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none" />
          <div className="flex gap-2">
            <input type="password" placeholder="New password" value={pwNew}
              onChange={e => setPwNew(e.target.value)} autoComplete="new-password"
              className="flex-1 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none" />
            <input type="password" placeholder="Repeat" value={pwNew2}
              onChange={e => setPwNew2(e.target.value)} autoComplete="new-password"
              className="flex-1 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none" />
          </div>
          <button type="submit" disabled={busy === 'pw' || !pwCurrent || !pwNew}
            className="px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#e8e8e8] disabled:opacity-40">
            {busy === 'pw' ? 'Changing…' : 'Change password'}
          </button>
        </form>
      </section>

      <section className="bg-[#1a0f0f] border border-red-900/30 rounded-xl p-4">
        <h2 className="flex items-center gap-1.5 text-xs text-red-300 font-semibold mb-2">
          <Trash2 size={13} /> Delete account
        </h2>
        <p className="text-[10px] text-red-200/60 mb-3">
          Removes your access and revokes every session. Chat history was
          already private to this account. Notes/todos stored under the old
          shared store are purged in a later stage — you will be told when
          that becomes automatic.
        </p>
        {!delConfirm ? (
          <button onClick={() => setDelConfirm(true)}
            className="px-4 py-2 rounded-full bg-red-500/15 hover:bg-red-500/25 text-xs text-red-300 transition-colors">
            Delete my account…
          </button>
        ) : (
          <form onSubmit={doDelete} className="space-y-2">
            <input type="password" placeholder="Confirm with your password" value={delPassword}
              onChange={e => setDelPassword(e.target.value)} autoComplete="current-password"
              className="w-full bg-[#0f0f0f] border border-red-900/40 rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-red-500/50 outline-none" />
            <div className="flex gap-2">
              <button type="submit" disabled={busy === 'del' || !delPassword}
                className="px-4 py-2 rounded-full bg-red-500/20 hover:bg-red-500/30 text-xs text-red-200 disabled:opacity-40">
                {busy === 'del' ? 'Deleting…' : 'Permanently delete'}
              </button>
              <button type="button" onClick={() => { setDelConfirm(false); setDelPassword('') }}
                className="px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#9aa0a6]">
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      <div className="mt-4">
        <button
          onClick={async () => {
            try { await logout() } catch {}
            setToken('')
            clearAuth()
            window.location.href = '/login'
          }}
          className="flex items-center gap-1.5 text-xs text-[#9aa0a6] hover:text-[#e8e8e8] transition-colors"
        >
          <KeyRound size={13} /> Sign out on this device
        </button>
      </div>
    </div>
  )
}
