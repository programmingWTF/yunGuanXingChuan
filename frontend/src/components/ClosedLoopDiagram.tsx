/**
 * 云观星传 - 闭环迭代流程示意图（issue #130，交互版）
 *
 * 首页展示：7 阶段环形闭环 —— 选题孵化 → 文献综述 → 研究设计 → 方法推荐 →
 * 数据分析 → 学术写作 → 同行评审 →（虚线回流到 文献综述 / 研究设计）。
 *
 * 交互（桂鱼 2026-08-30 反馈）：
 * - 节点可点击 → 直达对应阶段页面（未解锁置灰禁用）
 * - 每个节点按项目真实状态着色 + 角标（已完成/可操作/运行中/未解锁）
 * - 项目已有迭代记录时，回流虚线加亮并标注「已迭代 N 轮」
 */
import { Link } from 'react-router-dom'
import type { WorkflowStageRecord } from '../api'

const NODES = [
  { label: '选题孵化', icon: '💡', stage: 1, route: '/inspiration' },
  { label: '文献综述', icon: '📚', stage: 2, route: '/literature' },
  { label: '研究设计', icon: '🎯', stage: 3, route: '/design' },
  { label: '方法推荐', icon: '🧪', stage: 4, route: '/method' },
  { label: '数据分析', icon: '📊', stage: 5, route: '/data-analysis' },
  { label: '学术写作', icon: '✍️', stage: 6, route: '/writing' },
  { label: '同行评审', icon: '👨‍⚖️', stage: 7, route: '/review' },
]

/** 回流虚线：同行评审 → 研究设计（主回流），同行评审 → 文献综述（分支回流） */
const BACKFLOW = [
  { from: 6, to: 2, label: '按评审意见修改设计' },
  { from: 6, to: 1, label: '补充文献检索' },
]

const W = 900
const H = 360
const CX = W / 2
const CY = 158
const R = 132

/** 节点在环上的坐标（第 0 个在正上方，顺时针排布） */
function nodePos(i: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + (i * 2 * Math.PI) / NODES.length
  return { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) * 0.92 }
}

/** 节点状态（与 ResearchPipeline 同口径）：done/active/running/locked */
function stageState(stage: number, stages: Record<string, WorkflowStageRecord> | null | undefined, currentStage: number): 'done' | 'active' | 'running' | 'locked' {
  if (!stages) return 'locked'
  const rec = stages[String(stage)]
  if (rec && rec.status === 'completed') return 'done'
  if (stage < currentStage) return 'done'
  if (stage === currentStage) return rec && rec.status === 'running' ? 'running' : 'active'
  return 'locked'
}

const STATE_STYLE: Record<string, { ring: string; fill: string; badge: string; color: string }> = {
  done: { ring: 'rgba(16,185,129,.7)', fill: '#ecfdf5', badge: '✓ 已完成', color: '#059669' },
  active: { ring: 'rgba(99,102,241,.75)', fill: '#eef2ff', badge: '▶ 可操作', color: '#4f46e5' },
  running: { ring: 'rgba(245,158,11,.8)', fill: '#fffbeb', badge: '⏳ 运行中', color: '#d97706' },
  locked: { ring: 'rgba(148,163,184,.45)', fill: '#f8fafc', badge: '未解锁', color: '#94a3b8' },
}

interface ClosedLoopDiagramProps {
  stages?: Record<string, WorkflowStageRecord> | null
  currentStage?: number
  /** 已完成迭代轮数（>0 时回流虚线加亮并标注轮数） */
  iterationsCount?: number
}

