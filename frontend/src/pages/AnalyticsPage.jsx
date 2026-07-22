import { useState, useEffect } from 'react'
import { getHeatmap, getTrends, getPredictedGrades, getFocusScore, getWeeklySummary } from '../services/api'
import { showToast } from '../components/Toast'

export default function AnalyticsPage() {
  const [heatmap, setHeatmap] = useState(null)
  const [trends, setTrends] = useState(null)
  const [grades, setGrades] = useState(null)
  const [focus, setFocus] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [h, t, g, f, s] = await Promise.all([
        getHeatmap(6).catch(() => null),
        getTrends(30).catch(() => null),
        getPredictedGrades().catch(() => null),
        getFocusScore().catch(() => null),
        getWeeklySummary().catch(() => null),
      ])
      setHeatmap(h); setTrends(t); setGrades(g); setFocus(f); setSummary(s)
    } catch (e) { showToast('Failed to load analytics', 'error') }
    setLoading(false)
  }

  const levelColors = ['#1a1a2e', '#1e3a5f', '#2563eb', '#3b82f6', '#60a5fa']

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Analytics Dashboard</h1>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#666]">Loading analytics...</div>
      ) : (
        <div className="space-y-4">
          {/* Stats Row */}
          <div className="grid grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xl font-bold text-[#7c6af7]">{summary?.total_questions || 0}</div>
              <div className="text-xs text-[#666]">Questions Answered</div>
            </div>
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xl font-bold text-[#10b981]">{summary?.overall_accuracy || 0}%</div>
              <div className="text-xs text-[#666]">Accuracy</div>
            </div>
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xl font-bold text-[#06b6d4]">{heatmap?.current_streak || 0}</div>
              <div className="text-xs text-[#666]">Day Streak</div>
            </div>
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xl font-bold text-[#f59e0b]">{focus?.focus_score || 0}</div>
              <div className="text-xs text-[#666]">Focus Score</div>
            </div>
          </div>

          {/* Heatmap */}
          {heatmap && (
            <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <h3 className="text-sm font-semibold text-[#aaa] mb-3">Study Activity Heatmap</h3>
              <div className="flex gap-0.5 flex-wrap">
                {heatmap.heatmap.map((day, i) => (
                  <div
                    key={i}
                    title={`${day.date}: ${day.count} interactions`}
                    className="w-3 h-3 rounded-sm cursor-pointer hover:ring-1 hover:ring-[#7c6af7]"
                    style={{ background: levelColors[day.level] }}
                  />
                ))}
              </div>
              <div className="flex items-center gap-2 mt-2 text-[10px] text-[#666]">
                <span>Less</span>
                {levelColors.map((c, i) => <div key={i} className="w-3 h-3 rounded-sm" style={{ background: c }} />)}
                <span>More</span>
              </div>
            </div>
          )}

          {/* Focus Score */}
          {focus && (
            <div className="grid grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
                <h4 className="text-xs text-[#888] mb-2">Subject Variety</h4>
                <div className="w-full h-2 rounded-full bg-[#252540]">
                  <div className="h-full rounded-full bg-[#7c6af7]" style={{ width: `${focus.variety_score}%` }} />
                </div>
                <div className="text-xs text-[#666] mt-1">{focus.subjects_practiced?.length || 0} subjects</div>
              </div>
              <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
                <h4 className="text-xs text-[#888] mb-2">Consistency</h4>
                <div className="w-full h-2 rounded-full bg-[#252540]">
                  <div className="h-full rounded-full bg-[#06b6d4]" style={{ width: `${focus.consistency_score}%` }} />
                </div>
                <div className="text-xs text-[#666] mt-1">{focus.days_active_this_week}/7 days</div>
              </div>
              <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
                <h4 className="text-xs text-[#888] mb-2">Volume</h4>
                <div className="w-full h-2 rounded-full bg-[#252540]">
                  <div className="h-full rounded-full bg-[#10b981]" style={{ width: `${focus.volume_score}%` }} />
                </div>
                <div className="text-xs text-[#666] mt-1">{focus.total_interactions_week} interactions</div>
              </div>
            </div>
          )}

          {/* Predicted Grades */}
          {grades && Object.keys(grades).length > 0 && (
            <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <h3 className="text-sm font-semibold text-[#aaa] mb-3">Predicted Grades (NSW Band System)</h3>
              <div className="space-y-2">
                {Object.entries(grades).map(([subj, data]) => (
                  <div key={subj} className="flex items-center gap-3">
                    <span className="text-sm text-[#e8e8e8] w-24 capitalize">{subj}</span>
                    <div className="flex-1 h-2 rounded-full bg-[#252540]">
                      <div className="h-full rounded-full bg-[#7c6af7]" style={{ width: `${data.accuracy}%` }} />
                    </div>
                    <span className="text-xs text-[#06b6d4] w-20">{data.predicted_band}</span>
                    <span className="text-[10px] text-[#666] w-12">{data.confidence}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Subject Breakdown */}
          {summary?.subjects?.length > 0 && (
            <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <h3 className="text-sm font-semibold text-[#aaa] mb-3">Subject Breakdown</h3>
              <div className="space-y-2">
                {summary.subjects.map((s, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <span className="capitalize text-[#e8e8e8] w-20">{s.subject}</span>
                    <span className="text-[#666] w-20">{s.questions}q</span>
                    <div className="flex-1 h-1.5 rounded-full bg-[#252540]">
                      <div className="h-full rounded-full bg-[#10b981]" style={{ width: `${s.accuracy}%` }} />
                    </div>
                    <span className="text-[#aaa] w-10">{s.accuracy}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
