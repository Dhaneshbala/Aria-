import { useState, useEffect } from 'react'
import { getProfile } from '../services/api'
import { User, TrendingUp, TrendingDown, Star, Target } from 'lucide-react'

export default function ProfilePage() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const accuracy = profile?.total_questions > 0
    ? Math.round((profile.correct_answers / profile.total_questions) * 100)
    : 0

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-6">
        <User size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Study Profile</h1>
      </div>

      {/* Overview */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatCard icon={<Target size={18} className="text-[#7c6af7]" />}
          label="Accuracy" value={`${accuracy}%`} />
        <StatCard icon={<Star size={18} className="text-yellow-400" />}
          label="Questions" value={profile?.total_questions || 0} />
        <StatCard icon={<TrendingUp size={18} className="text-green-400" />}
          label="Streak" value={`${profile?.streak || 0}d`} />
      </div>

      {/* Subject breakdown */}
      {Object.keys(profile?.subjects || {}).length > 0 && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 mb-4">
          <h3 className="text-sm font-medium text-[#e8e8e8] mb-3">Subjects</h3>
          <div className="space-y-3">
            {Object.entries(profile.subjects).map(([subj, stats]) => {
              const ratio = stats.total > 0 ? stats.correct / stats.total : 0
              return (
                <div key={subj}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-[#aaa] capitalize">{subj}</span>
                    <span className="text-[#777]">{stats.correct}/{stats.total}</span>
                  </div>
                  <div className="w-full bg-[#2a2a2a] rounded-full h-1.5">
                    <div className="h-1.5 rounded-full transition-all"
                      style={{
                        width: `${ratio * 100}%`,
                        background: ratio >= 0.8 ? '#4ade80' : ratio >= 0.5 ? '#7c6af7' : '#f87171'
                      }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Weak / Strong areas */}
      <div className="grid grid-cols-2 gap-3">
        <AreaCard
          icon={<TrendingDown size={14} className="text-red-400" />}
          title="Needs Work"
          items={profile?.weak_areas || []}
          color="text-red-400"
          empty="Keep practising to see weak areas"
        />
        <AreaCard
          icon={<TrendingUp size={14} className="text-green-400" />}
          title="Strong Areas"
          items={profile?.strong_areas || []}
          color="text-green-400"
          empty="Complete quizzes to track strengths"
        />
      </div>

      {/* Last active */}
      {profile?.last_active && (
        <p className="text-xs text-[#555] mt-4 text-center">
          Last active: {new Date(profile.last_active).toLocaleDateString()}
        </p>
      )}
    </div>
  )
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 text-center">
      <div className="flex justify-center mb-2">{icon}</div>
      <p className="text-xl font-bold text-[#e8e8e8]">{value}</p>
      <p className="text-xs text-[#555] mt-0.5">{label}</p>
    </div>
  )
}

function AreaCard({ icon, title, items, color, empty }) {
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4">
      <div className="flex items-center gap-1.5 mb-3">
        {icon}
        <span className="text-xs font-medium text-[#e8e8e8]">{title}</span>
      </div>
      {items.length === 0
        ? <p className="text-xs text-[#444]">{empty}</p>
        : items.map(item => (
          <p key={item} className={`text-xs ${color} capitalize mb-1`}>• {item}</p>
        ))
      }
    </div>
  )
}
