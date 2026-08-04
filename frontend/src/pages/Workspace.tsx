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
import { useStore } from '../store'
import { runAllWorkflow, getWorkflowProject, exportWorkflowProject } from '../api'
import type { ResearchProject } from '../api'
import ResearchPipeline from '../components/ResearchPipeline'

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
  const [interest, setInterest] = useState('')
  const [creating, setCreating] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
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
    try { await loadProject(id) } catch { /* ignore */ }
  }

  const [selected, setSelected] = useState<string | null>(null)
  const detail: ResearchProject | null = currentProject?.id === selected ? currentProject : projects.find(p => p.id === selected) ?? projects[0] ?? null

  const handleExport = async (fmt: 'md' | 'json') => {
    if (!detail) return
    setExporting(true)
    try {
      const { content } = await exportWorkflowProject(detail.id, fmt)
      downloadText(`${detail.title}.${fmt === 'md' ? 'md' : 'json'}`, content, fmt === 'md' ? 'text/markdown' : 'application/json')
    } catch {
      setError('导出失败，请确认后端已启动')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 顶部欢迎条 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">科研工作台</h2>
          <p className="text-xs text-slate-500 mt-1">输入研究兴趣 → 一键生成全部 7 个科研阶段；历史项目可随时加载查看</p>
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
              className="w-full rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60 resize-none"
            />
            {error && <p className="text-[11px] text-flare-400 mt-2">{error}</p>}
            <button type="submit" disabled={creating || generatingAll || !interest.trim()}
              className="btn-primary w-full mt-3 text-xs disabled:opacity-40 disabled:cursor-not-allowed">
              {creating ? '创建中…' : generatingAll ? '⏳ 全流程生成中…' : '🚀 新建并一键生成'}
            </button>
            {generatingAll && (
              <p className="text-[10px] text-astro-300 mt-2 animate-pulse">AI 正在串行生成 7 个阶段（约 8-12 分钟），进度实时更新，可离开页面</p>
            )}
          </form>

          {/* 历史记录 */}
          <div className="card p-4">
            <h3 className="sec-label !mb-2">历史记录（{projects.length}）</h3>
            <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
              {projects.length === 0 && (
                <p className="text-[11px] text-slate-600 py-4 text-center">暂无项目，从上方创建第一个吧</p>
              )}
              {projects.map(p => (
                <button
                  key={p.id}
                  onClick={() => handleSelect(p.id)}
                  className={`w-full text-left rounded-xl border px-3 py-2.5 transition-all ${
                    selected === p.id || (projects[0]?.id === p.id && selected === null)
                      ? 'border-astro-400/60 bg-astro-500/10'
                      : 'border-white/10 bg-white/[0.02] hover:border-white/25'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[13px] font-medium text-slate-200 truncate">{p.title}</p>
                    <span className={`text-[9px] shrink-0 px-1.5 py-0.5 rounded border ${
                      p.status === 'completed' ? 'text-aurora-300 border-aurora-400/40' : 'text-astro-300 border-astro-400/40'
                    }`}>
                      {p.status === 'completed' ? '已完成' : '进行中'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-0.5 truncate">{p.interest}</p>
                  <div className="flex items-center gap-1 mt-1.5">
                    {Object.keys(p.stages).map(s => {
                      const st = p.stages[s]?.status
                      const on = st === 'completed' || st === 'awaiting_review' || st === 'running'
                      return <span key={s} className={`w-3 h-1.5 rounded-full ${on ? (st === 'completed' ? 'bg-aurora-400' : 'bg-astro-400') : 'bg-white/10'}`} />
                    })}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 右：选中项目详情 */}
        <div className="card p-5">
          {!detail ? (
            <p className="text-xs text-slate-600 text-center py-16">创建项目后，这里将展示 7 阶段进度与产出物</p>
          ) : (
            <div className="space-y-5">
              {/* 项目头 + 操作 */}
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <h3 className="font-display text-lg font-bold text-white">{detail.title}</h3>
                  <p className="text-[11px] text-slate-500 mt-1">兴趣：{detail.interest}</p>
                  <p className="text-[10px] text-slate-600 mt-0.5">创建于 {detail.created_at?.slice(0, 19).replace('T', ' ')}</p>
                </div>
                <div className="flex gap-2 flex-wrap shrink-0">
                  {detail.status !== 'completed' && (
                    <button onClick={() => handleRunAll(detail.id)} disabled={generatingAll}
                      className="text-xs px-3 py-1.5 rounded-lg border border-astro-400/50 bg-astro-500/10 text-astro-300 hover:bg-astro-500/20 disabled:opacity-40 transition-all">
                      {generatingAll ? '⏳ 生成中…' : '🚀 一键生成全部'}
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

              {/* Research Pipeline 进度 */}
              <div className="border-t border-white/[0.06] pt-4">
                <ResearchPipeline stages={detail.stages} currentStage={detail.current_stage} />
              </div>

              {/* 7 阶段产出物摘要 */}
              <div className="space-y-2.5 border-t border-white/[0.06] pt-4">
                {Object.keys(detail.stages).map(s => {
                  const rec = detail.stages[s]
                  const meta = STATUS_META[rec?.status] ?? STATUS_META.pending
                  return (
                    <div key={s} className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="text-base">{STAGE_ICONS[s]}</span>
                          <span className="text-[13px] font-medium text-slate-200">{STAGE_NAMES[s]}</span>
                          {rec?.error && <span className="text-[10px] text-flare-400 truncate">{rec.error}</span>}
                        </div>
                        <span className={`text-[10px] shrink-0 px-2 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                      </div>
                      {rec?.output && (
                        <pre className="text-[9px] text-slate-500 whitespace-pre-wrap bg-black/20 rounded-lg p-2.5 mt-2 max-h-24 overflow-y-auto">
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
    </div>
  )
}
