/**
 * 云观星传 - 科研流程页面共享 UI 组件
 *
 * 7 个科研流程页面（选题孵化/文献综述/研究设计/方法推荐/数据分析/学术写作/同行评审）
 * 统一复用：阶段头部、评分条、运行/确认操作、产出物展示。
 */
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'

export interface StageInfo {
  stage: number
  icon: string
  title: string
  en: string
  description: string
}

/** 阶段页统一布局：头部 + 内容（进度条统一显示在主页科研工作台，子页不再重复） */
export function StageLayout({ info, children }: { info: StageInfo; children: ReactNode }) {
  return (
    <div className="space-y-6">
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
          {running ? 'AI 生成中…' : runLabel}
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
      {running && (
        <span className="text-[11px] text-astro-300 animate-pulse">
          AI 正在分析中…（生成质量优先，约需 1-3 分钟，请耐心等待，勿刷新页面）
        </span>
      )}
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

  return { projectId, status, rec, running, error, exec, approve, loadProject }
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

/* ═══════════ RAG + KG 双校验报告（产出物后置校验，见 src/workflow/engine.py） ═══════════ */

export interface VerificationItem {
  claim: string
  status: string            // verified / partial / unverified / conflicting
  confidence: number
  rag_evidence: string | null
  kg_match: string | null
  notes: string
}

export interface VerificationReport {
  summary: {
    total: number
    verified: number
    partial: number
    unverified: number
    conflicting: number
    avg_confidence: number
  }
  items: VerificationItem[]
}

const VERIFY_STATUS_META: Record<string, { label: string; cls: string }> = {
  verified: { label: '✓ 已验证', cls: 'text-aurora-300 border-aurora-400/50 bg-aurora-500/10' },
  partial: { label: '◐ 部分验证', cls: 'text-astro-300 border-astro-400/50 bg-astro-500/10' },
  unverified: { label: '○ 未验证', cls: 'text-slate-400 border-white/15 bg-white/[0.03]' },
  conflicting: { label: '⚠ 存在冲突', cls: 'text-flare-400 border-flare-400/50 bg-flare-500/10' },
}

/** RAG + KG 双校验报告面板（产出物附带 output.verification 时展示） */
export function VerificationPanel({ verification }: { verification: VerificationReport | null }) {
  if (!verification || !verification.summary || verification.summary.total === 0) return null
  const s = verification.summary
  const rate = s.total > 0 ? Math.round(((s.verified + s.partial) / s.total) * 100) : 0
  return (
    <div className="card p-4 border-aurora-400/20">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <h3 className="sec-label !mb-0">🛡️ RAG + KG 双校验</h3>
        <span className="text-[10px] text-slate-500">
          共 {s.total} 条断言 · 证据覆盖 {rate}% · 平均置信度 {s.avg_confidence}
        </span>
      </div>
      <div className="space-y-1.5">
        {verification.items.map((it, i) => {
          const m = VERIFY_STATUS_META[it.status] ?? VERIFY_STATUS_META.unverified
          return (
            <div key={i} className="flex items-start gap-2 rounded-lg bg-white/[0.03] border border-white/10 px-3 py-2">
              <span className={`text-[9px] shrink-0 px-1.5 py-0.5 rounded border ${m.cls}`}>{m.label}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-slate-300 leading-snug">{it.claim}</p>
                {(it.rag_evidence || it.kg_match) && (
                  <p className="text-[10px] text-slate-500 mt-0.5 leading-snug">
                    {it.rag_evidence && <>RAG 证据：{it.rag_evidence}</>}
                    {it.rag_evidence && it.kg_match && ' ｜ '}
                    {it.kg_match && <>KG 匹配：{it.kg_match}</>}
                  </p>
                )}
                {it.notes && <p className="text-[9px] text-slate-600 mt-0.5">{it.notes}</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
