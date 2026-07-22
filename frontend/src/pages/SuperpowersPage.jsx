import { useState } from 'react'
import {
  optimisePrompt, selfCritique, confidenceScore,
  hallucinationCheck, reflectOnAnswer, multiAgentDebate,
  suggestNextTopic, getRevisionNeeds, getWeakTopics, getLearnedFormulas
} from '../services/api'
import { showToast } from '../components/Toast'

const TABS = [
  { id: 'superpowers', label: 'AI Superpowers', icon: '🚀' },
  { id: 'study-intel', label: 'Study Intelligence', icon: '📚' },
]

export default function SuperpowersPage() {
  const [tab, setTab] = useState('superpowers')
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex border-b border-[#2a2a40] px-4">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              tab === t.id
                ? 'border-[#7c6af7] text-[#7c6af7]'
                : 'border-transparent text-[#888] hover:text-[#ccc]'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'superpowers' ? <SuperpowersTab /> : <StudyIntelTab />}
      </div>
    </div>
  )
}

function SuperpowersTab() {
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState('')
  const [question, setQuestion] = useState('')
  const [context, setContext] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const tools = [
    {
      id: 'optimise',
      label: 'Prompt Optimiser',
      icon: '✨',
      desc: 'Rewrite vague prompts into clear, effective ones',
      inputs: [
        { key: 'prompt', label: 'Your prompt', placeholder: 'Enter a prompt to optimise...', type: 'textarea' },
      ],
      fn: () => optimisePrompt(prompt),
    },
    {
      id: 'critique',
      label: 'Self-Critique',
      icon: '🔍',
      desc: 'Review AI answers for accuracy and completeness',
      inputs: [
        { key: 'question', label: 'Question asked', placeholder: 'What was the question?' },
        { key: 'response', label: 'AI response', placeholder: 'Paste the AI response...', type: 'textarea' },
      ],
      fn: () => selfCritique(response, question),
    },
    {
      id: 'confidence',
      label: 'Confidence Score',
      icon: '📊',
      desc: 'Rate how certain the AI is about its answer',
      inputs: [
        { key: 'question', label: 'Question asked', placeholder: 'What was the question?' },
        { key: 'response', label: 'AI response', placeholder: 'Paste the AI response...', type: 'textarea' },
      ],
      fn: () => confidenceScore(response, question),
    },
    {
      id: 'hallucination',
      label: 'Hallucination Detector',
      icon: '🚩',
      desc: 'Flag claims that need verification',
      inputs: [
        { key: 'context', label: 'Context / source material', placeholder: 'Known facts or source text...', type: 'textarea' },
        { key: 'response', label: 'AI response to check', placeholder: 'Paste the AI response...', type: 'textarea' },
      ],
      fn: () => hallucinationCheck(response, context),
    },
    {
      id: 'reflect',
      label: 'Reflection Mode',
      icon: '🪞',
      desc: 'Review and improve the AI answer',
      inputs: [
        { key: 'question', label: 'Question asked', placeholder: 'What was the question?' },
        { key: 'response', label: 'AI response', placeholder: 'Paste the AI response...', type: 'textarea' },
      ],
      fn: () => reflectOnAnswer(response, question),
    },
    {
      id: 'debate',
      label: 'Multi-Agent Debate',
      icon: '🤖',
      desc: 'Multiple models answer and compare',
      inputs: [
        { key: 'prompt', label: 'Question', placeholder: 'What should the models debate?' },
      ],
      fn: () => multiAgentDebate(prompt),
    },
  ]

  const [activeTool, setActiveTool] = useState(null)

  const runTool = async (tool) => {
    setActiveTool(tool.id)
    setResult(null)
    setLoading(true)
    try {
      const data = await tool.fn()
      setResult(data)
    } catch (e) {
      showToast(`Failed: ${e.message}`, 'error')
    }
    setLoading(false)
  }

  const getInputs = () => {
    if (!activeTool) return null
    const tool = tools.find(t => t.id === activeTool)
    if (!tool) return null
    return (
      <div className="space-y-3 mb-4">
        {tool.inputs.map(input => (
          <div key={input.key}>
            <label className="block text-xs text-[#888] mb-1">{input.label}</label>
            {input.type === 'textarea' ? (
              <textarea
                value={input.key === 'prompt' ? prompt : input.key === 'response' ? response : input.key === 'context' ? context : question}
                onChange={(e) => {
                  if (input.key === 'prompt') setPrompt(e.target.value)
                  else if (input.key === 'response') setResponse(e.target.value)
                  else if (input.key === 'context') setContext(e.target.value)
                  else setQuestion(e.target.value)
                }}
                placeholder={input.placeholder}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7] h-24 resize-none"
              />
            ) : (
              <input
                type="text"
                value={input.key === 'prompt' ? prompt : input.key === 'response' ? response : input.key === 'context' ? context : question}
                onChange={(e) => {
                  if (input.key === 'prompt') setPrompt(e.target.value)
                  else if (input.key === 'response') setResponse(e.target.value)
                  else if (input.key === 'context') setContext(e.target.value)
                  else setQuestion(e.target.value)
                }}
                placeholder={input.placeholder}
                className="w-full px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a40] text-[#e8e8e8] placeholder-[#555] focus:outline-none focus:border-[#7c6af7]"
              />
            )}
          </div>
        ))}
        <button
          onClick={() => runTool(tool)}
          disabled={loading}
          className="px-4 py-2 text-sm rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors disabled:opacity-50"
        >
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        {tools.map(tool => (
          <button
            key={tool.id}
            onClick={() => { setActiveTool(activeTool === tool.id ? null : tool.id); setResult(null) }}
            className={`p-3 rounded-xl border text-left transition-all ${
              activeTool === tool.id
                ? 'bg-[#7c6af7]/10 border-[#7c6af7]'
                : 'bg-[#1a1a2e] border-[#2a2a40] hover:border-[#7c6af7]/50'
            }`}
          >
            <div className="text-lg mb-1">{tool.icon}</div>
            <div className="text-xs font-semibold text-[#e8e8e8]">{tool.label}</div>
            <div className="text-[10px] text-[#666] mt-0.5">{tool.desc}</div>
          </button>
        ))}
      </div>

      {getInputs()}

      {result && (
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-xs text-[#888] mb-2">Result</div>
          <pre className="text-sm text-[#ccc] whitespace-pre-wrap font-mono">
            {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

function StudyIntelTab() {
  const [weakTopics, setWeakTopics] = useState([])
  const [nextTopic, setNextTopic] = useState(null)
  const [revisionNeeds, setRevisionNeeds] = useState([])
  const [formulas, setFormulas] = useState([])
  const [loading, setLoading] = useState(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [weak, next, rev, form] = await Promise.all([
        getWeakTopics().catch(() => []),
        suggestNextTopic().catch(() => null),
        getRevisionNeeds().catch(() => []),
        getLearnedFormulas().catch(() => []),
      ])
      setWeakTopics(weak)
      setNextTopic(next)
      setRevisionNeeds(rev)
      setFormulas(form)
    } catch (e) {
      showToast('Failed to load study intelligence', 'error')
    }
    setLoading(false)
  }

  return (
    <div className="space-y-4">
      <button
        onClick={loadAll}
        disabled={loading}
        className="px-4 py-2 text-sm rounded-lg bg-[#7c6af7] text-white hover:bg-[#6a59e0] transition-colors disabled:opacity-50"
      >
        {loading ? 'Loading...' : 'Load Study Intelligence'}
      </button>

      {nextTopic && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-[#7c6af7]/10 to-[#06b6d4]/10 border border-[#7c6af7]/30">
          <div className="text-xs text-[#888] mb-1">Suggested Next</div>
          <div className="text-lg font-bold text-[#e8e8e8]">{nextTopic.suggestion}</div>
          <div className="text-sm text-[#888] mt-1">{nextTopic.reason}</div>
        </div>
      )}

      {weakTopics.length > 0 && (
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-sm font-semibold text-red-400 mb-2">Weak Topics</div>
          <div className="space-y-2">
            {weakTopics.map((t, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="text-[#e8e8e8]">{t.topic}</span>
                <span className="text-red-400">{(t.accuracy * 100).toFixed(0)}%</span>
                <span className="text-[#666]">{t.attempts} attempts</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {revisionNeeds.length > 0 && (
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-sm font-semibold text-[#f59e0b] mb-2">Needs Revision</div>
          <div className="space-y-2">
            {revisionNeeds.map((r, i) => (
              <div key={i} className="text-sm text-[#ccc]">{r.suggestion}</div>
            ))}
          </div>
        </div>
      )}

      {formulas.length > 0 && (
        <div className="p-4 rounded-xl bg-[#1a1a2e] border border-[#2a2a40]">
          <div className="text-sm font-semibold text-[#06b6d4] mb-2">Learned Formulas</div>
          <div className="space-y-2">
            {formulas.map((f, i) => (
              <div key={i} className="p-2 rounded-lg bg-[#252540] text-sm font-mono text-[#e8e8e8]">
                {f.formula}
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && weakTopics.length === 0 && !nextTopic && revisionNeeds.length === 0 && formulas.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-[#666] gap-2">
          <p className="text-3xl">📚</p>
          <p>No study data yet</p>
          <p className="text-xs text-[#555]">Take quizzes and study to build your intelligence profile</p>
        </div>
      )}
    </div>
  )
}
