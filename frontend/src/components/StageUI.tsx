/**
 * 云观星传 - 科研流程页面共享 UI 组件
 *
 * 7 个科研流程页面（选题孵化/文献综述/研究设计/方法推荐/数据分析/学术写作/同行评审）
 * 统一复用：阶段头部、评分条、运行/确认操作、产出物展示。
 */
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'
import ResearchPipeline from './ResearchPipeline'

export interface StageInfo {
  stage: number
  icon: string
  title: string
  en: string
  description: string
}

/** 阶段页统一布局：进度条 + 头部 + 内容 */
export function StageLayout({ info, children }: { info: StageInfo; children: ReactNode }) {
  const { currentProject } = useStore()
  return (
    <div className="space-y-6">
      <div className="card p-4">
        <ResearchPipeline
          stages={currentProject?.stages ?? null}
          currentStage={currentProject?.current_stage ?? 1}
          compact
        />
      </div>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">
            {info.icon} {info.title}
          </h2>
          <p className="text-xs text-slate-500 mt-1">{info.en} · {info.description}</p>
        </div>
        <span className="text-[9px] font-mono text-slate-600 tracking-widest">STAGE {info.stage}</span>
      </div>
      {children}
    </div>
  )
}

/** 0-100 评分条 */
export function ScoreBar({ label, value, color = 'bg-astro-400' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-slate-400 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="text-[11px] font-mono text-slate-300 w-7 text-right">{value}</span>
    </div>
  )
}

/** 状态徽章 */
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: '待开始', cls: 'text-slate-500 border-white/10' },
    running: { label: '运行中', cls: 'text-flare-300 border-flare-400/40 animate-pulse' },
    awaiting_review: { label: '待确认', cls: 'text-astro-300 border-astro-400/50' },
    completed: { label: '已完成', cls: 'text-aurora-300 border-aurora-400/50' },
    failed: { label: '失败', cls: 'text-flare-400 border-flare-400/60' },
  }
  const m = map[status] ?? map.pending
  return <span className={`text-[10px] shrink-0 px-2 py-0.5 rounded border ${m.cls}`}>{m.label}</span>
}

/** 运行/确认操作区 */
export function StageActions({
  status, onRun, onApprove, running, error, runLabel = '开始本阶段',
}: {
  status: string
  onRun: () => void
  onApprove: () => void
  running: boolean
  error: string
  runLabel?: string
}) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {status === 'pending' || status === 'failed' ? (
        <button onClick={onRun} disabled={running}
          className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
          {running ? '运行中…' : runLabel}
        </button>
      ) : status === 'awaiting_review' ? (
        <button onClick={onApprove} className="btn-primary text-xs">
          确认产出，进入下一阶段 →
        </button>
      ) : status === 'completed' ? (
        <button onClick={onRun} disabled={running} className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
          重新运行
        </button>
      ) : null}
      {error && <span className="text-[11px] text-flare-400">{error}</span>}
    </div>
  )
}

/** 无项目引导 */
export function NoProjectHint() {
  return (
    <div className="card p-8 text-center text-sm text-slate-500">
      暂无项目上下文 —— 请先到 <Link to="/projects" className="text-astro-400 hover:text-astro-300">我的项目</Link> 创建研究项目
    </div>
  )
}

/** 使用当前项目执行阶段的 hook */
export function useStageExec(stage: number) {
  const { currentProject, loadProject, runStage, approveStage } = useStore()
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const projectId = currentProject?.id ?? null
  const rec = currentProject?.stages ? currentProject.stages[String(stage)] : null
  const status = rec?.status ?? 'pending'

  const exec = async (inputs: Record<string, unknown>) => {
    if (!projectId) return
    setRunning(true)
    setError('')
    try {
      await runStage(projectId, stage, inputs)
      await loadProject(projectId)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '执行失败'
      setError(msg.includes('未解锁') ? '本阶段尚未解锁，请先完成上一阶段' : msg)
    } finally {
      setRunning(false)
    }
  }

  const approve = async () => {
    if (!projectId) return
    setRunning(true)
    setError('')
    try {
      await approveStage(projectId, stage)
      await loadProject(projectId)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '确认失败')
    } finally {
      setRunning(false)
    }
  }

  return { projectId, status, rec, running, error, exec, approve }
}

/** 产出物 JSON 展示 */
export function OutputView({ output }: { output: Record<string, unknown> | null }) {
  if (!output) return <p className="text-[11px] text-slate-600">暂无产出物</p>
  return (
    <pre className="text-[10px] text-slate-400 whitespace-pre-wrap bg-black/20 rounded-lg p-3 max-h-64 overflow-y-auto">
      {JSON.stringify(output, null, 2)}
    </pre>
  )
}