export default function ClosedLoopDiagram({ stages, currentStage = 1, iterationsCount = 0 }: ClosedLoopDiagramProps) {
  const hasProject = !!stages && Object.keys(stages).length > 0
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h3 className="sec-label !mb-0">🔄 闭环迭代流程</h3>
        <div className="flex items-center gap-3 flex-wrap">
          {iterationsCount > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-medium">
              🔄 本项目已迭代 {iterationsCount} 轮
            </span>
          )}
          <span className="text-[10px] text-slate-400">{hasProject ? '点击节点直达对应阶段' : '创建项目后此处展示实时进度'}</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="闭环迭代流程示意图">
        <defs>
          <marker id="cl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(99,102,241,.55)" />
          </marker>
          <marker id="cl-arrow-dash" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(217,119,6,.7)" />
          </marker>
        </defs>

        {/* 环向实线箭头（相邻节点，随起点状态着色） */}
        {NODES.map((_, i) => {
          const a = nodePos(i)
          const b = nodePos((i + 1) % NODES.length)
          const dx = b.x - a.x
          const dy = b.y - a.y
          const len = Math.hypot(dx, dy) || 1
          const pad = 34
          const x1 = a.x + (dx / len) * pad
          const y1 = a.y + (dy / len) * pad
          const x2 = b.x - (dx / len) * (pad + 8)
          const y2 = b.y - (dy / len) * (pad + 8)
          const st = stageState(NODES[i].stage, stages, currentStage)
          const stroke = st === 'done' ? 'rgba(16,185,129,.55)' : st === 'running' ? 'rgba(245,158,11,.55)' : st === 'locked' ? 'rgba(148,163,184,.4)' : 'rgba(99,102,241,.5)'
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={stroke} strokeWidth="2" markerEnd="url(#cl-arrow)" />
          )
        })}

        {/* 回流虚线（同行评审 → 研究设计 / 文献综述） */}
        {BACKFLOW.map(({ from, to, label }, i) => {
          const a = nodePos(from)
          const b = nodePos(to)
          const midX = (a.x + b.x) / 2
          const midY = Math.max(a.y, b.y) + (i === 0 ? 128 : 96)
          const lit = iterationsCount > 0
          // 标签固定画在弧线最低点下方，两端对齐避让节点文字
          const lblY = H - (i === 0 ? 64 : 44)
          return (
            <g key={i}>
              <path d={`M ${a.x} ${a.y + 28} Q ${midX} ${midY} ${b.x} ${b.y - 28}`}
                fill="none"
                stroke={lit ? 'rgba(217,119,6,.75)' : 'rgba(217,119,6,.35)'}
                strokeWidth={i === 0 ? 2.2 : 1.6} strokeDasharray="7 5"
                markerEnd="url(#cl-arrow-dash)" />
              <text x={midX} y={lblY} textAnchor="middle" fontSize="10.5"
                className="fill-amber-600" opacity={lit ? 1 : 0.75}>
                {label}{lit && i === 0 ? `（已迭代 ${iterationsCount} 轮）` : ''}
              </text>
            </g>
          )
        })}

        {/* 节点（可点击跳转；状态着色 + 角标） */}
        {NODES.map((n, i) => {
          const { x, y } = nodePos(i)
          const st = stageState(n.stage, stages, currentStage)
          const style = STATE_STYLE[st]
          const locked = st === 'locked'
          const circle = (
            <>
              <circle cx={x} cy={y} r="24" fill={style.fill} stroke={style.ring} strokeWidth="2" />
              <text x={x} y={y + 6} textAnchor="middle" fontSize="16" style={{ pointerEvents: 'none' }}>{n.icon}</text>
              {st === 'running' && <circle cx={x} cy={y} r="30" fill="none" stroke="rgba(245,158,11,.5)" strokeWidth="2" className="animate-pulse" />}
              {/* 状态小圆点（右上角），文字角标简化——降低与相邻节点标签的拥挤 */}
              <circle cx={x + 19} cy={y - 19} r="5" fill={style.color} stroke="white" strokeWidth="1.5" />
              <text x={x} y={y + 43} textAnchor="middle" fontSize="11.5" className="fill-slate-600">{n.label}</text>
            </>
          )
          if (locked) {
            return <g key={n.label} opacity="0.55" style={{ cursor: 'not-allowed' }}>{circle}</g>
          }
          return (
            <Link key={n.label} to={n.route} style={{ cursor: 'pointer' }} aria-label={`进入${n.label}`}>
              {circle}
            </Link>
          )
        })}
      </svg>

      {/* 状态图例 */}
      <div className="flex items-center justify-center gap-4 mt-1 text-[10px] text-slate-500 flex-wrap">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-400" /> 已完成</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-indigo-400" /> 当前阶段（可点击进入）</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" /> 运行中</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-300" /> 未解锁</span>
      </div>
    </div>
  )
}
