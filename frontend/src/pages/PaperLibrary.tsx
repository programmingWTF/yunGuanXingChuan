/**
 * 云观星传 - 个人论文库（我的论文库）
 *
 * 用户上传自己的论文（PDF/DOCX/MD/TXT），系统解析后存入用户级向量库，
 * 并在学术写作阶段自动学习其风格（风格三件套）。
 *
 * 上传链路（R2 直传，绕开 CF Tunnel 100MB/100s 限制）：
 *   1. POST /library/upload-url → 后端签发 presigned PUT URL + 建记录
 *   2. 浏览器直接 PUT 文件到 R2（不经过后端，带进度条）
 *   3. POST /library/confirm → 后端拉取解析/嵌入/风格提取
 */
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import axios from 'axios'
import { useAuth } from '../auth'
import {
  confirmLibraryUpload, createLibraryUpload, deleteLibraryPaper,
  getLibraryHealth, getLibraryStyle, listLibraryPapers, searchLibrary,
  type LibraryPaper, type LibrarySearchResult, type LibraryStyle,
} from '../api'

const ACCEPT = '.pdf,.docx,.md,.txt'

const STATUS_META: Record<string, { label: string; cls: string }> = {
  uploaded: { label: '待处理', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  processing: { label: '处理中', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200 animate-pulse' },
  ready: { label: '已就绪', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  error: { label: '失败', cls: 'bg-red-50 text-red-700 border-red-200' },
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function PaperLibrary() {
  const { user } = useAuth()
  const [health, setHealth] = useState<{ r2_configured: boolean; supported_extensions: string[] } | null>(null)
  const [papers, setPapers] = useState<LibraryPaper[]>([])
  const [style, setStyle] = useState<LibraryStyle | null>(null)
  const [searchResults, setSearchResults] = useState<LibrarySearchResult[] | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)

  // 上传状态
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0) // 0-100
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadAll = useCallback(async () => {
    try {
      const [h, ps, st] = await Promise.all([
        getLibraryHealth(), listLibraryPapers(), getLibraryStyle().catch(() => null),
      ])
      setHealth(h)
      setPapers(ps)
      setStyle(st)
    } catch {
      // 未登录或后端异常：静默（页面顶部有守卫提示）
    }
  }, [])

  useEffect(() => {
    if (user) void loadAll()
  }, [user, loadAll])

  // ── 上传流程 ──
  const startUpload = async (file: File) => {
    setError(null); setNotice(null)
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
    if (!['.pdf', '.docx', '.md', '.txt'].includes(ext)) {
      setError(`不支持的文件类型 ${ext || '(无扩展名)'}，支持：PDF / DOCX / MD / TXT`)
      return
    }
    setFileName(file.name)
    setUploading(true)
    setProgress(1)
    try {
      // ① 签发 presigned PUT URL
      const { upload_url, paper_id } = await createLibraryUpload(file.name, file.type || 'application/octet-stream')
      setProgress(5)
      // ② 浏览器直传 R2（整文件 PUT，presigned URL 指向 r2.cloudflarestorage.com，不走 CF 代理）
      await axios.put(upload_url, file, {
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        onUploadProgress: (e) => {
          if (e.total) setProgress(5 + Math.round(((e.loaded / e.total) * 90)))
        },
        timeout: 300000, // 大文件 5 分钟
      })
      setProgress(96)
      // ③ 确认 → 后端解析/嵌入/风格提取
      const res = await confirmLibraryUpload(paper_id)
      setProgress(100)
      if (res.status === 'ready') {
        setNotice(`「${file.name}」已入库（${res.chunk_count} 个片段），风格已提取`)
      }
      void loadAll()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string }).response?.data?.detail
        ?? (e as { message?: string }).message
        ?? '上传失败'
      setError(typeof msg === 'string' ? msg : '上传失败')
      void loadAll() // 刷新状态（可能已建记录但上传中断）
    } finally {
      setUploading(false)
    }
  }

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) void startUpload(f)
    e.target.value = ''
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) void startUpload(f)
  }

  const onDelete = async (id: number, name: string) => {
    if (!window.confirm(`确定删除「${name}」？将同时移除向量索引与 R2 文件。`)) return
    try {
      await deleteLibraryPaper(id)
      setNotice(`已删除「${name}」`)
      void loadAll()
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? '删除失败')
    }
  }

  const onSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true); setError(null)
    try {
      const res = await searchLibrary(searchQuery.trim(), 5)
      setSearchResults(res.results)
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? '检索失败')
      setSearchResults(null)
    } finally {
      setSearching(false)
    }
  }

  // ── 未登录守卫 ──
  if (!user) {
    return (
      <div className="py-16 text-center">
        <p className="text-4xl mb-4">📚</p>
        <h2 className="font-display text-xl font-semibold text-slate-800">个人论文库</h2>
        <p className="text-sm text-slate-500 mt-3 max-w-md mx-auto leading-relaxed">
          登录后即可上传自己的论文（PDF/DOCX/MD/TXT），让 AI 学习你的研究成果与写作风格，
          在学术写作阶段真正用上你自己的科研积累。
        </p>
        <a href="/login" className="inline-block mt-5 text-sm font-medium px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all">
          去登录
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页头 */}
      <div className="py-1">
        <h2 className="font-display text-2xl font-semibold text-slate-900 tracking-tight">📚 我的论文库</h2>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed max-w-3xl">
          上传你自己的论文/报告，系统解析后建立<strong className="text-slate-700">个人专属向量库</strong>，
          并提取你的<strong className="text-slate-700">学术写作风格</strong>（术语 / 结构 / 句式）。学术写作阶段会自动参考你的风格与既有研究。
          {health && !health.r2_configured && (
            <span className="ml-2 text-amber-600 font-medium">⚠ 存储未配置（R2），上传暂不可用</span>
          )}
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 flex items-start justify-between gap-3">
          <span>❌ {error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">✕</button>
        </div>
      )}
      {notice && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-700 flex items-start justify-between gap-3">
          <span>✅ {notice}</span>
          <button onClick={() => setNotice(null)} className="text-emerald-400 hover:text-emerald-600">✕</button>
        </div>
      )}

      {/* 上传区 */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`rounded-2xl border-2 border-dashed px-6 py-8 text-center cursor-pointer transition-all ${
          dragOver ? 'border-indigo-400 bg-indigo-50/60' : 'border-slate-300 bg-white hover:border-indigo-300 hover:bg-slate-50/50'
        } ${uploading ? 'pointer-events-none opacity-80' : ''}`}
      >
        <input ref={fileInputRef} type="file" accept={ACCEPT} className="hidden" onChange={onPickFile} />
        {!uploading ? (
          <>
            <p className="text-3xl mb-2">📄</p>
            <p className="text-sm font-medium text-slate-700">点击选择或拖拽论文文件到此处</p>
            <p className="text-[11px] text-slate-400 mt-1.5">支持 PDF / DOCX / MD / TXT（单文件建议 ≤ 50MB，直传 R2 不走隧道）</p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-700 mb-3">
              正在上传「{fileName}」… {progress}%
            </p>
            <div className="h-2 rounded-full bg-slate-200 overflow-hidden max-w-md mx-auto">
              <div className="h-full bg-indigo-500 transition-all duration-200" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-[11px] text-slate-400 mt-2">
              {progress < 95 ? '直传 Cloudflare R2…' : '后端解析 & 向量化…'}
            </p>
          </>
        )}
      </div>

      {/* 检索测试 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-1">🔍 试一下检索你的论文库</h3>
        <p className="text-[11px] text-slate-400 mb-3">输入一个研究方向/关键词，看 AI 能从你库里召回什么。</p>
        <form onSubmit={onSearch} className="flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="例如：深度学习在医学影像中的应用"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
          <button type="submit" disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-40 transition-all">
            {searching ? '检索中…' : '检索'}
          </button>
        </form>
        {searchResults !== null && (
          <div className="mt-4 space-y-2">
            {searchResults.length === 0 ? (
              <p className="text-xs text-slate-400">没有命中（论文库可能为空，或语义距离较远）</p>
            ) : searchResults.map((r, i) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium text-slate-500 truncate">
                    {String(r.metadata?.title ?? '')} · 片段 {i + 1}
                  </span>
                  <span className="text-[11px] font-mono text-indigo-600 shrink-0">{(r.score * 100).toFixed(0)}%</span>
                </div>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed line-clamp-2">{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 论文列表 */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800">📄 我的论文（{papers.length}）</h3>
            <button onClick={() => void loadAll()} className="text-[11px] text-slate-400 hover:text-indigo-600 transition-colors">↻ 刷新</button>
          </div>
          {papers.length === 0 ? (
            <p className="text-xs text-slate-400 py-8 text-center">还没有论文，先上传一篇吧</p>
          ) : (
            <ul className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
              {papers.map((p) => {
                const st = STATUS_META[p.status] ?? STATUS_META.uploaded
                return (
                  <li key={p.id} className="group rounded-lg border border-slate-100 hover:border-slate-200 bg-slate-50/50 hover:bg-white px-3 py-2.5 transition-all">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-700 truncate">{p.file_name}</p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          {fmtTime(p.created_at)}
                          {p.status === 'ready' && p.chunk_count > 0 && ` · ${p.chunk_count} 片段`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${st.cls}`}>{st.label}</span>
                        <button onClick={() => void onDelete(p.id, p.file_name)}
                          className="opacity-0 group-hover:opacity-100 text-[11px] text-slate-300 hover:text-red-600 transition-all" title="删除">
                          🗑
                        </button>
                      </div>
                    </div>
                    {p.status === 'error' && p.error_msg && (
                      <p className="text-[10px] text-red-500 mt-1.5 truncate" title={p.error_msg}>⚠ {p.error_msg}</p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* 风格三件套 */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800">✍️ 已学习的写作风格</h3>
            {style && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 border border-violet-200">
                {style.terms?.length ?? 0} 术语 · {style.few_shot?.length ?? 0} 示例
              </span>
            )}
          </div>
          {!style ? (
            <p className="text-xs text-slate-400 py-8 text-center leading-relaxed">
              上传并处理论文后，这里会展示从你的论文中提取的
              <br />术语表 / 结构习惯 / 代表性句式，学术写作会自动参考
            </p>
          ) : (
            <div className="space-y-4">
              {style.terms && style.terms.length > 0 && (
                <div>
                  <p className="text-[11px] font-medium text-slate-500 mb-1.5">🔤 高频术语</p>
                  <div className="flex flex-wrap gap-1.5">
                    {style.terms.slice(0, 15).map((t, i) => (
                      <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">{t}</span>
                    ))}
                    {style.terms.length > 15 && <span className="text-[11px] text-slate-300 self-center">+{style.terms.length - 15}</span>}
                  </div>
                </div>
              )}
              {style.structure?.avg_sentence_len ? (
                <div>
                  <p className="text-[11px] font-medium text-slate-500 mb-1.5">📐 句式习惯</p>
                  <p className="text-xs text-slate-600">平均句长约 <strong className="text-slate-800">{style.structure.avg_sentence_len}</strong> 字
                    {style.structure.sections_detected && style.structure.sections_detected.length > 0 && (
                      <> · 章节结构：<span className="text-slate-500">{style.structure.sections_detected.slice(0, 6).join(' → ')}</span></>
                    )}
                  </p>
                </div>
              ) : null}
              {style.few_shot && style.few_shot.length > 0 && (
                <div>
                  <p className="text-[11px] font-medium text-slate-500 mb-1.5">💬 代表性句式（few-shot）</p>
                  <div className="space-y-1.5">
                    {style.few_shot.map((s, i) => (
                      <blockquote key={i} className="text-xs text-slate-600 leading-relaxed border-l-2 border-violet-200 pl-2.5 py-0.5 line-clamp-2">
                        “{s}”
                      </blockquote>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}