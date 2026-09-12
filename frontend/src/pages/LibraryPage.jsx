import { useState, lazy, Suspense } from 'react'
import { Library, FileText, Youtube } from 'lucide-react'

const YouTubePage = lazy(() => import('./YouTubePage'))

const TABS = [
  { id: 'youtube', label: 'YouTube', icon: Youtube, comp: YouTubePage },
]

export default function LibraryPage() {
  const [tab, setTab] = useState('youtube')
  const Active = TABS.find(t => t.id === tab)?.comp
  return (
    <div className="flex flex-col h-full bg-[#131314] w-full">
      <div className="flex items-center gap-2 px-6 py-3 border-b border-[#2d2e30] bg-[#131314] sticky top-0 z-10">
        <span className="text-sm font-medium text-[#e3e3e3] mr-3 tracking-tight">Library</span>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${tab===id ? 'bg-[#8ab4f8] text-[#062e6f]' : 'text-[#9aa0a6] hover:text-[#e3e3e3] hover:bg-[#1e1f20]'}`}>
            <Icon size={14}/>{label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto w-full">
        <Suspense fallback={<div className="p-8 text-center text-sm text-[#9aa0a6]">Loading…</div>}>
          {Active && <Active />}
        </Suspense>
      </div>
    </div>
  )
}
