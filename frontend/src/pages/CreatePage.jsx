import { useState, lazy, Suspense } from 'react'
import { BookOpen, Layers, CalendarClock, Calculator, Sigma } from 'lucide-react'

const QuizPage = lazy(() => import('./QuizPage'))
const FlashcardsPage = lazy(() => import('./FlashcardsPage'))
const ExamPlanPage = lazy(() => import('./ExamPlanPage'))
const GradeCalculatorPage = lazy(() => import('./GradeCalculatorPage'))
const MathsAcceleratorPage = lazy(() => import('./MathsAcceleratorPage'))

const TABS = [
  { id: 'quiz', label: 'Quiz', icon: BookOpen, comp: QuizPage },
  { id: 'maths', label: 'Maths Accel', icon: Sigma, comp: MathsAcceleratorPage },
  { id: 'flashcards', label: 'Flashcards', icon: Layers, comp: FlashcardsPage },
  { id: 'examplan', label: 'Exam Plan', icon: CalendarClock, comp: ExamPlanPage },
  { id: 'grades', label: 'Am I Cooked?', icon: Calculator, comp: GradeCalculatorPage },
]

export default function CreatePage() {
  const [tab, setTab] = useState('quiz')
  const Active = TABS.find(t => t.id === tab)?.comp

  return (
    <div className="flex flex-col h-full w-full">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-[#1a1a1a] bg-[#0f0f0f] sticky top-0 z-10">
        <span className="text-xs font-semibold text-[#7c6af7] mr-2">Create</span>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition-colors ${tab===id ? 'bg-[#7c6af7] text-white' : 'text-[#666] hover:text-[#aaa] hover:bg-[#1a1a1a]'}`}>
            <Icon size={12}/>{label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-[#333] hidden sm:block">Or just ask in Chat — everything works there too</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<div className="p-8 text-center text-sm text-[#555]">Loading…</div>}>
          {Active && <Active />}
        </Suspense>
      </div>
    </div>
  )
}
