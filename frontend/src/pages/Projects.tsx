/**
 * 云观星传 - 我的科研项目
 *
 * 项目管理页：新建项目、阶段进度一览、各阶段产出物查看、
 * 一键导出（Markdown / JSON）。
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { useStore } from '../store'
import { exportWorkflowProject, runAllWorkflow, getWorkflowProject } from '../api'
import type { ResearchProject } from '../api'

const STAGE_NAMES: Record<string, string> = {
  '1': '选题孵化', '2': '文献综述', '3': '研究设计',
  '4': '方法推荐', '5': '数据分析', '6': '学术写作', '7': '同行评审',
}

const STAGE_ICONS: Record<string, string> = {
  '1': '💡', '2': '📚', '3': '🎯', '4': '🧪', '5': '📊', '6': '✍️', '7': '👨‍⚖️',
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: '待开始', cls: 'text-slate-500 border-white/10' },
  running: { label: '运行中', cls: 'text-flare-300 border-flare-400/40 animate-pulse' },
  awaiting_review: { label: '待确认', cls: 'text-astro-300 border-astro-400/50' },
  completed: { label: '已完成', cls: 'text-aurora-300 border-aurora-400/50' },
  failed: { label: '失败', cls: 'text-flare-400 border-flare-400/60' },
}

/** 下载文本文件 */
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

/** 产出物摘要（JSON 截断展示） */
function OutputSummary({ output }: { output: Record<string, unknown> | null }) {
  if (!output) return <p className="text-[11px] text-slate-600">暂无产出物</p>
  const text = JSON.stringify(output, null, 2)
  const preview = text.length > 400 ? text.slice(0, 400) + '…' : text
  return (
    <pre className="text-[10px] text-slate-400 whitespace-pre-wrap bg-black/20 rounded-lg p-3 max-h-40 overflow-y-auto">
      {preview}
    </pre>
  )
}

