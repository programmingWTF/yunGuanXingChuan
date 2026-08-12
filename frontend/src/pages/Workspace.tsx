/**
 * 云观星传 - 科研工作台（合并版主页，默认打开）
 *
 * 将「科研首页」与「我的项目」合并为单一入口：
 * - 左侧：项目历史记录列表（点击加载）
 * - 右侧：新建项目（输入兴趣 → 一键生成全部）+ 选中项目详情
 *   （Research Pipeline 进度 / 7 阶段产出物 / 导出 Markdown/JSON）
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'
import { useStore } from '../store'
import { useAuth } from '../auth'
import { runAllWorkflow, getWorkflowProject, exportWorkflowProject, getHotTopics, deleteWorkflowProject } from '../api'
import type { ResearchProject } from '../api'
import ResearchPipeline from '../components/ResearchPipeline'
import ConfirmDialog from '../components/ConfirmDialog'

const STAGE_NAMES: Record<string, string> = {
  '1': '选题孵化', '2': '文献综述', '3': '研究设计',
  '4': '方法推荐', '5': '数据分析', '6': '学术写作', '7': '同行评审',
}
const STAGE_ICONS: Record<string, string> = {
  '1': '💡', '2': '📚', '3': '🎯', '4': '🧪', '5': '📊', '6': '✍️', '7': '👨‍⚖️',
}
const STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: '待开始', cls: 'text-slate-500 border-slate-200' },
  running: { label: '运行中', cls: 'text-amber-600 border-red-200 animate-pulse' },
  awaiting_review: { label: '待确认', cls: 'text-sky-600 border-sky-300' },
  completed: { label: '已完成', cls: 'text-emerald-600 border-emerald-300' },
  failed: { label: '失败', cls: 'text-red-600 border-red-300' },
}

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function Workspace() {
  const { projects, currentProject, refreshProjects, loadProject, createProject, setCurrentProject, setProjects } = useStore()
  const { user } = useAuth()
  const [interest, setInterest] = useState('')
  const [creating, setCreating] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  // 「一键生成全部」二次确认（会串行重跑 7 阶段并覆盖全部产出物，issue #66）
  const [confirmingAll, setConfirmingAll] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])

  /** 新建项目并一键生成全部（轮询进度） */
  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    if (!interest.trim()) return
    setCreating(true)
    setError('')
    try {
      const p = await createProject('', interest.trim())
      setInterest('')
      await handleRunAll(p.id)
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 404 ? '后端未包含 /api/workflow（请先更新后端）' : '创建项目失败，请确认后端已启动')
      setCreating(false)
    }
  }

  /** 触发一键全流程并轮询各阶段进度 */
  const handleRunAll = async (projectId?: string) => {
    const id = projectId ?? currentProject?.id
    if (!id) return
    setGeneratingAll(true)
    setError('')
    setCreating(false)
    try {
      await runAllWorkflow(id)
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 400 ? '该项目已全部生成完成' : '启动全流程失败，请确认后端已启动')
      setGeneratingAll(false)
      return
    }
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const { project } = await getWorkflowProject(id)
        setCurrentProject(project)
        setProjects(prev => prev.map(p => (p.id === id ? project : p)))
        if (project.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGeneratingAll(false)
        }
      } catch { /* 网络抖动忽略 */ }
    }, 2500)
  }

  const handleSelect = async (id: string) => {
    setSelected(id)
    setConfirmDeleteId(null)  // 切换项目时收起未决的删除确认态
    try { await loadProject(id) } catch { /* ignore */ }
  }

  /** 删除：第一击进入确认态（按钮变红），第二击才真正删除（防误触）；已在确认态再点时执行删除 */
  const handleDeleteClick = (id: string) => {
    if (confirmDeleteId === id && deletingId !== id) {
      void handleConfirmDelete(id)
    } else {
      setConfirmDeleteId(prev => (prev === id ? null : id))
    }
  }

  /** 删除当前选中项目后的回退：清空选中态与当前项目 */
  const handleConfirmDelete = async (id: string) => {
    setDeletingId(id)
    setConfirmDeleteId(null)
    try {
      await deleteWorkflowProject(id)
      await refreshProjects()
      // 若删除的是当前选中/详情项目，回退到默认空态
      if (selected === id) {
        setSelected(null)
        setCurrentProject(null)
      }
    } catch {
      setError('删除失败，请确认后端已启动')
    } finally {
      setDeletingId(null)
    }
  }

  const [selected, setSelected] = useState<string | null>(null)
  // 删除历史记录：confirmDeleteId=待确认删除的项目 id（二次点击确认防误触）；deletingId=正在删除
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const detail: ResearchProject | null = currentProject?.id === selected ? currentProject : projects.find(p => p.id === selected) ?? projects[0] ?? null

  // ── 今日科技热点 + 最近任务（首页驾驶舱模块）──
  const [hotTopics, setHotTopics] = useState<{ title: string; url: string; source: string }[]>([])
  useEffect(() => {
    getHotTopics(5).then(({ topics }) => setHotTopics(topics)).catch(() => { /* 后端不可用忽略 */ })
  }, [])
  const pendingTasks = projects
    .filter(p => p.status !== 'completed')
    .map(p => ({
      id: p.id,
      title: p.title,
      stageName: STAGE_NAMES[String(p.current_stage)] ?? '—',
      icon: STAGE_ICONS[String(p.current_stage)] ?? '📁',
    }))
    .slice(0, 5)

  const handleExport = async (fmt: 'md' | 'json' | 'word' | 'pdf') => {
    if (!detail) return
    setExporting(true)
    try {
      if (fmt === 'word' || fmt === 'pdf') {
        // Word/PDF：二进制文件下载（下载文件名与后端一致净化，防头注入/非法字符）
        const safeTitle = (detail.title || '云观星传科研项目').replace(/[\r\n"\x00-\x1f]/g, '').trim() || '云观星传科研项目'
        const { blob } = await exportWorkflowProject(detail.id, fmt) as { blob: Blob }
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${safeTitle}.${fmt === 'word' ? 'docx' : 'pdf'}`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      } else {
        const { content } = await exportWorkflowProject(detail.id, fmt) as { content: string }
        downloadText(`${detail.title}.${fmt}`, content, fmt === 'md' ? 'text/markdown' : 'application/json')
      }
    } catch {
      setError('导出失败，请确认后端已启动')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 未配置 LLM API 引导（多租户自带钥匙模式） */}
      {user && !user.llm_configured && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs text-amber-700">
            ⚙️ 平台不提供推理 API：生成前请先在<b>模型设置</b>里填你自己的 Qwen API（Key / BaseURL / 模型ID，阿里云百炼或 Token Plan 获取，新用户有免费额度）。向量模型可选，不填自动降级。
          </p>
          <Link to="/settings" className="text-[11px] font-medium px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-all shrink-0">
            去配置 →
          </Link>
        </div>
      )}

      {/* 顶部标语（他山 Hero：短句 Slogan 体） */}
      <div className="py-4">
        <h2 className="font-display text-3xl font-semibold text-slate-900 tracking-tight leading-tight">
          让科研流程可见，让每个产出可验证。
        </h2>
        <p className="text-sm text-slate-500 mt-2.5 leading-relaxed max-w-2xl">
          输入研究兴趣，AI Scientist 协同完成 7 个科研阶段；每阶段产出经 RAG + 知识图谱双校验，历史项目可随时加载查看。
        </p>
      </div>

      {/* 科研驾驶舱：今日热点 + 最近任务 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="card-sweep p-4">
          <h3 className="sec-label !mb-2">🌐 今日科技热点</h3>
          {hotTopics.length === 0 ? (
            <p className="text-[11px] text-slate-400 py-2">暂无热点（后端搜索不可用时显示为空）</p>
          ) : (
            <ul className="space-y-1.5">
              {hotTopics.map((t, i) => {
                // 外部搜索来源的 url 不可信：仅渲染 http/https，其余按纯文本展示（防 javascript: 等注入）
                const safeUrl = /^https?:\/\//i.test(t.url || '') ? t.url : null
                return (
                  <li key={i}>
                    {safeUrl ? (
                      <a href={safeUrl} target="_blank" rel="noreferrer"
                        className="flex items-start gap-2 text-[12px] text-slate-600 hover:text-sky-700 transition-colors leading-snug">
                        <span className="text-[9px] font-mono text-slate-400 mt-0.5 shrink-0">#{i + 1}</span>
                        <span className="flex-1">{t.title}</span>
                      </a>
                    ) : (
                      <span className="flex items-start gap-2 text-[12px] text-slate-500 leading-snug">
                        <span className="text-[9px] font-mono text-slate-400 mt-0.5 shrink-0">#{i + 1}</span>
                        <span className="flex-1">{t.title}</span>
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
        <div className="card-sweep p-4">
          <h3 className="sec-label !mb-2">📋 最近任务</h3>
          {pendingTasks.length === 0 ? (
            <p className="text-[11px] text-slate-400 py-2">暂无进行中的项目，从左侧创建第一个吧</p>
          ) : (
            <ul className="space-y-1.5">
              {pendingTasks.map(t => (
                <li key={t.id} className="flex items-center gap-2.5 text-[12px] text-slate-600">
                  <span className="text-base shrink-0">{t.icon}</span>
                  <span className="truncate flex-1">{t.title}</span>
                  <span className="text-[10px] text-sky-600 shrink-0">当前：{t.stageName}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 新建项目 + 历史记录 */}
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-5">
        {/* 左：历史记录 + 新建 */}
        <div className="space-y-4">
          {/* 新建项目 */}
          <form onSubmit={handleCreate} className="card p-4">
            <h3 className="sec-label !mb-2">新建研究项目</h3>
            <textarea
              value={interest}
              onChange={e => setInterest(e.target.value)}
              placeholder="输入研究兴趣，如：嫦娥七号月球南极探测的国际报道"
              rows={3}
              className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-sky-300 resize-none"
            />
            {error && <p className="text-[11px] text-red-600 mt-2">{error}</p>}
            <button type="submit" disabled={creating || generatingAll || !interest.trim()}
              className="btn-primary w-full mt-3 text-xs disabled:opacity-40 disabled:cursor-not-allowed">
              {creating ? '创建中…' : generatingAll ? '⏳ 全流程生成中…' : '🚀 新建并一键生成'}
            </button>
            {generatingAll && (
              <p className="text-[10px] text-sky-600 mt-2 animate-pulse">AI 正在串行生成 7 个阶段（约 8-12 分钟），进度实时更新，可离开页面</p>
            )}
          </form>

          {/* 历史记录 */}
          <div className="card p-4">
            <h3 className="sec-label !mb-2">历史记录（{projects.length}）</h3>
            <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
              {projects.length === 0 && (
                <p className="text-[11px] text-slate-400 py-4 text-center">暂无项目，从上方创建第一个吧</p>
              )}
              {projects.map(p => (
                <button
                  key={p.id}
                  onClick={() => handleSelect(p.id)}
                  className={`group w-full text-left rounded-xl border px-3 py-2.5 transition-all ${
                    selected === p.id || (projects[0]?.id === p.id && selected === null)
                      ? 'border-sky-300 bg-sky-50'
                      : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[13px] font-medium text-slate-700 truncate">{p.title}</p>
                    <span className="flex items-center gap-1.5 shrink-0">
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${
                        p.status === 'completed' ? 'text-emerald-600 border-emerald-200' : 'text-sky-600 border-sky-200'
                      }`}>
                        {p.status === 'completed' ? '已完成' : '进行中'}
                      </span>
                      {/* 删除（hover 显示防误触；第一击进确认态 → 第二击真正删除） */}
                      <span
                        role="button"
                        tabIndex={-1}
                        aria-label={`删除项目 ${p.title}`}
                        onClick={e => { e.stopPropagation(); handleDeleteClick(p.id) }}
                        className={`px-1.5 py-0.5 rounded text-[10px] border transition-all select-none ${
                          deletingId === p.id
                            ? 'opacity-60 cursor-wait bg-red-50 text-red-400 border-red-200'
                            : confirmDeleteId === p.id
                              ? 'bg-red-600 text-white border-red-600 font-medium'
                              : 'opacity-0 group-hover:opacity-100 text-slate-400 border-transparent hover:text-red-600 hover:border-red-200 cursor-pointer'
                        }`}
                      >
                        {deletingId === p.id ? '删除中…' : confirmDeleteId === p.id ? '确认删除？' : '🗑 删除'}
                      </span>
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-0.5 truncate">{p.interest}</p>
                  <div className="flex items-center gap-1 mt-1.5">
                    {Object.keys(p.stages).map(s => {
                      const st = p.stages[s]?.status
                      const on = st === 'completed' || st === 'awaiting_review' || st === 'running'
                      return <span key={s} className={`w-3 h-1.5 rounded-full ${on ? (st === 'completed' ? 'bg-emerald-500' : 'bg-sky-500') : 'bg-slate-100'}`} />
                    })}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 右：选中项目详情 */}
        <div className="card-sweep p-5">
          {!detail ? (
            <p className="text-xs text-slate-400 text-center py-16">创建项目后，这里将展示 7 阶段进度与产出物</p>
          ) : (
            <div className="space-y-5">
              {/* 项目头 + 操作 */}
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <h3 className="font-display text-lg font-bold text-slate-800">{detail.title}</h3>
                  <p className="text-[11px] text-slate-500 mt-1">兴趣：{detail.interest}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">创建于 {detail.created_at?.slice(0, 19).replace('T', ' ')}</p>
                </div>
                <div className="flex gap-2 flex-wrap shrink-0">
                  {detail.status !== 'completed' && (
                    <button onClick={() => setConfirmingAll(true)} disabled={generatingAll}
                      className="text-xs px-3 py-1.5 rounded-lg border border-sky-300 bg-sky-50 text-sky-600 hover:bg-sky-100 disabled:opacity-40 transition-all">
                      {generatingAll ? '⏳ 生成中…' : '🚀 一键生成全部'}
                    </button>
                  )}
                  <button onClick={() => handleExport('md')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-40 transition-all">
                    {exporting ? '导出中…' : '导出 Markdown'}
                  </button>
                  <button onClick={() => handleExport('word')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-40 transition-all">
                    Word
                  </button>
                  <button onClick={() => handleExport('pdf')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-40 transition-all">
                    PDF
                  </button>
                  <button onClick={() => handleExport('json')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-40 transition-all">
                    JSON
                  </button>
                </div>
              </div>

              {/* Research Pipeline 进度 */}
              <div className="border-t border-slate-100 pt-4">
                <ResearchPipeline stages={detail.stages} currentStage={detail.current_stage} />
              </div>

              {/* 7 阶段产出物摘要 */}
              <div className="space-y-2.5 border-t border-slate-100 pt-4">
                {Object.keys(detail.stages).map(s => {
                  const rec = detail.stages[s]
                  const meta = STATUS_META[rec?.status] ?? STATUS_META.pending
                  return (
                    <div key={s} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="text-base">{STAGE_ICONS[s]}</span>
                          <span className="text-[13px] font-medium text-slate-700">{STAGE_NAMES[s]}</span>
                          {rec?.error && <span className="text-[10px] text-red-600 truncate">{rec.error}</span>}
                        </div>
                        <span className={`text-[10px] shrink-0 px-2 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                      </div>
                      {rec?.output && (
                        <pre className="text-[9px] text-slate-500 whitespace-pre-wrap bg-slate-50 rounded-lg p-2.5 mt-2 max-h-24 overflow-y-auto">
                          {JSON.stringify(rec.output, null, 1).slice(0, 500)}
                        </pre>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 二次确认：一键生成全部会串行重跑 7 阶段并覆盖全部已确认产出物 */}
      <ConfirmDialog
        open={confirmingAll}
        title="确认一键生成全部？"
        description={
          <>
            将<strong className="text-red-600 font-medium">串行重跑全部 7 个阶段</strong>（约 8-12 分钟），
            <strong className="text-red-600 font-medium">覆盖当前项目的全部已确认产出物</strong>，此操作
            <strong className="text-red-600 font-medium">不可撤销</strong>。确认后点「继续」，否则点「取消」。
          </>
        }
        confirmText="继续生成"
        cancelText="取消"
        onCancel={() => setConfirmingAll(false)}
        onConfirm={() => { setConfirmingAll(false); void handleRunAll(detail?.id) }}
      />
    </div>
  )
}
