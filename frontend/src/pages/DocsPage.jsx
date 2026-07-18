import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Upload, MessageSquare, X, Loader, BookOpen,
  Quote, List, Search, ChevronDown, ChevronUp, FileSearch,
  Presentation, Table2, Code, Hash, ArrowRight, MessagesSquare
} from 'lucide-react'
import { useStore } from '../store'
import { getConversations } from '../services/api'

const BASE = '/api'

// ── File type detection ─────────────────────────────────────────────────────
function getFileCategory(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  if (['pdf', 'docx', 'doc', 'txt', 'md'].includes(ext)) return 'text'
  if (['pptx', 'ppt'].includes(ext)) return 'presentation'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'data'
  if (['py', 'js', 'jsx', 'ts', 'tsx', 'json', 'html', 'xml', 'css', 'java', 'cpp', 'c', 'h'].includes(ext)) return 'code'
  if (['zip'].includes(ext)) return 'archive'
  return 'text'
}

function getFileIcon(filename) {
  const cat = getFileCategory(filename)
  switch (cat) {
    case 'presentation': return <Presentation size={20} className="text-[#7c6af7]" />
    case 'data': return <Table2 size={20} className="text-[#7c6af7]" />
    case 'code': return <Code size={20} className="text-[#7c6af7]" />
    default: return <FileText size={20} className="text-[#7c6af7]" />
  }
}

// ── Adaptive content by file type ───────────────────────────────────────────
const ADAPTIVE = {
  text: {
    tabs: [
      { id: 'chat',      icon: <MessageSquare size={14}/>, label: 'Ask Anything' },
      { id: 'summarise', icon: <BookOpen size={14}/>,      label: 'Summarise' },
      { id: 'quotes',    icon: <Quote size={14}/>,         label: 'Find Quotes' },
      { id: 'keypoints', icon: <List size={14}/>,          label: 'Key Points' },
    ],
    quickQuestions: [
      'What are the main themes?',
      'Summarise this document',
      'What is the author\'s main argument?',
      'What are the key facts or findings?',
    ],
    quoteThemes: [
      'diversity and acceptance',
      'courage and fear',
      'identity and belonging',
      'justice and inequality',
      'friendship and loyalty',
      'family and love',
    ],
    placeholder: 'e.g. What are the main themes?\nWhat quotes could I use for an essay on diversity?\nWhat happens in chapter 3?',
  },
  presentation: {
    tabs: [
      { id: 'chat',      icon: <MessageSquare size={14}/>, label: 'Ask Anything' },
      { id: 'summarise', icon: <BookOpen size={14}/>,      label: 'Overview' },
      { id: 'keypoints', icon: <List size={14}/>,          label: 'Key Points' },
    ],
    quickQuestions: [
      'What is this presentation about?',
      'Summarise all the slides',
      'What are the main topics covered?',
      'List the key data or statistics',
    ],
    quoteThemes: [],
    placeholder: 'e.g. What is this presentation about?\nSummarise slide 5\nWhat data is shown on slide 3?',
  },
  data: {
    tabs: [
      { id: 'chat',      icon: <MessageSquare size={14}/>, label: 'Ask Anything' },
      { id: 'summarise', icon: <BookOpen size={14}/>,      label: 'Data Summary' },
      { id: 'keypoints', icon: <List size={14}/>,          label: 'Key Patterns' },
    ],
    quickQuestions: [
      'What does this data show?',
      'Summarise the trends',
      'What are the column headers?',
      'Are there any outliers or anomalies?',
    ],
    quoteThemes: [],
    placeholder: 'e.g. What does this data show?\nWhat are the average values?\nWhich category has the highest count?',
  },
  code: {
    tabs: [
      { id: 'chat',      icon: <MessageSquare size={14}/>, label: 'Ask Anything' },
      { id: 'summarise', icon: <BookOpen size={14}/>,      label: 'Code Overview' },
      { id: 'keypoints', icon: <List size={14}/>,          label: 'Key Functions' },
    ],
    quickQuestions: [
      'What does this code do?',
      'What are the main functions?',
      'Are there any bugs or issues?',
      'How is the code structured?',
    ],
    quoteThemes: [],
    placeholder: 'e.g. What does this code do?\nExplain the main function\nAre there any security issues?',
  },
  archive: {
    tabs: [
      { id: 'chat', icon: <MessageSquare size={14}/>, label: 'Ask Anything' },
    ],
    quickQuestions: [
      'What files are in this archive?',
      'Summarise the contents',
    ],
    quoteThemes: [],
    placeholder: 'e.g. What files are in this archive?\nSummarise the main document',
  },
}

