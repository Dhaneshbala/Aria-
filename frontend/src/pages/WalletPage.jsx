import { useEffect, useState } from 'react'
import { Wallet as WalletIcon, RefreshCw } from 'lucide-react'
import { getWallet } from '../services/auth'

const fmt = (usd) =>
  `$${Number(usd || 0).toFixed(4).replace(/0+$/, '').replace(/\.$/, '.00')}`

const KIND_LABEL = { grant: 'Admin grant', usage: 'Cloud usage', adjustment: 'Adjustment', refund: 'Refund', payment: 'Verified payment (manual)' }

/**
 * The student's credit wallet. Every number here comes from the
 * server-side ledger — nothing is computed in the browser. Purchases
 * are NOT implemented yet and the page says so plainly.
 */
export default function WalletPage() {
  const [wallet, setWallet] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setWallet(await getWallet())
    } catch (e) {
      setError(e.message || 'Could not load wallet.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="w-full px-6 lg:px-8 py-6 page-enter overflow-y-auto h-full">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <WalletIcon size={20} className="text-[#7c6af7]" />
          <h1 className="text-lg font-semibold text-[#e8e8e8]">Wallet</h1>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-xs text-[#9aa0a6] hover:text-[#e8e8e8] transition-colors"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-xl p-3 mb-4 text-xs text-red-300">{error}</div>
      )}

      {wallet && (
        <>
          <div className="bg-[#141414] border border-aria-border rounded-xl p-5 mb-4">
            <p className="text-[11px] text-[#888] mb-1">Balance</p>
            <p className="text-3xl font-semibold text-[#e8e8e8]">{fmt(wallet.balance_usd)}</p>
            <p className="text-[10px] text-[#666] mt-2">{wallet.payments_note}</p>
          </div>

          <h2 className="text-xs text-[#888] font-semibold mb-2">Recent ledger entries</h2>
          {wallet.history?.length ? (
            <div className="bg-[#141414] border border-aria-border rounded-xl divide-y divide-[#222]">
              {wallet.history.map((h, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-xs text-[#e8e8e8]">{KIND_LABEL[h.kind] || h.kind}</p>
                    <p className="text-[10px] text-[#777] truncate mt-0.5">{h.reason}</p>
                    <p className="text-[10px] text-[#555]">{h.ts}</p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className={`text-xs font-semibold ${h.delta_usd < 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {h.delta_usd < 0 ? '−' : '+'}{fmt(Math.abs(h.delta_usd))}
                    </p>
                    <p className="text-[10px] text-[#666]">→ {fmt(h.balance_usd)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-[#141414] border border-aria-border rounded-xl p-6 text-center">
              <p className="text-xs text-[#888]">No ledger entries yet — your balance is $0.</p>
              <p className="text-[10px] text-[#555] mt-1">
                Cloud models consume credit. Local models are always free.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
