/**
 * 云观星传 - Research Pipeline 科研进度时间轴
 *
 * 首页核心组件：9 个科研流程节点（研究灵感 → 选题 → 文献 → Gap → RQ → 方法 → 数据 → 写作 → 评审），
 * 映射后端 7 个工作流阶段。用户点击任意节点进入对应科研流程页面，
 * 未解锁节点禁用 —— 替代传统左侧菜单切换，呈现科研工作流平台形态。
 */
import { Link } from 'react-router-dom'
import type { WorkflowStageRecord } from '../api'

export interface PipelineNode {
  key: string
  label: string
  en: string
  icon: string
  stage: number | null   // 对应后端阶段（null = 研究灵感，无后端阶段）
  route: string
}

export const PIPELINE_NODES: PipelineNode[] = [
  { key: 'inspiration', label: '研究灵感', en: 'IDEATION', icon: '✦', stage: null, route: '/inspiration' },
  { key: 'topic', label: '选题孵化', en: 'TOPIC', icon: '💡', stage: 1, route: '/inspiration' },
  { key: 'literature', label: '文献综述', en: 'LITERATURE', icon: '📚', stage: 2, route: '/literature' },
  { key: 'gap', label: 'Gap 识别', en: 'GAP', icon: '🔍', stage: 2, route: '/literature' },
  { key: 'rq', label: 'RQ 设计', en: 'RESEARCH Q', icon: '🎯', stage: 3, route: '/design' },
  { key: 'method', label: '方法推荐', en: 'METHOD', icon: '🧪', stage: 4, route: '/method' },
  { key: 'data', label: '数据分析', en: 'ANALYSIS', icon: '📊', stage: 5, route: '/data-analysis' },
  { key: 'writing', label: '学术写作', en: 'WRITING', icon: '✍️', stage: 6, route: '/writing' },
  { key: 'review', label: '同行评审', en: 'REVIEW', icon: '👨‍⚖️', stage: 7, route: '/review' },
]

export type NodeState = 'done' | 'active' | 'locked' | 'running'

/** 计算节点状态 */
export function nodeState(node: PipelineNode, stages: Record<string, WorkflowStageRecord> | null | undefined, currentStage: number): NodeState {
  if (node.stage === null) return 'active' // 研究灵感始终可进入
  if (!stages) return 'locked'
  const rec = stages[String(node.stage)]
  if (rec && rec.status === 'completed') return 'done'
  if (node.stage < currentStage) return 'done'     // 已解锁且已过（重跑场景）
  if (node.stage === currentStage) {
    if (rec && rec.status === 'running') return 'running'
    return 'active'                                 // awaiting_review / pending / failed 均可操作
  }
  return 'locked'
}

interface ResearchPipelineProps {
  stages?: Record<string, WorkflowStageRecord> | null
  currentStage?: number
  compact?: boolean
}

export default function ResearchPipeline({ stages, currentStage = 1, compact = false }: ResearchPipelineProps) {
  return (
    <div className={`w-full ${compact ? '' : 'py-2'}`}>
      {/* 节点行 */}
      <div className="flex items-start justify-between gap-1">
        {PIPELINE_NODES.map((node, idx) => {
          const state = nodeState(node, stages, currentStage)
          const locked = state === 'locked'
          const nodeCls = [
            'flex flex-col items-center gap-1.5 w-[64px] shrink-0 transition-all',
            locked ? 'opacity-35 cursor-not-allowed' : 'cursor-pointer hover:-translate-y-0.5',
          ].join(' ')

          const circleCls = [
            'relative w-10 h-10 rounded-full flex items-center justify-center text-base border transition-all',
            state === 'done' && 'bg-aurora-500/20 border-aurora-400/70 text-aurora-300 shadow-[0_0_14px_rgba(52,211,153,0.35)]',
            state === 'active' && 'bg-astro-500/20 border-astro-400/80 text-astro-300 shadow-[0_0_14px_rgba(12,184,232,0.4)]',
            state === 'running' && 'bg-flare-500/20 border-flare-400/80 text-flare-300 animate-pulse',
            state === 'locked' && 'bg-white/[0.03] border-white/10 text-slate-600',
          ].join(' ')

          const body = (
            <>
              <div className={circleCls}>
                {state === 'done' ? <span className="text-sm font-bold">✓</span> : <span>{node.icon}</span>}
                {state === 'running' && <span className="absolute -inset-1 rounded-full border border-flare-400/50 animate-ping" />}
              </div>
              <span className={`text-[11px] font-medium leading-tight text-center ${locked ? 'text-slate-600' : state === 'done' ? 'text-aurora-300' : 'text-slate-200'}`}>
                {node.label}
              </span>
              <span className="text-[7px] font-mono tracking-widest text-slate-600">{node.en}</span>
            </>
          )

          return (
            <div key={node.key} className="flex items-start flex-1 last:flex-none">
              {locked ? (
                <div className={nodeCls}>{body}</div>
              ) : (
                <Link to={node.route} className={nodeCls}>{body}</Link>
              )}
              {idx < PIPELINE_NODES.length - 1 && (
                <div className={`flex-1 h-[2px] mt-5 mx-1 rounded ${state === 'done' ? 'bg-aurora-500/50' : 'bg-white/[0.07]'}`} />
              )}
            </div>
          )
        })}
      </div>
      {/* 图例 */}
      <div className="flex items-center justify-center gap-5 mt-4 text-[10px] text-slate-500">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-aurora-400" /> 已完成</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-astro-400" /> 当前阶段</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-white/20" /> 未解锁</span>
      </div>
    </div>
  )
}
