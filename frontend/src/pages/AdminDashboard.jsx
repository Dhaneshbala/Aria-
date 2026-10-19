import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import {
  LayoutDashboard, Users, ScrollText, Plug, ShieldCheck, Activity,
  MessagesSquare, RefreshCw, Search, DollarSign, Lock, CheckCircle2,
  XCircle, Settings,
} from 'lucide-react'
import { API_BASE, apiFetch } from '../services/api'
import { adminUnlock } from '../services/auth'
import { useStore } from '../store'

const AdminPage = lazy(() => import('./AdminPage'))

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'credits', label: 'Credits & audit', icon: ScrollText },
  { id: 'providers', label: 'Providers & budget', icon: Plug },
  { id: 'feedback', label: 'Feedback', icon: MessagesSquare },
  { id: 'health', label: 'Health', icon: Activity },
  { id: 'studio', label: 'Studio', icon: Settings },
]

async function adminJson(path, options = {}) {
  const r = await apiFetch(`${API_BASE}/v2/admin${path}`, options)
  return r.json()
}

const post = (path, body) =>
  adminJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
const patch = (path, body) =>
  adminJson(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

const money = (usd) =>
  usd == null ? '—' : `$${Number(usd).toFixed(usd !== 0 && Math.abs(usd) < 0.01 ? 6 : 2)}`

/* ── Step-up: every admin MUTATION re-verifies the password first. ───── */

function useAdminActions(reload) {
  const user = useStore(s => s.authUser)
  const [stepUpOpen, setStepUpOpen] = useState(false)
  const [pending, setPending] = useState(null) // {label, run}
  const [stepUpError, setStepUpError] = useState('')
  const [stepUpBusy, setStepUpBusy] = useState(false)
  const [actionError, setActionError] = useState('')

  const withStepUp = useCallback((label, run) => {
    setPending({ label, run })
    setStepUpError('')
    setStepUpOpen(true)
  }, [])

  async function confirmStepUp(password) {
    setStepUpBusy(true)
    setStepUpError('')
    try {
      await adminUnlock(user?.username || '', password)
      try {
        await pending.run(post)
        reload()
      } catch (e) {
        setActionError(e.message || 'The change could not be applied.')
        setStepUpOpen(false)
        setPending(null)
        return true
      }
      setStepUpOpen(false)
      setPending(null)
      return true
    } catch (e) {
      setStepUpError(e.message || 'Re-verification failed.')
      return false
    } finally {
      setStepUpBusy(false)
    }
  }

  return {
    withStepUp,
    stepUpOpen, stepUpError, stepUpBusy,
    confirmStepUp,
    closeStepUp: () => { setStepUpOpen(false); setPending(null) },
    pendingLabel: pending?.label || '',
    actionError, dismissActionError: () => setActionError(''),
  }
}

function StepUpModal({ open, label, error, busy, onConfirm, onClose }) {
  const [password, setPassword] = useState('')
  useEffect(() => { if (open) setPassword('') }, [open])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center px-4">
      <div className="bg-[#141414] border border-[#2a2a2a] rounded-2xl p-5 w-full max-w-sm">
        <div className="flex items-center gap-2 mb-3">
          <Lock size={16} className="text-[#7c6af7]" />
          <h2 className="text-sm font-semibold text-[#e8e8e8]">Confirm it&apos;s you</h2>
        </div>
        <p className="text-[11px] text-[#9aa0a6] mb-3">
          <span className="text-[#e8e8e8]">{label}</span> is audited with your name on it.
          Re-enter your password to unlock admin actions for 15 minutes.
        </p>
        <form onSubmit={async e => { e.preventDefault(); if (await onConfirm(password)) setPassword('') }}>
          <input
            type="password" autoFocus value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#e8e8e8] focus:border-[#5f6368] outline-none mb-2"
          />
          {error && <p className="text-xs text-red-300 mb-2">{error}</p>}
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-xs text-[#9aa0a6]">
              Cancel
            </button>
            <button type="submit" disabled={busy || !password}
              className="px-4 py-2 rounded-full bg-[#7c6af7] hover:bg-[#6a58e0] text-xs text-white disabled:opacity-40">
              {busy ? 'Verifying…' : 'Unlock & apply'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ── Shared bits ─────────────────────────────────────────────────────── */

function Panel({ title, sub, children }) {
  return (
    <div className="bg-[#141414] border border-aria-border rounded-xl p-4">
      <h2 className="text-xs text-[#888] font-semibold">{title}</h2>
      {sub && <p className="text-[10px] text-[#555] mt-0.5 mb-2">{sub}</p>}
      {!sub && <div className="mb-2" />}
      {children}
    </div>
  )
}

function KvRow({ k, v }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 border-b border-[#1d1d1d] last:border-0">
      <span className="text-[11px] text-[#888] shrink-0">{k}</span>
      <span className="text-[11px] text-[#e8e8e8] text-right break-words">{String(v)}</span>
    </div>
  )
}

function Loading() {
  return <div className="p-10 text-center text-xs text-[#666] animate-pulse">Loading server data…</div>
}

function ErrorNote({ text }) {
  return (
    <div className="bg-red-500/10 border border-red-500/25 rounded-xl p-4">
      <p className="text-xs text-red-300">{text}</p>
      <p className="text-[10px] text-red-200/60 mt-1">
        The backend independently enforces admin permissions — data only loads for
        admin sessions.
      </p>
    </div>
  )
}

/* ── Overview ────────────────────────────────────────────────────────── */

function OverviewTab() {
  const [ov, setOv] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    adminJson('/overview').then(setOv).catch(e => setErr(e.message))
  }, [])
  if (err) return <ErrorNote text={err} />
  if (!ov) return <Loading />
  const u = ov.users || {}
  const cards = [
    ['Accounts', u.total ?? 0, `${u.active ?? 0} active · ${u.suspended ?? 0} suspended`],
    ['New sign-ups (7d)', u.new_last_7d ?? 0, `${u.new_last_30d ?? 0} in 30 days`],
    ['Daily active (24h)', u.dau ?? 0, `${u.mau ?? 0} monthly`],
    ['Free / premium', `${u.free ?? 0} / ${u.premium ?? 0}`, 'plans come from the server'],
    ['Open feedback', ov.feedback_open ?? 0, 'unresolved reports'],
  ]
  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
        {cards.map(([label, value, sub]) => (
          <div key={label} className="bg-[#141414] border border-aria-border rounded-xl p-4">
            <p className="text-[11px] text-[#888]">{label}</p>
            <p className="text-xl font-semibold text-[#e8e8e8] mt-1">{value}</p>
            <p className="text-[10px] text-[#666] mt-1">{sub}</p>
          </div>
        ))}
        <div className="bg-[#141414] border border-aria-border rounded-xl p-4">
          <p className="text-[11px] text-[#888]">Revenue</p>
          <p className="text-xl font-semibold text-[#e8e8e8] mt-1">—</p>
          <p className="text-[10px] text-[#666] mt-1">
            Payments are not implemented yet — no invented numbers.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Panel title="AI usage (all users, 30d)" sub="token counts provider-reported; cost is an estimate">
          <KvRow k="Requests" v={ov.ai_usage?.requests ?? 0} />
          <KvRow k="Prompt tokens" v={ov.ai_usage?.prompt_tokens ?? 0} />
          <KvRow k="Completion tokens" v={ov.ai_usage?.completion_tokens ?? 0} />
          <KvRow k="Estimated cost" v={money(ov.ai_usage?.estimated_cost_usd)} />
        </Panel>
        <Panel title="Credit wallet totals" sub="micro-dollar ledger, exact">
          <KvRow k="Outstanding balances" v={money(ov.credits?.outstanding_usd)} />
          <KvRow k="Granted (all time)" v={money(ov.credits?.granted_usd)} />
          <KvRow k="Spent on cloud usage" v={money(ov.credits?.usage_spent_usd)} />
          <KvRow k="Ledger rows" v={ov.credits?.ledger_rows ?? 0} />
        </Panel>
      </div>
      <div className="bg-[#141414] border border-aria-border rounded-xl p-4 mt-3">
        <p className="text-[11px] text-[#888] mb-1">Global cloud budget</p>
        {ov.budget?.daily_budget_usd == null ? (
          <p className="text-xs text-[#c2e7ff]">
            No daily cap set — cloud calls allowed while wallets have credit.
          </p>
        ) : (
          <p className="text-xs text-[#e8e8e8]">
            ${ov.budget.daily_budget_usd} / day — spent today {money(ov.budget.spent_today_usd)} ·{' '}
            <span className={ov.budget.status === 'exhausted' ? 'text-red-400' : 'text-green-400'}>
              {ov.budget.status}
            </span>
          </p>
        )}
      </div>
    </div>
  )
}

/* ── Users ───────────────────────────────────────────────────────────── */

function UsersTab({ actions, reloadKey }) {
  const [users, setUsers] = useState([])
  const [err, setErr] = useState('')
  const [q, setQ] = useState('')
  const me = useStore(s => s.authUser)

  useEffect(() => {
    adminJson(`/users${q ? `?q=${encodeURIComponent(q)}` : ''}`)
      .then(d => setUsers(d.users || []))
      .catch(e => setErr(e.message))
  }, [q, reloadKey])

  function act(label, uid, body) {
    const defaultReason = {
      suspended: `suspend ${uid}`,
      active: `restore ${uid}`,
      plan_change: 'plan change',
      role_change: 'role change',
    }
    actions.withStepUp(label, async p => {
      await p(`/users/${uid}`, body)
    })
    void defaultReason
  }

  if (err) return <ErrorNote text={err} />
  return (
    <div>
      <div className="flex items-center gap-2 bg-[#141414] border border-[#2a2a2a] rounded-full px-3 py-2 mb-3 w-full sm:w-72">
        <Search size={13} className="text-[#9aa0a6]" />
        <input
          placeholder="Search usernames" value={q} onChange={e => setQ(e.target.value)}
          className="bg-transparent text-xs text-[#e8e8e8] placeholder-[#666] flex-1 outline-none"
        />
      </div>
      <div className="bg-[#141414] border border-aria-border rounded-xl divide-y divide-[#222]">
        {users.map(u => (
          <div key={u.id} className="px-4 py-3 flex flex-wrap items-center gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-xs text-[#e8e8e8] truncate">
                {u.display_name || u.username}
                {u.username === me?.username && <span className="text-[#7c6af7]"> (you)</span>}
              </p>
              <p className="text-[10px] text-[#666] mt-0.5">
                {u.username} · {u.role} · {u.plan} ·{' '}
                <span className={u.status === 'active' ? 'text-green-400' : 'text-red-400'}>{u.status}</span>
                {' '}· balance {money(u.balance_usd)}
                {u.last_seen_at ? ` · seen ${String(u.last_seen_at).slice(0, 10)}` : ''}
              </p>
            </div>
            {u.status === 'active' ? (
              <button
                onClick={() => {
                  const reason = prompt(`Reason for suspending ${u.username} (recorded in audit):`)
                  if (reason) act(`Suspend ${u.username}`, u.id, { status: 'suspended', reason })
                }}
                className="px-3 py-1.5 rounded-full bg-red-500/10 hover:bg-red-500/20 text-[10px] text-red-300">
                Suspend
              </button>
            ) : (
              <button
                onClick={() => {
                  const reason = prompt(`Reason for restoring ${u.username} (recorded in audit):`)
                  if (reason) act(`Restore ${u.username}`, u.id, { status: 'active', reason })
                }}
                className="px-3 py-1.5 rounded-full bg-green-500/10 hover:bg-green-500/20 text-[10px] text-green-300">
                Restore
              </button>
            )}
            <button
              onClick={() => {
                const reason = prompt(`Reason for the plan change (recorded in audit):`)
                if (reason) act(`Plan change for ${u.username}`, u.id, {
                  plan: u.plan === 'free' ? 'premium' : 'free', reason,
                })
              }}
              className="px-3 py-1.5 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[10px] text-[#c2e7ff]">
              {u.plan === 'free' ? 'Set premium' : 'Set free'}
            </button>
            {me?.role === 'superadmin' && u.username !== me.username && (
              <button
                onClick={() => {
                  const role = prompt(`New role for ${u.username} (student / admin / superadmin):`)
                  if (role) act(`Role change for ${u.username}`, u.id, { role, reason: 'confirmed role change' })
                }}
                className="px-3 py-1.5 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[10px] text-[#9aa0a6]">
                Role…
              </button>
            )}
          </div>
        ))}
        {!users.length && (
          <p className="text-xs text-[#777] px-4 py-6 text-center">No accounts match.</p>
        )}
      </div>
    </div>
  )
}

/* ── Credits + audit ─────────────────────────────────────────────────── */

function CreditsTab({ actions, reloadKey }) {
  const [ledger, setLedger] = useState(null)
  const [auditData, setAuditData] = useState(null)
  const [target, setTarget] = useState('')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    adminJson('/credits/ledger?limit=100').then(setLedger).catch(() => {})
    adminJson('/audit?limit=60').then(setAuditData).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load, reloadKey])

  function grant(e) {
    e.preventDefault()
    setErr('')
    const uid = parseInt(target, 10)
    const delta = parseFloat(amount)
    if (!Number.isInteger(uid) || !delta) {
      setErr('Enter the user id (shown in the Users tab) and a non-zero amount.')
      return
    }
    actions.withStepUp(
      `Credit ${delta > 0 ? 'grant' : 'adjustment'} of ${money(delta)} to user #${uid}`,
      async p => {
        const r = await p(`/credits/${uid}`, {
          delta_dollars: delta, reason, kind: delta > 0 ? 'grant' : 'adjustment',
        })
        setNote(`Done — new balance ${money(r.balance_usd)}.`)
      },
    )
  }

  return (
    <div className="space-y-3">
      {!ledger?.chain_ok && ledger && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/25 rounded-xl px-3 py-2">
          <XCircle size={14} className="text-red-400" />
          <p className="text-xs text-red-300">
            Audit chain verification FAILED — investigate on the server before trusting records.
          </p>
        </div>
      )}
      {ledger?.chain_ok && (
        <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-xl px-3 py-2">
          <CheckCircle2 size={14} className="text-green-400" />
          <p className="text-xs text-green-300">Audit hash chain verified — records are tamper-evident.</p>
        </div>
      )}

      <Panel title="Manual credit adjustment" sub="server-validated, transactional, every change written to the ledger">
        <form onSubmit={grant} className="flex flex-wrap gap-2 items-end">
          <label>
            <span className="text-[10px] text-[#888] block">User id</span>
            <input value={target} onChange={e => setTarget(e.target.value)} inputMode="numeric"
              className="mt-1 w-20 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-[#e8e8e8] outline-none" />
          </label>
          <label>
            <span className="text-[10px] text-[#888] block">Amount USD (− deducts)</span>
            <input value={amount} onChange={e => setAmount(e.target.value)} inputMode="decimal" placeholder="5.00 or -2"
              className="mt-1 w-36 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-[#e8e8e8] outline-none" />
          </label>
          <label className="flex-1 min-w-40">
            <span className="text-[10px] text-[#888] block">Reason (required, audited)</span>
            <input value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. pilot starter grant"
              className="mt-1 w-full bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-[#e8e8e8] outline-none" />
          </label>
          <button type="submit" disabled={!target || !amount || reason.trim().length < 3}
            className="flex items-center gap-1 px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[10px] text-[#c2e7ff] disabled:opacity-40">
            <DollarSign size={12} /> Apply
          </button>
        </form>
        {(note || err) && (
          <p className={`text-[11px] mt-2 ${err ? 'text-red-300' : 'text-green-300'}`}>{err || note}</p>
        )}
      </Panel>

      <Panel title="Credit ledger (latest 100)" sub="every balance change with its reason and resulting balance">
        {ledger?.entries?.length ? (
          <div className="space-y-1">
            {ledger.entries.map(e => (
              <div key={e.id} className="flex items-center justify-between text-[11px] py-1 border-b border-[#1d1d1d]">
                <span className="text-[#9aa0a6] w-30 shrink-0">{e.ts?.slice(0, 16).replace('T', ' ')}</span>
                <span className="text-[#e8e8e8] truncate max-w-40 mx-2">{e.username || `user ${e.user_id}`}</span>
                <span className={`font-semibold ${e.delta_usd < 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {e.delta_usd < 0 ? '−' : '+'}{money(Math.abs(e.delta_usd))}
                </span>
                <span className="text-[#666] truncate hidden sm:block flex-1 mx-2">{e.reason}</span>
                <span className="text-[#555] shrink-0">{e.kind}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[#777] py-3 text-center">No ledger entries yet.</p>
        )}
      </Panel>

      <Panel title="Audit log (latest 60)" sub="who did what, when, why — append-only, hash-chained">
        {auditData?.entries?.length ? (
          <div className="space-y-1">
            {auditData.entries.map(a => (
              <div key={a.id} className="text-[11px] py-1 border-b border-[#1d1d1d] flex gap-2">
                <span className="text-[#666] shrink-0">{a.ts?.slice(0, 16).replace('T', ' ')}</span>
                <span className="text-[#c2e7ff] shrink-0">{a.action}</span>
                <span className="text-[#9aa0a6] truncate" title={a.reason || ''}>
                  {a.username || 'system'}{a.target ? ` → ${a.target}` : ''}
                  {a.reason ? ` — ${a.reason}` : ''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[#777] py-3 text-center">No audit entries yet.</p>
        )}
      </Panel>
    </div>
  )
}

/* ── Providers & budget ──────────────────────────────────────────────── */

function ProvidersTab({ actions, reloadKey }) {
  const [providerInfo, setProviderInfo] = useState(null)
  const [budgetInput, setBudgetInput] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    adminJson('/providers').then(setProviderInfo).catch(e => setErr(e.message))
  }, [reloadKey])

  function saveBudget(e) {
    e.preventDefault()
    const v = budgetInput.trim()
    const usd = v === '' ? null : parseFloat(v)
    actions.withStepUp(`Cloud budget ${usd == null ? 'removed' : `set to ${money(usd)}`}`, async p => {
      const r = await p('/budget', { daily_budget_usd: usd, reason: 'Operator setting (providers tab)' })
      setProviderInfo(prev => ({ ...(prev || {}), budget_state: r }))
      setNote(usd == null ? 'Budget removed.' : `Budget set: ${money(r.daily_budget_usd)}/day.`)
      setBudgetInput('')
    })
  }

  if (err) return <ErrorNote text={err} />
  if (!providerInfo) return <Loading />
  const bs = providerInfo.budget_state || {}
  return (
    <div className="space-y-3">
      <Panel title="Cloud provider" sub="keys live server-side; values are never shown or returned">
        <KvRow k="ANTHROPIC key configured" v={providerInfo.anthropic_key_configured ? 'yes' : 'no (local models only)'} />
        <KvRow k="Cloud consent" v={providerInfo.cloud_consent ? 'granted' : 'not granted'} />
        <p className="text-[10px] text-[#555] mt-2">{providerInfo.secret_note}</p>
      </Panel>

      <Panel title="Daily cloud budget" sub="hard stop at dispatch — individual wallets cap separately">
        <form onSubmit={saveBudget} className="flex flex-wrap gap-2 items-end">
          <label>
            <span className="text-[10px] text-[#888] block">USD per day (empty = no cap)</span>
            <input value={budgetInput} onChange={e => setBudgetInput(e.target.value)} inputMode="decimal" placeholder="5.00"
              className="mt-1 w-28 bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs text-[#e8e8e8] outline-none" />
          </label>
          <button type="submit" className="px-4 py-2 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[10px] text-[#c2e7ff]">
            {bs.daily_budget_usd == null ? 'Set budget' : 'Update'} / remove
          </button>
        </form>
        <div className="mt-2">
          <p className="text-[11px] text-[#9aa0a6]">
            Current: {bs.daily_budget_usd == null ? 'no cap' : `${money(bs.daily_budget_usd)}/day`} ·
            spent today {money(bs.spent_today_usd)}
            {bs.daily_budget_usd != null && (
              <span className={bs.status === 'exhausted' ? 'text-red-400' : 'text-green-400'}> ({bs.status})</span>
            )}
          </p>
          {note && <p className="text-[11px] text-green-300 mt-1">{note}</p>}
        </div>
      </Panel>

      {providerInfo.pricing && typeof providerInfo.pricing === 'object' && (
        <Panel title="Pricing used for estimates" sub="from config/pricing.py — the only cost source">
          <div className="space-y-1">
            {Object.entries(providerInfo.pricing).slice(0, 12).map(([model, p]) => {
              const pair = Array.isArray(p) ? p : [p?.input, p?.output]
              return (
                <div key={model} className="flex justify-between text-[11px] py-0.5 border-b border-[#1d1d1d]">
                  <span className="text-[#9aa0a6]">{model}</span>
                  <span className="text-[#e8e8e8]">
                    ${pair[0] ?? '?'} in / ${pair[1] ?? '?'} per MTok
                  </span>
                </div>
              )
            })}
          </div>
        </Panel>
      )}
      <Panel title="Model allowlists" sub="cloud models the back end accepts">
        <p className="text-[11px] text-[#9aa0a6]">{(providerInfo.allowlist_models || []).join(' · ') || '—'}</p>
      </Panel>
    </div>
  )
}

/* ── Feedback ────────────────────────────────────────────────────────── */

function FeedbackTab({ actions, reloadKey }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState('')
  useEffect(() => {
    adminJson('/feedback?open_only=true').then(d => setItems(d.feedback || [])).catch(e => setErr(e.message))
  }, [reloadKey])

  function resolve(id, status) {
    actions.withStepUp(`Mark feedback #${id} as ${status}`, async p => {
      await p(`/feedback/${id}`, { status, reason: `resolved from dashboard as ${status}` })
    })
  }

  if (err) return <ErrorNote text={err} />
  return (
    <div className="bg-[#141414] border border-aria-border rounded-xl divide-y divide-[#222]">
      {items.length ? items.map(f => (
        <div key={f.id} className="px-4 py-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#004a77] text-[#c2e7ff]">{f.kind}</span>
            <span className="text-[10px] text-[#666]">{f.user_name} · {f.ts?.slice(0, 16).replace('T', ' ')}</span>
            <button onClick={() => resolve(f.id, 'done')}
              className="ml-auto px-3 py-1.5 rounded-full bg-green-500/10 hover:bg-green-500/20 text-[10px] text-green-300">
              Mark done
            </button>
            <button onClick={() => resolve(f.id, 'wont_do')}
              className="px-3 py-1.5 rounded-full bg-[#2d2e30] hover:bg-[#35363a] text-[10px] text-[#9aa0a6]">
              Won&apos;t do
            </button>
          </div>
          <p className="text-xs text-[#e8e8e8] whitespace-pre-wrap break-words">{f.message}</p>
        </div>
      )) : (
        <p className="text-xs text-[#777] px-4 py-8 text-center">No open feedback — inbox zero.</p>
      )}
    </div>
  )
}

/* ── Health ──────────────────────────────────────────────────────────── */

function HealthTab({ reloadKey }) {
  const [h, setH] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    adminJson('/health').then(setH).catch(e => setErr(e.message))
  }, [reloadKey])
  if (err) return <ErrorNote text={err} />
  if (!h) return <Loading />
  return (
    <div className="space-y-3">
      <Panel title="System" sub="server-reported, live probe">
        <KvRow k="Backend" v={h.backend} />
        <KvRow k="Version" v={h.version} />
        <KvRow k="Auth mode" v={h.auth_mode} />
        <KvRow k="Ollama" v={h.ollama ? 'reachable' : 'not reachable — restart options live in Studio'} />
        <KvRow k="Disk free" v={`${h.disk?.free_gb} of ${h.disk?.total_gb} GB`} />
        <KvRow k="Audit chain" v={h.database?.audit_chain_ok ? 'verified' : 'FAILED'} />
        <KvRow k="Users table" v={h.database?.users_ok ? 'ok' : 'error'} />
        <KvRow k="Background jobs" v={`${h.background_jobs?.tracked ?? 0} tracked, ${h.background_jobs?.failed ?? 0} failed`} />
        <KvRow k="Backups present" v={h.backups_found ?? 0} />
      </Panel>
      <p className="text-[10px] text-[#555]">{h.data_dir_size_note}</p>
    </div>
  )
}

