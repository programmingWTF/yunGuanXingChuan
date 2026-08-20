/**
 * 云观星传 V3.0 - 科研流程页面共享 UI 组件（他山世界学术风 · 浅色）
 *
 * 7 个科研流程页面（选题孵化/文献综述/研究设计/方法推荐/数据分析/学术写作/同行评审）
 * 统一复用：阶段头部、评分条、运行/确认操作、产出物展示。
 *
 * 「重新运行」属覆盖型危险操作（后端 clear_output 清空旧产出物），
 * 点击前弹二次确认（ConfirmDialog），避免误触覆盖已确认产出物（issue #66）。
 */
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import { useAuth } from '../auth'
import ConfirmDialog from './ConfirmDialog'
import SearchSources from './SearchSources'
import type { SearchSource } from '../api'

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
          <h2 className="font-display text-2xl font-semibold text-slate-900 tracking-tight">
            {info.icon} {info.title}
          </h2>
          <p className="text-xs text-slate-500 mt-1.5">{info.en} · {info.description}</p>
        </div>
        <span className="text-[10px] font-sans text-slate-400 tracking-[0.22em] uppercase">Stage {info.stage}</span>
      </div>
      {children}
    </div>
  )
}

/** 0-100 评分条 */
export function ScoreBar({ label, value, color = 'bg-sky-500' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-slate-500 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="text-[11px] font-mono text-slate-600 w-7 text-right">{value}</span>
    </div>
  )
}

/** 状态徽章（胶囊，他山 8.6） */
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending: { label: '待开始', cls: 'text-slate-500 bg-slate-50 border-slate-200' },
    running: { label: '运行中', cls: 'text-amber-600 bg-amber-50 border-amber-200 animate-pulse' },
    awaiting_review: { label: '待确认', cls: 'text-sky-700 bg-sky-50 border-sky-200' },
    completed: { label: '已完成', cls: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    failed: { label: '失败', cls: 'text-red-600 bg-red-50 border-red-200' },
  }
  const m = map[status] ?? map.pending
  return <span className={`text-[10px] shrink-0 px-2.5 py-1 rounded-full border font-medium ${m.cls}`}>{m.label}</span>
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
  // 重新运行属覆盖型危险操作：仅当该阶段已有已确认/产出物待覆盖时才需二次确认
  const [confirming, setConfirming] = useState(false)
  const { user } = useAuth()
  const navigate = useNavigate()
  const isRerun = status === 'completed'
  const handleRunClick = () => {
    if (isRerun) setConfirming(true) // 先确认再执行，避免误触清空旧产出物
    else onRun()
  }
  // 未登录：主界面可浏览，运行需登录
  if (!user) {
    return (
      <button onClick={() => navigate('/login')}
        className="btn-primary text-xs">
        🔑 登录后使用
      </button>
    )
  }
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {status === 'pending' || status === 'failed' ? (
        <button onClick={handleRunClick} disabled={running}
          className="btn-primary text-xs disabled:opacity-45 disabled:cursor-not-allowed">
          {running ? 'AI 生成中…' : runLabel}
        </button>
      ) : status === 'awaiting_review' ? (
        <button onClick={onApprove} className="btn-primary text-xs">
          确认产出，进入下一阶段 →
        </button>
      ) : status === 'completed' ? (
        <button onClick={handleRunClick} disabled={running} className="text-xs px-3.5 py-2 rounded-btn border border-slate-200 text-slate-600 hover:border-sky-300 hover:text-sky-700 hover:bg-sky-50 disabled:opacity-45 transition-all">
          重新运行
        </button>
      ) : null}
      {running && (
        <span className="text-[11px] text-amber-600 animate-pulse">
          AI 正在分析中…（生成质量优先，约需 1-3 分钟，请耐心等待，勿刷新页面）
        </span>
      )}
      {error && <span className="text-[11px] text-red-600">{error}</span>}
      {/* 二次确认：确认后才会 onRun，后端会 clear_output 清空旧产出物 */}
      <ConfirmDialog
        open={confirming}
        title="确认重新运行？"
        description={
          <>
            重新运行将<strong className="text-red-600 font-medium">清空并覆盖当前已确认的产出物</strong>
            ，此操作<strong className="text-red-600 font-medium">不可撤销</strong>。已确认请继续，否则点「取消」保留现有产出。
          </>
        }
        confirmText="重新运行"
        onCancel={() => setConfirming(false)}
        onConfirm={() => { setConfirming(false); onRun() }}
      />
    </div>
  )
}

/** 无项目引导 */
export function NoProjectHint() {
  return (
    <div className="card p-12 text-center">
      <div className="text-4xl mb-4 opacity-30">🔭</div>
      <p className="text-sm text-slate-500 mb-2">暂无项目上下文</p>
      <p className="text-xs text-slate-400">
        请先到 <Link to="/" className="text-sky-600 hover:text-sky-700 font-medium underline underline-offset-2">科研工作台</Link> 创建研究项目
      </p>
    </div>
  )
}

