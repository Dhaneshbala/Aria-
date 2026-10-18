import { useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, MessageCircle, PlusSquare, Layers, Mic } from 'lucide-react'

const TABS = [
  { path: '/', label: 'Home', icon: LayoutDashboard },
  { path: '/chat', label: 'Chat', icon: MessageCircle },
  { path: '/create', label: 'Create', icon: PlusSquare },
  { path: '/spaced', label: 'Review', icon: Layers },
  { path: '/voice', label: 'Voice', icon: Mic },
]

/**
 * MobileNav — thumb-friendly bottom tab bar for phones.
 * Desktop keeps the Sidebar; this only renders below md.
 */
export default function MobileNav() {
  const location = useLocation()
  const navigate = useNavigate()

  const active = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)

  return (
    <nav aria-label="Primary"
      className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-aria-border bg-aria-bg/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]">
      <div className="grid grid-cols-5">
        {TABS.map(({ path, label, icon: Icon }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            aria-label={label}
            aria-current={active(path) ? 'page' : undefined}
            className={`flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors ${
              active(path) ? 'text-[#8ab4f8]' : 'text-aria-muted hover:text-aria-text'
            }`}
          >
            <Icon size={20} />
            {label}
          </button>
        ))}
      </div>
    </nav>
  )
}
