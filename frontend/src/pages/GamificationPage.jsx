import { useState, useEffect } from 'react'
import { Trophy, Flame, Target, Star, Zap, Medal, Crown, Award } from 'lucide-react'
import { showToast } from '../components/Toast'

const CATEGORY_COLORS = {
  milestone: { bg: 'bg-[#7c6af7]/10', border: 'border-[#7c6af7]/30', text: 'text-[#a89bf8]', dot: 'bg-[#7c6af7]' },
  streak:    { bg: 'bg-[#f59e0b]/10', border: 'border-[#f59e0b]/30', text: 'text-[#f59e0b]', dot: 'bg-[#f59e0b]' },
  achievement: { bg: 'bg-[#10b981]/10', border: 'border-[#10b981]/30', text: 'text-[#10b981]', dot: 'bg-[#10b981]' },
  special:   { bg: 'bg-[#06b6d4]/10', border: 'border-[#06b6d4]/30', text: 'text-[#06b6d4]', dot: 'bg-[#06b6d4]' },
}

export default function GamificationPage() {
  const [progress, setProgress] = useState(null)
  const [challenge, setChallenge] = useState(null)
  const [leaderboard, setLeaderboard] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [p, c, l] = await Promise.all([
        fetch('/api/v2/game/progress').then(r => r.json()),
        fetch('/api/v2/game/challenge').then(r => r.json()),
        fetch('/api/v2/game/leaderboard').then(r => r.json()),
      ])
      setProgress(p)
      setChallenge(c)
      setLeaderboard(l)
    } catch (e) {
      showToast('Failed to load gamification data', 'error')
    }
    setLoading(false)
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const xpPercent = progress ? ((100 - progress.xp_to_next) / 100) * 100 : 0
  const earnedSet = new Set((progress?.achievements || []).map(a => a.id))

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto w-full px-4 py-6 page-enter">
        {/* Level & XP Bar */}
        <div className="flex items-center gap-2 mb-6">
          <Trophy size={20} className="text-[#7c6af7]" />
          <h1 className="text-lg font-semibold text-[#e8e8e8]">Achievements & Challenges</h1>
        </div>

        {progress && (
          <div className="p-5 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-[#7c6af7]/15 border border-[#7c6af7]/30 flex items-center justify-center">
                  <Crown size={22} className="text-[#7c6af7]" />
                </div>
                <div>
                  <p className="text-xs text-[#888]">Level</p>
                  <p className="text-2xl font-bold text-[#e8e8e8]">{progress.level}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-[#888]">Total XP</p>
                <p className="text-xl font-bold text-[#f59e0b]">{progress.xp}</p>
              </div>
            </div>
            <div className="w-full h-3 rounded-full bg-[#252540]">
              <div className="h-3 rounded-full bg-gradient-to-r from-[#7c6af7] to-[#a89bf8] transition-all"
                style={{ width: `${xpPercent}%` }} />
            </div>
            <p className="text-xs text-[#666] mt-2 text-right">{progress.xp_to_next} XP to next level</p>
            <div className="flex items-center gap-4 mt-3 pt-3 border-t border-[#2a2a40]">
              <div className="flex items-center gap-1.5">
                <Award size={14} className="text-[#10b981]" />
                <span className="text-xs text-[#888]">{progress.achievements_earned}/{progress.total_achievements} badges</span>
              </div>
              <div className="flex-1 h-1.5 rounded-full bg-[#252540]">
                <div className="h-1.5 rounded-full bg-[#10b981]" style={{ width: `${progress.percentage}%` }} />
              </div>
              <span className="text-xs text-[#10b981]">{progress.percentage}%</span>
            </div>
          </div>
        )}

        {/* Today's Challenge */}
        {challenge && (
          <div className="p-4 rounded-2xl bg-gradient-to-r from-[#f59e0b]/10 to-[#7c6af7]/10 border border-[#f59e0b]/30 mb-6">
            <div className="flex items-center gap-2 mb-2">
              <Zap size={16} className="text-[#f59e0b]" />
              <span className="text-xs font-semibold text-[#f59e0b] uppercase tracking-wide">Daily Challenge</span>
            </div>
            <h3 className="text-base font-bold text-[#e8e8e8] mb-1">{challenge.name}</h3>
            <p className="text-sm text-[#aaa]">{challenge.desc}</p>
            <div className="flex items-center gap-3 mt-3">
              <span className="px-2.5 py-1 rounded-full bg-[#f59e0b]/15 text-[#f59e0b] text-xs font-medium">
                +{challenge.xp_reward} XP
              </span>
              <span className="text-xs text-[#666] capitalize">{challenge.type} challenge</span>
            </div>
          </div>
        )}

        {/* Leaderboard */}
        {leaderboard && leaderboard.entries?.length > 0 && (
          <div className="p-4 rounded-2xl bg-[#1a1a2e] border border-[#2a2a40] mb-6">
            <div className="flex items-center gap-2 mb-4">
              <Medal size={16} className="text-[#06b6d4]" />
              <span className="text-sm font-semibold text-[#e8e8e8]">Subject Leaderboard</span>
            </div>
            <div className="overflow-hidden rounded-xl border border-[#2a2a40]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[#252540]">
                    <th className="text-left px-3 py-2 text-xs text-[#888] font-medium">Rank</th>
                    <th className="text-left px-3 py-2 text-xs text-[#888] font-medium">Subject</th>
                    <th className="text-right px-3 py-2 text-xs text-[#888] font-medium">Accuracy</th>
                    <th className="text-right px-3 py-2 text-xs text-[#888] font-medium">XP</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.entries.map((entry, i) => (
                    <tr key={i} className={`border-t border-[#2a2a40] ${i === 0 ? 'bg-[#f59e0b]/5' : ''}`}>
                      <td className="px-3 py-2.5 text-[#aaa]">{entry.rank}</td>
                      <td className="px-3 py-2.5 text-[#e8e8e8] capitalize">{entry.subject}</td>
                      <td className="px-3 py-2.5 text-right">
                        <span className={entry.accuracy >= 80 ? 'text-[#10b981]' : entry.accuracy >= 50 ? 'text-[#f59e0b]' : 'text-red-400'}>
                          {entry.accuracy}%
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right text-[#f59e0b]">{entry.xp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#2a2a40]">
              <span className="text-xs text-[#666]">Total XP: {leaderboard.total_xp}</span>
              <span className="text-xs text-[#666]">Level: {leaderboard.level}</span>
            </div>
          </div>
        )}

        {/* Achievement Badges Grid */}
        {progress?.all_achievements && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Star size={16} className="text-[#7c6af7]" />
              <span className="text-sm font-semibold text-[#e8e8e8]">All Achievements</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {progress.all_achievements.map(ach => {
                const earned = earnedSet.has(ach.id)
                const colors = CATEGORY_COLORS[ach.category] || CATEGORY_COLORS.milestone
                return (
                  <div
                    key={ach.id}
                    className={`p-4 rounded-xl border transition-all ${
                      earned
                        ? `${colors.bg} ${colors.border}`
                        : 'bg-[#1a1a2e] border-[#2a2a40] opacity-50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xl">{ach.icon}</span>
                      {earned && <Flame size={12} className={colors.text} />}
                    </div>
                    <p className="text-sm font-semibold text-[#e8e8e8]">{ach.name}</p>
                    <p className="text-xs text-[#666] mt-0.5">{ach.desc}</p>
                    <div className="flex items-center gap-1.5 mt-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
                      <span className={`text-[10px] uppercase tracking-wide ${colors.text}`}>
                        {ach.category}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