/** 使用当前项目执行阶段的 hook */
export function useStageExec(stage: number) {
  const { currentProject, loadProject, runStage, approveStage } = useStore()
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  // 「重新生成本阶段」二次确认（覆盖型危险操作，issue #66）
  const [confirming, setConfirming] = useState(false)

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

  // 打开/关闭「重新生成本阶段」二次确认弹窗
  // 仅当已有产出物（completed / awaiting_review）时才需确认覆盖；其余首次生成直接执行
  const hasProduced = status === 'completed' || status === 'awaiting_review'
  const confirmRerun = () => {
    if (hasProduced) setConfirming(true)
    else void exec({})
  }
  const cancelRerun = () => setConfirming(false)
  const doRerun = () => { setConfirming(false); void exec({}) }

  // 确认弹窗元素：子页直接 {rerunConfirmEl} 渲染即可
  const rerunConfirmEl = (
    <ConfirmDialog
      open={confirming}
      title="确认重新运行本阶段？"
      description={
        <>
          重新运行将<strong className="text-red-600 font-medium">清空并覆盖该阶段当前产出物</strong>
          ，此操作<strong className="text-red-600 font-medium">不可撤销</strong>。确认将覆盖，否则点「取消」保留现有产出。
        </>
      }
      confirmText="重新运行"
      cancelText="取消"
      onCancel={cancelRerun}
      onConfirm={doRerun}
    />
  )

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

  return { projectId, status, rec, running, error, exec, approve, loadProject, confirmRerun, rerunConfirmEl }
}

/** 产出物 JSON 展示 */
export function OutputView({ output }: { output: Record<string, unknown> | null }) {
  if (!output) return <p className="text-[11px] text-slate-400">暂无产出物</p>
  return (
    <div>
      <StageSources output={output} />
      <pre className="text-[10px] text-slate-500 whitespace-pre-wrap bg-slate-50 border border-slate-100 rounded-lg p-3 max-h-64 overflow-y-auto">
        {JSON.stringify(output, null, 2)}
      </pre>
    </div>
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
  verified: { label: '✓ 已验证', cls: 'text-emerald-700 border-emerald-200 bg-emerald-50' },
  partial: { label: '◐ 部分验证', cls: 'text-sky-700 border-sky-200 bg-sky-50' },
  unverified: { label: '○ 未验证', cls: 'text-slate-500 border-slate-200 bg-slate-50' },
  conflicting: { label: '⚠ 存在冲突', cls: 'text-red-700 border-red-200 bg-red-50' },
}

/** RAG + KG 双校验报告面板（产出物附带 output.verification 时展示） */
export function VerificationPanel({ verification }: { verification: VerificationReport | null }) {
  if (!verification || !verification.summary || verification.summary.total === 0) return null
  const s = verification.summary
  const rate = s.total > 0 ? Math.round(((s.verified + s.partial) / s.total) * 100) : 0
  return (
    <div className="card p-5 !border-emerald-200/70">
      <div className="flex items-center justify-between mb-2.5 flex-wrap gap-2">
        <h3 className="sec-label !mb-0">RAG + KG 双校验</h3>
        <span className="text-[10px] font-sans text-slate-500">
          共 {s.total} 条断言 · 证据覆盖 {rate}% · 平均置信度 {s.avg_confidence}
        </span>
      </div>
      <div className="space-y-1.5">
        {verification.items.map((it, i) => {
          const m = VERIFY_STATUS_META[it.status] ?? VERIFY_STATUS_META.unverified
          return (
            <div key={i} className="flex items-start gap-2.5 rounded-xl bg-slate-50/70 border border-slate-100 px-3.5 py-2.5">
              <span className={`text-[9px] shrink-0 px-2 py-0.5 rounded-full border font-medium ${m.cls}`}>{m.label}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-slate-600 leading-snug">{it.claim}</p>
                {(it.rag_evidence || it.kg_match) && (
                  <p className="text-[10px] text-slate-400 mt-0.5 leading-snug">
                    {it.rag_evidence && <>RAG 证据：{it.rag_evidence}</>}
                    {it.rag_evidence && it.kg_match && ' ｜ '}
                    {it.kg_match && <>KG 匹配：{it.kg_match}</>}
                  </p>
                )}
                {it.notes && <p className="text-[9px] text-slate-400 mt-0.5">{it.notes}</p>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * 阶段页联网搜索来源面板（Issue #98）。
 *
 * 从阶段产出物 rec.output.search_sources 读取结构化来源并渲染为可点击链接。
 * 产出物无来源时渲染 null，不占版面。
 */
export function StageSources({ output }: { output: Record<string, unknown> | null | undefined }) {
  if (!output) return null
  const sources = (output as { search_sources?: SearchSource[] | null }).search_sources
  if (!Array.isArray(sources) || sources.length === 0) return null
  return (
    <div className="mt-4">
      <SearchSources sources={sources} />
    </div>
  )
}