export default function Projects() {
  const { projects, currentProject, refreshProjects, loadProject, createProject, setCurrentProject, setProjects } = useStore()
  const [searchParams] = useSearchParams()
  const focusId = searchParams.get('focus')

  const [title, setTitle] = useState('')
  const [interest, setInterest] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(focusId)
  const [exporting, setExporting] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  // 组件卸载时停止轮询
  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])

  // 聚焦 URL 指定项目
  useEffect(() => {
    if (focusId) {
      setSelectedId(focusId)
      loadProject(focusId).catch(() => { /* ignore */ })
    }
  }, [focusId, loadProject])

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    if (!interest.trim()) return
    setCreating(true)
    setError('')
    try {
      const p = await createProject(title.trim() || interest.trim(), interest.trim())
      setSelectedId(p.id)
      setTitle('')
      setInterest('')
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 404
        ? '后端尚未包含 /api/workflow 路由（需先合并后端 PR #52），或服务未启动'
        : '创建项目失败，请确认后端服务已启动')
    } finally {
      setCreating(false)
    }
  }

  const handleSelect = async (id: string) => {
    setSelectedId(id)
    try {
      await loadProject(id)
    } catch { /* ignore */ }
  }

  /** 一键生成全部：触发后台 run-all 并轮询各阶段进度 */
  const handleRunAll = async () => {
    if (!selectedId) return
    setGeneratingAll(true)
    setError('')
    try {
      await runAllWorkflow(selectedId)
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 400 ? '该项目已全部生成完成' : '启动全流程失败，请确认后端已启动')
      setGeneratingAll(false)
      return
    }
    // 轮询项目详情（每 2.5 秒），阶段状态实时点亮
    pollRef.current = setInterval(async () => {
      try {
        const { project } = await getWorkflowProject(selectedId)
        setCurrentProject(project)
        setProjects(prev => prev.map(p => (p.id === selectedId ? project : p)))
        const allDone = project.status === 'completed'
        if (allDone) {
          if (pollRef.current) clearInterval(pollRef.current)
          setGeneratingAll(false)
        }
      } catch { /* 网络抖动忽略 */ }
    }, 2500)
  }

  const handleExport = async (fmt: 'md' | 'json') => {
    if (!selectedId) return
    setExporting(true)
    try {
      const { content } = await exportWorkflowProject(selectedId, fmt)
      const project = projects.find(p => p.id === selectedId)
      downloadText(
        `${project?.title ?? 'project'}.${fmt === 'md' ? 'md' : 'json'}`,
        content,
        fmt === 'md' ? 'text/markdown' : 'application/json',
      )
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 404 ? '导出接口不可用（后端需先合并 PR #52）' : '导出失败，请确认后端服务已启动')
    } finally {
      setExporting(false)
    }
  }

  const detail: ResearchProject | null = currentProject?.id === selectedId ? currentProject : projects.find(p => p.id === selectedId) ?? null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">我的科研项目</h2>
          <p className="text-xs text-slate-500 mt-1">项目管理 · 阶段进度 · 版本导出（Word / PDF / Markdown）</p>
        </div>
      </div>

      {/* 新建项目 */}
      <form onSubmit={handleCreate} className="card p-5">
        <h3 className="sec-label !mb-3">新建研究项目</h3>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto] gap-3">
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="项目名称（可选）"
            className="rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60"
          />
          <input
            value={interest}
            onChange={e => setInterest(e.target.value)}
            placeholder="研究兴趣 / 议题，如：朱雀2号火箭的国际报道"
            className="rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60"
          />
          <button type="submit" disabled={creating || !interest.trim()}
            className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
            {creating ? '创建中…' : '创建项目'}
          </button>
        </div>
        {error && <p className="text-[11px] text-flare-400 mt-2">{error}</p>}
      </form>

      {/* 项目列表 + 详情 */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
        {/* 项目列表 */}
        <div className="card p-4 space-y-2">
          <h3 className="sec-label !mb-2">项目列表（{projects.length}）</h3>
          {projects.length === 0 && (
            <p className="text-[11px] text-slate-600 py-6 text-center">还没有项目，从上方创建第一个科研项目吧</p>
          )}
          {projects.map(p => (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              className={`w-full text-left rounded-xl border px-3.5 py-3 transition-all ${
                selectedId === p.id
                  ? 'border-astro-400/60 bg-astro-500/10'
                  : 'border-white/10 bg-white/[0.02] hover:border-white/25'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-200 truncate">{p.title}</p>
                <span className={`text-[9px] shrink-0 px-1.5 py-0.5 rounded border ${
                  p.status === 'completed' ? 'text-aurora-300 border-aurora-400/40' : 'text-astro-300 border-astro-400/40'
                }`}>
                  {p.status === 'completed' ? '已完成' : '进行中'}
                </span>
              </div>
              <p className="text-[10px] text-slate-500 mt-1 truncate">{p.interest}</p>
              <div className="flex items-center gap-1 mt-2">
                {Object.keys(p.stages).map(s => {
                  const st = p.stages[s]?.status
                  const on = st === 'completed' || st === 'awaiting_review' || st === 'running'
                  return (
                    <span key={s} className={`w-3 h-1.5 rounded-full ${on ? (st === 'completed' ? 'bg-aurora-400' : 'bg-astro-400') : 'bg-white/10'}`} />
                  )
                })}
                <span className="ml-auto text-[9px] font-mono text-slate-600">阶段 {p.current_stage}/7</span>
              </div>
            </button>
          ))}
        </div>

        {/* 项目详情 */}
        <div className="card p-5">
          {!detail ? (
            <p className="text-xs text-slate-600 text-center py-16">选择左侧项目查看阶段进度与产出物</p>
          ) : (
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-display text-lg font-bold text-white">{detail.title}</h3>
                  <p className="text-[11px] text-slate-500 mt-1">兴趣：{detail.interest}</p>
                  <p className="text-[10px] text-slate-600 mt-0.5">创建于 {detail.created_at?.slice(0, 19).replace('T', ' ')}</p>
                </div>
                <div className="flex gap-2 shrink-0 flex-wrap">
                  {/* 一键生成全部 */}
                  {detail.status !== 'completed' && (
                    <button
                      onClick={handleRunAll}
                      disabled={generatingAll}
                      className="text-xs px-3 py-1.5 rounded-lg border border-astro-400/50 bg-astro-500/10 text-astro-300 hover:bg-astro-500/20 disabled:opacity-40 transition-all"
                    >
                      {generatingAll ? '⏳ 全流程生成中…' : '🚀 一键生成全部'}
                    </button>
                  )}
                  <button onClick={() => handleExport('md')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                    {exporting ? '导出中…' : '导出 Markdown'}
                  </button>
                  <button onClick={() => handleExport('json')} disabled={exporting || generatingAll}
                    className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                    JSON
                  </button>
                </div>
              </div>

              {/* 阶段进度 */}
              <div className="space-y-3">
                {Object.keys(detail.stages).map(s => {
                  const rec = detail.stages[s]
                  const meta = STATUS_META[rec?.status] ?? STATUS_META.pending
                  return (
                    <div key={s} className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="text-lg">{STAGE_ICONS[s]}</span>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-slate-200">
                              {STAGE_NAMES[s] ?? `阶段 ${s}`}
                              <span className="ml-2 text-[9px] font-mono text-slate-600">STAGE {s}</span>
                            </p>
                            {rec?.error && <p className="text-[10px] text-flare-400 mt-0.5">{rec.error}</p>}
                          </div>
                        </div>
                        <span className={`text-[10px] shrink-0 px-2 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                      </div>
                      {rec?.status !== 'pending' && (
                        <div className="mt-3">
                          <OutputSummary output={rec?.output ?? null} />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