/* ── Shell ───────────────────────────────────────────────────────────── */

export default function AdminDashboard() {
  const [tab, setTab] = useState('overview')
  const [reloadKey, setReloadKey] = useState(0)
  const user = useStore(s => s.authUser)
  const reload = useCallback(() => setReloadKey(k => k + 1), [])
  const actions = useAdminActions(reload)

  // Any user actionable error surfaces briefly at the top of the shell.
  useEffect(() => {
    if (!actions.actionError) return
    const t = setTimeout(() => actions.dismissActionError(), 6000)
    return () => clearTimeout(t)
  }, [actions.actionError])

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter overflow-y-auto h-full">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} className="text-[#7c6af7]" />
          <h1 className="text-lg font-semibold text-[#e8e8e8]">Admin dashboard</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#7c6af7]/15 text-[#a89bf8]">
            {user?.username} ({user?.role})
          </span>
        </div>
        <button onClick={reload}
          className="flex items-center gap-1.5 text-xs text-[#9aa0a6] hover:text-[#e8e8e8] transition-colors">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {actions.actionError && (
        <div className="flex items-center justify-between bg-red-500/10 border border-red-500/25 rounded-xl px-3 py-2 mb-3">
          <p className="text-xs text-red-300">{actions.actionError}</p>
          <button onClick={actions.dismissActionError} className="text-[10px] text-red-200/70">Dismiss</button>
        </div>
      )}

      <div className="flex gap-1 overflow-x-auto mb-4 bg-[#141414] border border-[#2a2a2a] rounded-full p-1 w-fit max-w-full">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs whitespace-nowrap transition-colors ${
              tab === id ? 'bg-[#2d2e30] text-[#c2e7ff]' : 'text-[#9aa0a6] hover:text-[#e8e8e8]'
            }`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab />}
      {tab === 'users' && <UsersTab actions={actions} reloadKey={reloadKey} />}
      {tab === 'credits' && <CreditsTab actions={actions} reloadKey={reloadKey} />}
      {tab === 'providers' && <ProvidersTab actions={actions} reloadKey={reloadKey} />}
      {tab === 'feedback' && <FeedbackTab actions={actions} reloadKey={reloadKey} />}
      {tab === 'health' && <HealthTab reloadKey={reloadKey} />}
      {tab === 'studio' && (
        <Suspense fallback={<Loading />}>
          <AdminPage />
        </Suspense>
      )}

      <StepUpModal
        open={actions.stepUpOpen} label={actions.pendingLabel} error={actions.stepUpError}
        busy={actions.stepUpBusy} onConfirm={actions.confirmStepUp} onClose={actions.closeStepUp}
      />
    </div>
  )
}
