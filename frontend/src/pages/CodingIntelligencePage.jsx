import { useState } from 'react'
import {
  understandProject, viewArchitecture, analyseDependencies,
  findDeadCode, scanSecurity, generateChangelog, explainProjectStructure,
  analysePerformance
} from '../services/api'
import { showToast } from '../components/Toast'

const TOOLS = [
  { id: 'understand', label: 'Project Overview', icon: '📁', desc: 'What this project is and how it works' },
  { id: 'explain', label: 'Explain Structure', icon: '🧠', desc: 'AI explanation of architecture' },
  { id: 'architecture', label: 'Architecture Viewer', icon: '🕸️', desc: 'Internal dependency graph' },
  { id: 'dependencies', label: 'Dependencies', icon: '📦', desc: 'Installed packages analysis' },
  { id: 'dead-code', label: 'Dead Code', icon: '💀', desc: 'Unused imports and functions' },
  { id: 'security', label: 'Security Scanner', icon: '🔒', desc: 'Vulnerability detection' },
  { id: 'performance', label: 'Performance', icon: '⚡', desc: 'Bottleneck analysis' },
  { id: 'changelog', label: 'Auto Changelog', icon: '📝', desc: 'Generate from git history' },
]

export default function CodingIntelligencePage() {
  const [projectPath, setProjectPath] = useState('')
  const [activeTool, setActiveTool] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const runTool = async (toolId) => {
    if (!projectPath.trim()) {
      showToast('Enter a project path first', 'error')
      return
    }
    setActiveTool(toolId)
    setResult(null)
    setLoading(true)
    try {
      let data
      switch (toolId) {
        case 'understand':
          data = await understandProject(projectPath)
          break
        case 'explain':
          data = await explainProjectStructure(projectPath)
          data = { explanation: data.explanation }
          break
        case 'architecture':
          data = await viewArchitecture(projectPath)
          break
        case 'dependencies':
          data = await analyseDependencies(projectPath)
          break
        case 'dead-code':
          data = await findDeadCode(projectPath)
          break
        case 'security':
          data = await scanSecurity(projectPath)
          break
        case 'performance':
          data = await analysePerformance(projectPath)
          data = { analysis: data.analysis }
          break
        case 'changelog':
          data = await generateChangelog(projectPath)
          data = { changelog: data.changelog }
          break
      }
      setResult(data)
    } catch (e) {
      showToast(`Analysis failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  const renderResult = () => {
    if (loading) return <div className="flex items-center justify-center py-12 text-[#666]">Analysing...</div>
    if (!result) return null

    if (activeTool === 'understand' && result.stats) {
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888]">Project Type</div>
              <div className="text-lg font-bold text-[#7c6af7]">{result.type}</div>
            </div>
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888]">Total Files</div>
              <div className="text-lg font-bold text-[#06b6d4]">{result.total_files}</div>
            </div>
          </div>
          {result.entry_points?.length > 0 && (
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888] mb-1">Entry Points</div>
              <div className="flex flex-wrap gap-1">
                {result.entry_points.map((ep, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-[#7c6af7]/20 text-[#7c6af7]">{ep}</span>
                ))}
              </div>
            </div>
          )}
          {result.stats && (
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888] mb-2">File Types</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(result.stats).slice(0, 10).map(([ext, count]) => (
                  <span key={ext} className="text-xs px-2 py-1 rounded-lg bg-[#252540] text-[#ccc]">
                    {ext || '(none)'}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
          {result.file_tree && (
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xs text-[#888] mb-2">File Tree</div>
              <pre className="text-xs text-[#ccc] overflow-x-auto font-mono">
                {JSON.stringify(result.file_tree, null, 2).slice(0, 2000)}
              </pre>
            </div>
          )}
        </div>
      )
    }

    if (activeTool === 'dead-code' && result.issues) {
      return (
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
              <div className="text-xl font-bold text-red-400">{result.total_issues}</div>
              <div className="text-xs text-[#666]">Issues Found</div>
            </div>
            {result.by_type && Object.entries(result.by_type).map(([type, count]) => (
              <div key={type} className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
                <div className="text-xl font-bold text-[#f59e0b]">{count}</div>
                <div className="text-xs text-[#666]">{type.replace('_', ' ')}</div>
              </div>
            ))}
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {result.issues.slice(0, 30).map((issue, i) => (
              <div key={i} className="p-2 rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-xs flex items-start gap-2">
                <span className="text-red-400">●</span>
                <div>
                  <span className="text-[#888]">{issue.file}:{issue.line || '?'} </span>
                  <span className="text-[#e8e8e8]">{issue.type.replace('_', ' ')}: {issue.name || issue.code}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )
    }

    if (activeTool === 'security' && result.issues) {
      return (
        <div className="space-y-3">
          <div className="p-3 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
            <div className="text-xl font-bold text-[#f59e0b]">{result.total_issues}</div>
            <div className="text-xs text-[#666]">Security Issues · Severity: {result.severity}</div>
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {result.issues.slice(0, 30).map((issue, i) => (
              <div key={i} className="p-2 rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-xs flex items-start gap-2">
                <span className={issue.type === 'hardcoded_secret' || issue.type === 'eval_usage' ? 'text-red-400' : 'text-[#f59e0b]'}>●</span>
                <div>
                  <span className="text-[#888]">{issue.file} </span>
                  <span className="text-[#e8e8e8]">{issue.description}</span>
                  {issue.match && <div className="text-[#666] font-mono mt-1">{issue.match}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )
    }

    // Generic text result
    const text = result.explanation || result.analysis || result.changelog ||
      (typeof result === 'string' ? result : JSON.stringify(result, null, 2))

    return (
      <pre className="text-sm text-[#ccc] whitespace-pre-wrap font-mono bg-[#1a1a2e] p-4 rounded-xl border border-[#2a2a40] max-h-96 overflow-y-auto">
        {text}
      </pre>
    )
  }

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <h1 className="text-xl font-bold text-[#e8e8e8]">Coding Intelligence</h1>

      {/* Path input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={projectPath}
          onChange={(e) => setProjectPath(e.target.value)}
          placeholder="Enter project path (e.g. ~/my-project)"
          className="flex-1 px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
        />
      </div>

      {/* Tool grid */}
      <div className="grid grid-cols-4 gap-2">
        {TOOLS.map(tool => (
          <button
            key={tool.id}
            onClick={() => runTool(tool.id)}
            disabled={loading}
            className={`p-3 rounded-xl border text-left transition-all ${
              activeTool === tool.id
                ? 'bg-[#7c6af7]/10 border-[#7c6af7]'
                : 'bg-[#1a1a2e] border-[#2a2a40] hover:border-[#7c6af7]/50'
            } disabled:opacity-50`}
          >
            <div className="text-lg mb-1">{tool.icon}</div>
            <div className="text-xs font-semibold text-[#e8e8e8]">{tool.label}</div>
            <div className="text-[10px] text-[#666] mt-0.5">{tool.desc}</div>
          </button>
        ))}
      </div>

      {/* Result */}
      {renderResult()}
    </div>
  )
}
