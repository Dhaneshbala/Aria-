import { useEffect, useState, useRef } from 'react'
import {
  uploadToKB, listKBDocuments, deleteKBDocument, getKBStats,
  getKBCollections, searchKB
} from '../services/api'
import { showToast } from '../components/Toast'
import ConfirmModal from '../components/ui/ConfirmModal'
import { Database, Upload, Search, Trash2, FileText, Loader, X, FolderOpen } from 'lucide-react'

export default function KBPage() {
  const [documents, setDocuments] = useState([])
  const [stats, setStats] = useState(null)
  const [collections, setCollections] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [activeCollection, setActiveCollection] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null) // {hash, name}
  const fileRef = useRef(null)

  const load = async () => {
    try {
      const [docs, st, cols] = await Promise.all([
        listKBDocuments(activeCollection).catch(() => []),
        getKBStats().catch(() => null),
        getKBCollections().catch(() => []),
      ])
      setDocuments(Array.isArray(docs) ? docs : [])
      setStats(st)
      setCollections(Array.isArray(cols) ? cols : [])
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [activeCollection])

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    let success = 0
    for (const f of files) {
      try {
        await uploadToKB(f)
        success++
      } catch (err) {
        showToast(`Failed: ${f.name} — ${err.message}`, 'error')
      }
    }
    setUploading(false)
    if (success) {
      showToast(`${success} document${success > 1 ? 's' : ''} uploaded`, 'success', 2500)
      load()
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleDelete = async () => {
    const { hash } = pendingDelete || {}
    if (!hash && hash !== 0) { setPendingDelete(null); return }
    try {
      await deleteKBDocument(hash)
      setDocuments(prev => prev.filter(d => d.file_hash !== hash))
      showToast('Document deleted', 'success', 2500)
      load()
    } catch (e) { showToast('Delete failed', 'error') }
    finally { setPendingDelete(null) }
  }

  const handleSearch = async (q) => {
    setSearch(q)
    if (!q.trim()) { setSearchResults(null); return }
    try {
      const results = await searchKB(q)
      setSearchResults(results?.results || results || [])
    } catch { setSearchResults([]) }
  }

  const items = searchResults || documents

  return (
    <div className="flex flex-col h-full w-full bg-[#131314]">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-6">
          {/* Header */}
          <div className="flex items-center gap-3 mb-4">
            <Database size={20} className="text-[#8ab4f8]" />
            <h1 className="text-xl font-semibold text-[#e3e3e3]">Knowledge Base</h1>
            {stats && (
              <span className="text-xs text-[#5f6368] ml-auto">
                {stats.total_documents || 0} docs · {stats.total_chunks || 0} chunks
              </span>
            )}
          </div>

          {/* Upload + Search */}
          <div className="flex gap-2 mb-4">
            <button onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#8ab4f8] text-[#062e6f] text-xs font-semibold hover:bg-[#aecbfa] transition-colors disabled:opacity-50">
              {uploading ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
            <input ref={fileRef} type="file" multiple className="hidden" onChange={handleUpload}
              accept=".pdf,.txt,.md,.docx,.csv,.json,.html" />
            <div className="flex-1 relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#5f6368]" />
              <input value={search} onChange={e => handleSearch(e.target.value)}
                placeholder="Search knowledge base…"
                className="w-full pl-9 pr-3 py-2 bg-[#1e1f20] border border-[#2d2e30] rounded-xl text-sm text-[#e3e3e3] placeholder-[#5f6368] outline-none focus:border-[#8ab4f8]" />
            </div>
          </div>

          {/* Collections */}
          {collections.length > 0 && (
            <div className="flex gap-1.5 mb-4 overflow-x-auto pb-1">
              <button onClick={() => setActiveCollection(null)}
                className={`shrink-0 text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  !activeCollection ? 'bg-[#8ab4f8]/15 border-[#8ab4f8] text-[#8ab4f8]' : 'border-[#2d2e30] text-[#9aa0a6] hover:border-[#3c4043]'
                }`}>
                All
              </button>
              {collections.map(c => (
                <button key={c.name || c} onClick={() => setActiveCollection(c.name || c)}
                  className={`shrink-0 text-xs px-3 py-1.5 rounded-full border transition-colors capitalize ${
                    activeCollection === (c.name || c) ? 'bg-[#8ab4f8]/15 border-[#8ab4f8] text-[#8ab4f8]' : 'border-[#2d2e30] text-[#9aa0a6] hover:border-[#3c4043]'
                  }`}>
                  {c.name || c}
                </button>
              ))}
            </div>
          )}

          {/* Document list */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader size={18} className="text-[#5f6368] animate-spin" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12">
              <FolderOpen size={40} className="text-[#2d2e30] mx-auto mb-2" />
              <p className="text-sm text-[#5f6368]">{search ? 'No results' : 'No documents yet'}</p>
              <p className="text-xs text-[#3c4043] mt-1">Upload PDFs, notes, or text files</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {items.map((doc, i) => {
                const hash = doc.file_hash || doc.hash || i
                const name = doc.filename || doc.name || doc.file_name || `Document ${i + 1}`
                const collection = doc.collection || ''
                const chunks = doc.chunk_count || doc.chunks || '?'
                return (
                  <div key={hash}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#1e1f20] transition-colors">
                    <FileText size={16} className="text-[#5f6368] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[#e3e3e3] truncate">{name}</p>
                      <p className="text-[10px] text-[#5f6368]">
                        {collection && <span className="capitalize">{collection}</span>}
                        {collection && chunks !== '?' && ' · '}
                        {chunks !== '?' && `${chunks} chunks`}
                      </p>
                    </div>
                    <button onClick={() => setPendingDelete({ hash, name })}
                      aria-label={`Delete ${name}`}
                      className="p-1.5 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-[#5f6368] hover:text-red-400 transition-all">
                      <Trash2 size={12} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
      <ConfirmModal
        open={pendingDelete !== null}
        title={`Delete "${pendingDelete?.name || 'document'}"?`}
        body="This removes it from the Knowledge Base. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  )
}
