import { useState, useEffect, useCallback } from 'react'
import {
  uploadToKB, uploadMultipleToKB, searchKB, listKBDocuments,
  deleteKBDocument, getKBStats, getKBCollections
} from '../services/api'
import { showToast } from '../components/Toast'
import {
  Database, Upload, Search, Trash2, FileText, RefreshCw,
  ChevronDown, ChevronUp, FolderOpen, Zap, Clock, Hash, X, MessageSquare
} from 'lucide-react'

const BASE = '/api'

const COLLECTION_LABELS = {
  education_au: { label: 'Education (AU)', emoji: '\u{1F393}', color: 'text-[#f59e0b]' },
  general:      { label: 'General', emoji: '\u{1F4DA}', color: 'text-[#7c6af7]' },
  coding:       { label: 'Coding', emoji: '\u{1F4BB}', color: 'text-[#06b6d4]' },
  research:     { label: 'Research', emoji: '\u{1F52C}', color: 'text-[#10b981]' },
  math:         { label: 'Mathematics', emoji: '\u{1F4D0}', color: 'text-[#f472b6]' },
  science:      { label: 'Science', emoji: '\u{1F52C}', color: 'text-[#22d3ee]' },
  history:      { label: 'History', emoji: '\u{1F3DB}', color: 'text-[#fb923c]' },
  geography:    { label: 'Geography', emoji: '\u{1F30D}', color: 'text-[#34d399]' },
  literature:   { label: 'Literature', emoji: '\u{1F4D6}', color: 'text-[#a78bfa]' },
  productivity: { label: 'Productivity', emoji: '\u{26A1}', color: 'text-[#fbbf24]' },
  user_docs:    { label: 'My Documents', emoji: '\u{1F4C4}', color: 'text-[#60a5fa]' },
}