export default function DocsPage() {
  const navigate = useNavigate()
  const { conversations, setConversationId } = useStore()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef()
  const fileDataRef = useRef(null)
  const fileCategory = doc ? getFileCategory(doc.name) : null
  const adaptive = fileCategory ? ADAPTIVE[fileCategory] || ADAPTIVE.text : ADAPTIVE.text

  // Per-feature state
  const [activeTab, setActiveTab] = useState('chat')
  const [summaryStyle, setSummaryStyle] = useState('structured')
  const [summaryFocus, setSummaryFocus] = useState('')
  const [summaryText, setSummaryText] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  const [quoteTheme, setQuoteTheme] = useState('')
  const [quotes, setQuotes] = useState([])
  const [quotesLoading, setQuotesLoading] = useState(false)

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [answerLoading, setAnswerLoading] = useState(false)

  const [keyPoints, setKeyPoints] = useState('')
  const [keyPointsLoading, setKeyPointsLoading] = useState(false)

  // Conversation picker state
  const [showChatPicker, setShowChatPicker] = useState(false)
  const [chatPickerSearch, setChatPickerSearch] = useState('')

  // Reset tab when file changes
  useEffect(() => {
    setActiveTab('chat')
  }, [doc?.name])

  // ── File upload ───────────────────────────────────────────────────────────
  const handleFile = async (file) => {
    if (!file) return
    const allowed = ['.pdf','.docx','.doc','.pptx','.ppt','.xlsx','.csv','.txt','.md','.zip',
                     '.py','.js','.jsx','.ts','.tsx','.json','.html','.xml','.css','.java','.cpp','.c','.h']
    if (!allowed.some(e => file.name.toLowerCase().endsWith(e))) {
      alert('Supported: PDF, Word, PowerPoint, Excel, TXT, Code files, ZIP')
      return
    }
    setLoading(true)
    setDoc(null)
    setSummaryText('')
    setQuotes([])
    setAnswer('')
    setKeyPoints('')
    fileDataRef.current = file

    const form = new FormData()
    form.append('file', file)
    try {
      const resp = await fetch(`${BASE}/docs/upload`, { method: 'POST', body: form })
      const data = await resp.json()
      setDoc({ name: data.filename, pages: data.pages, words: data.words,
               chars: data.characters, preview: data.preview })
    } catch (e) {
      alert('Could not read file: ' + e.message)
    }
    setLoading(false)
  }

  // ── Summarise ─────────────────────────────────────────────────────────────
  const handleSummarise = async () => {
    if (!fileDataRef.current) return
    setSummaryLoading(true)
    setSummaryText('')
    const form = new FormData()
    form.append('file', fileDataRef.current)
    form.append('style', summaryStyle)
    if (summaryFocus) form.append('focus', summaryFocus)

    try {
      const resp = await fetch(`${BASE}/docs/summarise`, { method: 'POST', body: form })
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6)
            if (chunk === '[DONE]') break
            setSummaryText(t => t + chunk)
          }
        }
      }
    } catch (e) {
      setSummaryText('Error: ' + e.message)
    }
    setSummaryLoading(false)
  }

  // ── Quote extraction ──────────────────────────────────────────────────────
  const handleExtractQuotes = async () => {
    if (!fileDataRef.current || !quoteTheme.trim()) return
    setQuotesLoading(true)
    setQuotes([])
    const form = new FormData()
    form.append('file', fileDataRef.current)
    form.append('theme', quoteTheme)
    form.append('min_relevance', '0.15')
    try {
      const resp = await fetch(`${BASE}/docs/quotes`, { method: 'POST', body: form })
      const data = await resp.json()
      setQuotes(data.quotes || [])
    } catch (e) {
      setQuotes([])
    }
    setQuotesLoading(false)
  }

  // ── Ask question ──────────────────────────────────────────────────────────
  const handleAsk = async () => {
    if (!fileDataRef.current || !question.trim()) return
    setAnswerLoading(true)
    setAnswer('')
    const form = new FormData()
    form.append('file', fileDataRef.current)
    form.append('question', question)
    try {
      const resp = await fetch(`${BASE}/docs/ask`, { method: 'POST', body: form })
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6)
            if (chunk === '[DONE]') break
            setAnswer(t => t + chunk)
          }
        }
      }
    } catch (e) {
      setAnswer('Error: ' + e.message)
    }
    setAnswerLoading(false)
  }

  // ── Key points ────────────────────────────────────────────────────────────
  const handleKeyPoints = async () => {
    if (!fileDataRef.current) return
    setKeyPointsLoading(true)
    setKeyPoints('')
    const form = new FormData()
    form.append('file', fileDataRef.current)
    try {
      const resp = await fetch(`${BASE}/docs/key-points`, { method: 'POST', body: form })
      const data = await resp.json()
      setKeyPoints(data.key_points || '')
    } catch (e) {
      setKeyPoints('Error: ' + e.message)
    }
    setKeyPointsLoading(false)
  }

  // ── Send to chat (with conversation picker) ───────────────────────────────
  const openInChat = async (convId = null, prefill = '') => {
    if (fileDataRef.current) {
      let fileText = ''
      try {
        const form = new FormData()
        form.append('file', fileDataRef.current)
        const resp = await fetch(`${BASE}/docs/upload`, { method: 'POST', body: form })
        const data = await resp.json()
        fileText = data.preview || ''
      } catch {}
      sessionStorage.setItem('aria_pending_doc', JSON.stringify({
        name: doc?.name,
        text: fileText.slice(0, 3000),
        prefill,
        hasFile: true,
      }))
    }
    if (convId) {
      setConversationId(convId)
      navigate(`/chat/${convId}`)
    } else {
      navigate('/chat')
    }
    setShowChatPicker(false)
  }

  const filteredConversations = conversations.filter(c =>
    c.title.toLowerCase().includes(chatPickerSearch.toLowerCase())
  )

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <div className="flex items-center gap-2 mb-2">
        <FileSearch size={20} className="text-[#7c6af7]" />
        <h1 className="text-lg font-semibold text-[#e8e8e8]">Document Reader</h1>
      </div>
      <p className="text-xs text-[#444] mb-6">
        {fileCategory
          ? `${doc.name.split('.').pop().toUpperCase()} file · ${doc.pages} page${doc.pages !== 1 ? 's' : ''}`
          : 'PDF · Word · PowerPoint · Excel · Code · TXT'
        }
      </p>

      {/* Upload zone */}
      {!doc && !loading && (
        <div
          onClick={() => fileRef.current.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }}
          className={`border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-[#7c6af7] bg-[#7c6af7]/5 scale-[1.01]'
              : 'border-[#2a2a2a] hover:border-[#7c6af7]/50 hover:bg-[#141414]'
          }`}
        >
          <Upload size={36} className="text-[#333] mx-auto mb-4" />
          <p className="text-[#888] text-sm mb-1 font-medium">Drop your document here</p>
          <p className="text-xs text-[#444]">or click to browse</p>
          <p className="text-xs text-[#333] mt-3">PDF · Word · PowerPoint · Excel · Code · TXT · ZIP</p>
          <input ref={fileRef} type="file"
            accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.csv,.txt,.md,.zip,.py,.js,.jsx,.ts,.tsx,.json,.html,.xml,.css,.java,.cpp,.c,.h"
            className="hidden" onChange={e => handleFile(e.target.files[0])} />
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center py-16 gap-3">
          <Loader size={28} className="text-[#7c6af7] animate-spin" />
          <p className="text-[#888] text-sm">Reading document...</p>
        </div>
      )}

      {/* Document loaded */}
      {doc && (
        <div className="space-y-4">
          {/* File header */}
          <div className="flex items-center gap-3 bg-[#141414] border border-[#2a2a2a] rounded-2xl p-4">
            <div className="w-10 h-10 rounded-xl bg-[#7c6af7]/10 flex items-center justify-center flex-shrink-0">
              {getFileIcon(doc.name)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[#e8e8e8] text-sm font-medium truncate">{doc.name}</p>
              <p className="text-xs text-[#444] mt-0.5">
                {doc.pages} page{doc.pages !== 1 ? 's' : ''} ·{' '}
                {(doc.words || 0).toLocaleString()} words ·{' '}
                {((doc.chars || 0) / 1000).toFixed(1)}k characters
              </p>
            </div>
            <button onClick={() => { setDoc(null); fileDataRef.current = null }}
              className="text-[#444] hover:text-[#f87171] p-1 transition-colors">
              <X size={16} />
            </button>
          </div>

          {/* Preview */}
          {doc.preview && (
            <DocPreview preview={doc.preview} />
          )}

          {/* Tabs — adaptive to file type */}
          <div className="flex gap-1 bg-[#111] border border-[#1e1e1e] p-1 rounded-xl overflow-x-auto">
            {adaptive.tabs.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs whitespace-nowrap transition-colors flex-shrink-0 ${
                  activeTab === tab.id
                    ? 'bg-[#7c6af7] text-white'
                    : 'text-[#666] hover:text-[#aaa]'
                }`}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {/* Tab: Ask Anything */}
          {activeTab === 'chat' && (
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
              <p className="text-xs text-[#555]">
                Ask any question about <span className="text-[#aaa]">{doc.name}</span>.
                ARIA reads the whole document and finds the relevant pages for you.
              </p>
              <div className="flex flex-col gap-2">
                <textarea
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }}}
                  placeholder={adaptive.placeholder}
                  rows={3}
                  className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-3 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50 resize-none"
                />
                <div className="flex gap-2">
                  <button onClick={handleAsk} disabled={!question.trim() || answerLoading}
                    className="flex-1 py-2.5 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
                    {answerLoading ? 'Searching document...' : 'Ask Question'}
                  </button>
                  <button onClick={() => setShowChatPicker(true)}
                    className="px-4 py-2.5 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#777] hover:text-[#e8e8e8] transition-colors whitespace-nowrap flex items-center gap-1.5">
                    <MessagesSquare size={12} /> Continue in Chat
                  </button>
                </div>
              </div>
              {answerLoading && !answer && (
                <div className="flex items-center gap-2 text-xs text-[#555] py-2">
                  <Loader size={13} className="animate-spin text-[#7c6af7]" /> Searching document...
                </div>
              )}
              {answer && (
                <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap">
                  {answer}
                </div>
              )}

              {/* Quick questions — adaptive to file type */}
              <div>
                <p className="text-xs text-[#444] mb-2">Quick questions:</p>
                <div className="flex flex-wrap gap-2">
                  {adaptive.quickQuestions.map(q => (
                    <button key={q} onClick={() => { setQuestion(q); setTimeout(() => handleAsk(), 50) }}
                      className="text-xs px-3 py-1.5 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#666] hover:text-[#aaa] hover:border-[#7c6af7]/30 transition-colors">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Tab: Summarise */}
          {activeTab === 'summarise' && (
            <div className="space-y-4">
              <div>
                <label className="text-xs text-[#666] mb-2 block">Summary style</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    ['structured', '📋 Structured'],
                    ['brief',      '⚡ Brief'],
                    ['detailed',   '📖 Detailed'],
                    ['key_points', '🎯 Key Points'],
                  ].map(([val, label]) => (
                    <button key={val} onClick={() => setSummaryStyle(val)}
                      className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                        summaryStyle === val
                          ? 'bg-[#7c6af7] text-white'
                          : 'bg-[#1a1a1a] border border-[#2a2a2a] text-[#777] hover:text-[#aaa]'
                      }`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-[#666] mb-2 block">
                  Focus on (optional) — e.g. "themes", "data trends", "key functions"
                </label>
                <input
                  value={summaryFocus}
                  onChange={e => setSummaryFocus(e.target.value)}
                  placeholder="Leave blank for a general summary"
                  className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50"
                />
              </div>
              <button onClick={handleSummarise} disabled={summaryLoading}
                className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-50 transition-colors">
                {summaryLoading
                  ? `Summarising ${doc.pages > 10 ? `${doc.pages}-page document...` : '...'}`
                  : `Summarise ${doc.name}`}
              </button>
              {doc.pages > 10 && (
                <p className="text-xs text-[#444] text-center">
                  Large document ({doc.pages} pages) — will summarise section by section, then combine
                </p>
              )}
              {summaryText && (
                <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                  {summaryText}
                </div>
              )}
            </div>
          )}

          {/* Tab: Find Quotes (only for text/PDF documents) */}
          {activeTab === 'quotes' && (
            <div className="space-y-4">
              <div>
                <p className="text-xs text-[#555] mb-3">
                  Enter a theme, topic, or essay question. ARIA will find the most relevant
                  quotes and passages from <span className="text-[#aaa]">{doc.name}</span> with page numbers.
                </p>
                <label className="text-xs text-[#666] mb-2 block">Theme or topic</label>
                <input
                  value={quoteTheme}
                  onChange={e => setQuoteTheme(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleExtractQuotes()}
                  placeholder="e.g. diversity and acceptance, courage, friendship, justice..."
                  className="w-full bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50"
                />
              </div>

              {/* Quote theme suggestions — adaptive */}
              {adaptive.quoteThemes.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {adaptive.quoteThemes.map(theme => (
                    <button key={theme} onClick={() => setQuoteTheme(theme)}
                      className="text-xs px-3 py-1 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#666] hover:text-[#aaa] hover:border-[#7c6af7]/30 transition-colors">
                      {theme}
                    </button>
                  ))}
                </div>
              )}

              <button onClick={handleExtractQuotes} disabled={!quoteTheme.trim() || quotesLoading}
                className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-40 transition-colors">
                {quotesLoading ? 'Scanning document...' : 'Find Quotes & Passages'}
              </button>

              {quotesLoading && (
                <div className="flex items-center gap-2 text-xs text-[#555] py-2">
                  <Loader size={13} className="animate-spin text-[#7c6af7]" />
                  Scanning {doc.pages} pages for relevant quotes...
                </div>
              )}

              {quotes.length > 0 && (
                <div className="space-y-3 overflow-y-auto pr-2" style={{maxHeight: '65vh'}}>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-[#666]">
                      Found <span className="text-[#a89bf8] font-medium">{quotes.length}</span> relevant passages
                      for <span className="text-[#a89bf8]">"{quoteTheme}"</span>
                    </p>
                    <button
                      onClick={() => {
                        const text = quotes.map(q =>
                          `"${q.quote}" (p. ${q.page})`
                        ).join('\n\n')
                        navigator.clipboard.writeText(text)
                      }}
                      className="text-xs text-[#555] hover:text-[#aaa] px-2 py-1 rounded bg-[#1a1a1a] border border-[#2a2a2a]"
                    >
                      Copy all
                    </button>
                  </div>
                  {quotes.map((q, i) => (
                    <QuoteCard key={i} quote={q} index={i + 1} />
                  ))}
                </div>
              )}

              {quotes.length === 0 && !quotesLoading && quoteTheme && (
                <p className="text-xs text-[#444] text-center py-4">
                  No quotes found yet. Click "Find Quotes" to search.
                </p>
              )}
            </div>
          )}

          {/* Tab: Key Points */}
          {activeTab === 'keypoints' && (
            <div className="space-y-4">
              <p className="text-xs text-[#555]">
                {fileCategory === 'code'
                  ? `Extract the key functions, classes, and structure from ${doc.name}.`
                  : fileCategory === 'data'
                  ? `Extract the key patterns, trends, and insights from ${doc.name}.`
                  : fileCategory === 'presentation'
                  ? `Extract the main topics and key information from each slide.`
                  : `Extract the 10 most important facts, arguments, or ideas from ${doc.name}.`
                }
              </p>
              <button onClick={handleKeyPoints} disabled={keyPointsLoading}
                className="w-full py-3 rounded-xl bg-[#7c6af7] hover:bg-[#6a59e0] text-white text-sm font-medium disabled:opacity-50 transition-colors">
                {keyPointsLoading ? 'Extracting...' : 'Extract Key Points'}
              </button>
              {keyPointsLoading && (
                <div className="flex items-center gap-2 text-xs text-[#555] py-2">
                  <Loader size={13} className="animate-spin text-[#7c6af7]" /> Reading document...
                </div>
              )}
              {keyPoints && (
                <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap">
                  {keyPoints}
                </div>
              )}
            </div>
          )}

          {/* Upload another */}
          <button onClick={() => { setDoc(null); fileDataRef.current = null; setSummaryText(''); setQuotes([]); setAnswer(''); setKeyPoints('') }}
            className="w-full text-xs text-[#333] hover:text-[#666] py-2 transition-colors">
            ↑ Upload a different document
          </button>
        </div>
      )}

      {/* ── Conversation Picker Modal ──────────────────────────────────────── */}
      {showChatPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setShowChatPicker(false)}>
          <div className="bg-[#141414] border border-[#2a2a2a] rounded-2xl w-full max-w-md mx-4 shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e1e1e]">
              <div className="flex items-center gap-2">
                <MessagesSquare size={16} className="text-[#7c6af7]" />
                <h2 className="text-sm font-semibold text-[#e8e8e8]">Continue in Chat</h2>
              </div>
              <button onClick={() => setShowChatPicker(false)}
                className="text-[#555] hover:text-[#aaa] transition-colors">
                <X size={16} />
              </button>
            </div>

            <div className="p-4">
              <input
                value={chatPickerSearch}
                onChange={e => setChatPickerSearch(e.target.value)}
                placeholder="Search conversations..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#333] outline-none focus:border-[#7c6af7]/50 mb-3"
                autoFocus
              />

              <div className="max-h-64 overflow-y-auto space-y-1">
                {/* New conversation option */}
                <button
                  onClick={() => openInChat(null, question)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left hover:bg-[#1e1e1e] transition-colors group"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#7c6af7]/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-[#7c6af7] text-lg">+</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[#e8e8e8] font-medium">New conversation</p>
                    <p className="text-xs text-[#444]">Start a fresh chat with this document</p>
                  </div>
                  <ArrowRight size={14} className="text-[#444] group-hover:text-[#7c6af7] transition-colors" />
                </button>

                {filteredConversations.length > 0 && (
                  <div className="pt-2 pb-1 px-1">
                    <p className="text-[10px] text-[#444] uppercase tracking-wider">Existing conversations</p>
                  </div>
                )}

                {filteredConversations.slice(0, 20).map(conv => (
                  <button
                    key={conv.id}
                    onClick={() => openInChat(conv.id, question)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left hover:bg-[#1e1e1e] transition-colors group"
                  >
                    <div className="w-8 h-8 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] flex items-center justify-center flex-shrink-0">
                      <MessageSquare size={13} className="text-[#555]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#ccc] truncate group-hover:text-[#e8e8e8]">{conv.title}</p>
                      <p className="text-xs text-[#444]">{conv.turn_count || 0} messages</p>
                    </div>
                    <ArrowRight size={14} className="text-[#333] group-hover:text-[#7c6af7] transition-colors flex-shrink-0" />
                  </button>
                ))}

                {filteredConversations.length === 0 && chatPickerSearch && (
                  <p className="text-xs text-[#444] text-center py-4">No conversations found</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────────────────

function DocPreview({ preview }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bg-[#0d0d0d] border border-[#1e1e1e] rounded-xl overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-[#555] hover:text-[#888] transition-colors">
        <FileText size={12} />
        <span>Preview first 600 characters</span>
        <span className="ml-auto">{open ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-[#1e1e1e]">
          <p className="text-xs text-[#666] leading-relaxed font-mono whitespace-pre-wrap mt-3">{preview}</p>
        </div>
      )}
    </div>
  )
}

function QuoteCard({ quote, index }) {
  const [copied, setCopied] = useState(false)
  const relevancePct = Math.round(quote.relevance * 100)
  const relevanceColor = relevancePct >= 70 ? 'text-green-400' : relevancePct >= 40 ? 'text-yellow-400' : 'text-[#666]'

  const copy = () => {
    navigator.clipboard.writeText(`"${quote.quote}" (p. ${quote.page})`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="bg-[#141414] border border-[#2a2a2a] rounded-xl p-4 group hover:border-[#7c6af7]/30 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <span className="text-xs text-[#444] flex-shrink-0">#{index}</span>
        <div className="flex items-center gap-3 ml-auto flex-shrink-0">
          <span className={`text-xs ${relevanceColor}`}>{relevancePct}% match</span>
          <span className="text-xs text-[#444] bg-[#1e1e1e] px-2 py-0.5 rounded-full">p. {quote.page}</span>
          <button onClick={copy}
            className="text-xs text-[#444] hover:text-[#a89bf8] transition-colors opacity-0 group-hover:opacity-100">
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        </div>
      </div>
      <blockquote className="text-sm text-[#ccc] leading-relaxed border-l-2 border-[#7c6af7]/40 pl-3 italic">
        "{quote.quote}"
      </blockquote>
      <p className="text-xs text-[#444] mt-2">{quote.word_count} words</p>
    </div>
  )
}
