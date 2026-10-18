import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { saveConfig } from '../services/api'
import { showToast } from './Toast'
import { GraduationCap, ChevronRight, Sparkles } from 'lucide-react'

const SUBJECTS = ['Maths', 'English', 'Science', 'History', 'Geography', 'PDHPE', 'Technology', 'Art', 'Music', 'Commerce']

export default function Onboarding({ onComplete }) {
  const { config, setConfig } = useStore()
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [selectedSubjects, setSelectedSubjects] = useState([])

  // Escape closes the welcome dialog. No dep array: re-subscribe each render so
  // the handler always sees the latest name/subjects (avoiding a stale closure
  // that would save an empty name).
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') handleFinish() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (config.student_name && config.student_name !== 'Student') return null

  const toggleSubject = (s) => {
    setSelectedSubjects(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])
  }

  const handleFinish = async () => {
    const finalName = name.trim() || 'Student'
    try {
      await saveConfig({ student_name: finalName, subjects: selectedSubjects })
      setConfig({ ...config, student_name: finalName })
      showToast(`Welcome, ${finalName}! Let's start learning.`, 'success', 3000)
      onComplete?.()
    } catch {
      showToast('Setup saved locally', 'success', 2000)
      setConfig({ ...config, student_name: finalName })
      onComplete?.()
    }
  }

  // Escape closes the dialog; window-level for reliability — keep with the hook above
  return (
    <div className="fixed inset-0 z-50 bg-aria-bg flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Welcome to ARIA">
      <div className="w-full max-w-md">
        {step === 0 && (
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-[#8ab4f8]/15 flex items-center justify-center mx-auto mb-4">
              <GraduationCap size={32} className="text-[#8ab4f8]" />
            </div>
            <h1 className="text-[28px] font-normal text-aria-text mb-2">Welcome to ARIA</h1>
            <p className="text-sm text-aria-muted mb-8">Your personal AI learning coach. Let's get you set up.</p>
            <input
              type="text"
              value={name}
              aria-label="Your name"
              onChange={e => setName(e.target.value)}
              placeholder="What's your name?"
              className="w-full px-4 py-3 bg-aria-surface border border-aria-border rounded-xl text-aria-text placeholder-[#5f6368] outline-none focus:border-[#8ab4f8] text-center text-lg"
              ref={el => { if (el) el.focus() }}
              onKeyDown={e => e.key === 'Enter' && setStep(1)}
            />
            <button onClick={() => setStep(1)}
              className="mt-4 w-full py-3 rounded-xl bg-[#8ab4f8] text-[#062e6f] font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[#aecbfa] transition-colors">
              Continue <ChevronRight size={16} />
            </button>
          </div>
        )}

        {step === 1 && (
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-[#8ab4f8]/15 flex items-center justify-center mx-auto mb-3">
              <Sparkles size={24} className="text-[#8ab4f8]" />
            </div>
            <h2 className="text-[24px] font-normal text-aria-text mb-1">What are you studying?</h2>
            <p className="text-xs text-aria-muted mb-6">Pick your subjects — we'll tailor quizzes and focus areas.</p>
            <div className="flex flex-wrap gap-2 justify-center mb-6">
              {SUBJECTS.map(s => (
                <button key={s} onClick={() => toggleSubject(s)}
                  aria-pressed={selectedSubjects.includes(s)}
                  aria-label={`Study ${s}`}
                  className={`px-4 py-2 rounded-full text-sm border transition-all ${
                    selectedSubjects.includes(s)
                      ? 'bg-[#8ab4f8]/15 border-[#8ab4f8] text-[#8ab4f8]'
                      : 'bg-aria-surface border-aria-border text-aria-muted hover:border-[#3c4043]'
                  }`}>
                  {s}
                </button>
              ))}
            </div>
            <button onClick={handleFinish}
              className="w-full py-3 rounded-xl bg-[#8ab4f8] text-[#062e6f] font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[#aecbfa] transition-colors">
              Start learning <Sparkles size={14} />
            </button>
            <button onClick={handleFinish} className="mt-2 text-xs text-aria-muted hover:text-aria-text">
              Skip for now
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