export default function KnowledgeBasePage() {
  const [tab, setTab] = useState('upload')
  const [stats, setStats] = useState(null)
  const [documents, setDocuments] = useState([])
  const [collections, setCollections] = useState({})
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState(null)
  const [expandedDoc, setExpandedDoc] = useState(null)

  const [chatQuestion, setChatQuestion] = useState('')
  const [chatAnswer, setChatAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, d, c] = await Promise.all([getKBStats(), listKBDocuments(), getKBCollections()])
      setStats(s)
      setDocuments(d.documents || [])
      setCollections(c.collections || {})
    } catch {}
  }, [])

  useEffect(() => { load() }, [load])

  const handleUpload = async (files) => {
    if (!files.length) return
    setUploading(true)
    try {
      const result = await uploadMultipleToKB(files, selectedCollection)
      const ok = (result.results || []).filter(r => r.status === 'ok').length
      const dup = (result.results || []).filter(r => r.status === 'duplicate').length
      const err = (result.results || []).filter(r => r.status === 'error').length
      if (ok) showToast(`${ok} document(s) ingested!`, 'success')
      if (dup) showToast(`${dup} duplicate(s) skipped`, 'info')
      if (err) showToast(`${err} failed to process`, 'error')
      await load()
    } catch (e) { showToast('Upload failed: ' + e.message, 'error') }
    setUploading(false)
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const data = await searchKB(searchQuery, selectedCollection, 10)
      setSearchResults(data.results || [])
    } catch (e) { showToast('Search failed', 'error') }
    setSearching(false)
  }

  const handleAsk = async () => {
    if (!chatQuestion.trim() || chatLoading) return
    setChatLoading(true)
    setChatAnswer('')
    const form = new FormData()
    form.append('question', chatQuestion)
    if (selectedCollection) form.append('collections', selectedCollection)
    form.append('n', '6')
    try {
      const resp = await fetch(`${BASE}/kb/ask`, { method: 'POST', body: form })
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let doneFlag = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6)
            if (chunk === '[DONE]') { doneFlag = true; break }
            setChatAnswer(t => t + chunk)
          }
        }
        if (doneFlag) break
      }
    } catch (e) {
      setChatAnswer('Error: ' + e.message)
    }
    setChatLoading(false)
  }

  const handleDelete = async (fileHash) => {
    try {
      await deleteKBDocument(fileHash)
      showToast('Document deleted', 'success')
      await load()
    } catch { showToast('Delete failed', 'error') }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleUpload(Array.from(e.dataTransfer.files))
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1048576).toFixed(1) + ' MB'
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 page-enter">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Database size={20} className="text-[#7c6af7]" />
          <h1 className="text-lg font-semibold text-[#e8e8e8]">Knowledge Base</h1>
        </div>
        {stats && (
          <div className="flex items-center gap-4 text-xs text-[#555]">
            <span className="flex items-center gap-1"><FileText size={12} /> {stats.total_documents} docs</span>
            <span className="flex items-center gap-1"><Hash size={12} /> {stats.total_chunks} chunks</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[#0a0a0a] rounded-xl p-1 border border-[#1a1a1a]">
        {[
          { id: 'upload', label: 'Upload', icon: Upload },
          { id: 'chat', label: 'Ask Docs', icon: MessageSquare },
          { id: 'search', label: 'Search', icon: Search },
          { id: 'documents', label: 'Documents', icon: FileText },
          { id: 'collections', label: 'Collections', icon: FolderOpen },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-all ${
              tab === t.id ? 'bg-[#1a1a1a] text-[#e8e8e8] shadow-sm' : 'text-[#555] hover:text-[#888]'
            }`}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      {/* Collection filter */}
      <div className="mb-4">
        <select value={selectedCollection || ''} onChange={e => setSelectedCollection(e.target.value || null)}
          className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-xs text-[#e8e8e8] outline-none focus:border-[#7c6af7]/50">
          <option value="">All collections</option>
          {Object.entries(COLLECTION_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v.emoji} {v.label}</option>
          ))}
        </select>
      </div>

      {/* Upload Tab */}
      {tab === 'upload' && (
        <div className="space-y-4">
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all ${
              dragOver
                ? 'border-[#7c6af7] bg-[#7c6af7]/5'
                : 'border-[#2a2a2a] hover:border-[#444]'
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-[#888]">Processing documents...</p>
              </div>
            ) : (
              <>
                <Upload size={32} className="text-[#444] mx-auto mb-3" />
                <p className="text-sm text-[#888] mb-2">Drag & drop files here, or click to browse</p>
                <p className="text-[10px] text-[#444] mb-4">PDF, DOCX, PPTX, TXT, MD, HTML, CSV, JSON, images</p>
                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#7c6af7] text-white text-xs font-medium cursor-pointer hover:bg-[#6a59e0] transition-colors">
                  <Upload size={12} /> Choose Files
                  <input type="file" multiple className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.html,.csv,.json,.xml,.png,.jpg,.jpeg,.webp"
                    onChange={e => handleUpload(Array.from(e.target.files))} />
                </label>
              </>
            )}
          </div>

          {/* Recent uploads */}
          {documents.length > 0 && (
            <div>
              <h3 className="text-xs text-[#555] mb-2">Recently ingested</h3>
              <div className="space-y-1">
                {documents.slice(0, 5).map((doc, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#141414] border border-[#1a1a1a] text-xs">
                    <FileText size={12} className="text-[#555]" />
                    <span className="text-[#e8e8e8] truncate">{doc.title}</span>
                    <span className="text-[10px] text-[#444] ml-auto">{doc.chunks_stored} chunks</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ask Docs Tab — multi-document RAG chat */}
      {tab === 'chat' && (
        <div className="space-y-4">
          <p className="text-xs text-[#555]">
            Ask a question and ARIA will search <span className="text-[#a89bf8]">
            {selectedCollection ? COLLECTION_LABELS[selectedCollection]?.label || selectedCollection : 'all'}</span>
            {' '}document{selectedCollection ? '' : 's'} in your knowledge base, then answer with the sources used.
          </p>
          <div className="flex gap-2">
            <textarea value={chatQuestion} onChange={e => setChatQuestion(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }}}
              placeholder="e.g. What are the key facts about the Nile River?"
              rows={3}
              className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50 resize-none" />
            <button onClick={handleAsk} disabled={!chatQuestion.trim() || chatLoading}
              className="px-4 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors self-end">
              {chatLoading ? <RefreshCw size={14} className="animate-spin" /> : <MessageSquare size={14} />}
            </button>
          </div>
          {chatLoading && !chatAnswer && (
            <div className="flex items-center gap-2 text-xs text-[#555] py-2">
              <div className="w-3.5 h-3.5 border-2 border-[#7c6af7] border-t-transparent rounded-full animate-spin" />
              Searching knowledge base and answering...
            </div>
          )}
          {chatAnswer && (
            <div className="p-4 rounded-xl bg-[#141414] border border-[#2a2a2a] text-sm text-[#d0d0d0] leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
              {chatAnswer}
            </div>
          )}
          <p className="text-[10px] text-[#444]">
            {stats?.total_documents || 0} documents indexed · answers cite the sources used
          </p>
        </div>
      )}

      {/* Search Tab */}
      {tab === 'search' && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Search your knowledge base..."
              className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#e8e8e8] placeholder-[#444] outline-none focus:border-[#7c6af7]/50" />
            <button onClick={handleSearch} disabled={searching}
              className="px-4 py-2.5 rounded-xl bg-[#7c6af7] text-white text-sm font-medium hover:bg-[#6a59e0] disabled:opacity-40 transition-colors">
              {searching ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-[#555]">{searchResults.length} results found</p>
              {searchResults.map((r, i) => (
                <div key={i} className="p-4 rounded-xl bg-[#141414] border border-[#1a1a1a] hover:border-[#7c6af7]/20 transition-colors">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] ${COLLECTION_LABELS[r.collection]?.color || 'text-[#888]'}`}>
                      {COLLECTION_LABELS[r.collection]?.emoji} {COLLECTION_LABELS[r.collection]?.label || r.collection}
                    </span>
                    <span className="text-[10px] text-[#444]">{r.metadata?.source}</span>
                    <span className="text-[10px] text-[#7c6af7] ml-auto">{(r.score * 100).toFixed(0)}% match</span>
                  </div>
                  <p className="text-xs text-[#aaa] leading-relaxed line-clamp-4">{r.text}</p>
                </div>
              ))}
            </div>
          )}

          {searchQuery && searchResults.length === 0 && !searching && (
            <div className="text-center py-12">
              <Search size={24} className="text-[#333] mx-auto mb-2" />
              <p className="text-xs text-[#555]">No results found. Try different keywords.</p>
            </div>
          )}
        </div>
      )}

      {/* Documents Tab */}
      {tab === 'documents' && (
        <div className="space-y-2">
          {documents.length === 0 ? (
            <div className="text-center py-12">
              <FileText size={24} className="text-[#333] mx-auto mb-2" />
              <p className="text-xs text-[#555]">No documents ingested yet</p>
            </div>
          ) : (
            documents.map((doc, i) => (
              <div key={i} className="rounded-xl bg-[#141414] border border-[#1a1a1a] overflow-hidden">
                <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#1a1a1a] transition-colors"
                  onClick={() => setExpandedDoc(expandedDoc === i ? null : i)}>
                  <FileText size={14} className="text-[#555]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-[#e8e8e8] truncate">{doc.title}</p>
                    <p className="text-[10px] text-[#444]">{doc.chunks_stored} chunks · {formatSize(doc.file_size)}</p>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] ${COLLECTION_LABELS[doc.collection]?.color || 'text-[#888]'}`}>
                    {COLLECTION_LABELS[doc.collection]?.label || doc.collection}
                  </span>
                  <button onClick={(e) => { e.stopPropagation(); handleDelete(doc.file_hash) }}
                    className="p-1.5 rounded-lg text-[#555] hover:text-red-400 hover:bg-red-500/10 transition-colors">
                    <Trash2 size={12} />
                  </button>
                  {expandedDoc === i ? <ChevronUp size={12} className="text-[#444]" /> : <ChevronDown size={12} className="text-[#444]" />}
                </div>
                {expandedDoc === i && (
                  <div className="px-4 pb-3 border-t border-[#1a1a1a]">
                    <div className="grid grid-cols-2 gap-2 mt-2 text-[10px] text-[#555]">
                      <span>Hash: {doc.file_hash}</span>
                      <span>Ingested: {new Date(doc.ingested_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Collections Tab */}
      {tab === 'collections' && (
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(COLLECTION_LABELS).map(([key, info]) => {
            const col = stats?.collections?.[key]
            return (
              <div key={key} className="p-4 rounded-xl bg-[#141414] border border-[#1a1a1a] hover:border-[#7c6af7]/20 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{info.emoji}</span>
                  <span className="text-xs font-medium text-[#e8e8e8]">{info.label}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-[#555]">
                  <span>{col?.documents || 0} docs</span>
                  <span>{col?.chunks || 0} chunks</span>
                </div>
                <p className="text-[10px] text-[#444] mt-1">{col?.description || ''}</p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
