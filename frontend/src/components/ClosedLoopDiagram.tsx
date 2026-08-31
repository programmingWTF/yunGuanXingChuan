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

/** 回流虚线：评审/诊断后按问题路由回改（与后端 auto_iterate 的 target_stage 路由一致）
 *  评审 → 研究设计（修订 RQ/假设）｜评审 → 文献综述（补检索）｜
 *  评审 → 学术写作（按意见修订）｜数据分析 → 方法推荐（按诊断调整方法） */
const BACKFLOW = [
  { from: 6, to: 2, label: '按评审意见修改设计' },
  { from: 6, to: 1, label: '补充文献检索' },
  { from: 6, to: 5, label: '按评审意见修订写作' },
  { from: 4, to: 3, label: '按诊断调整方法' },
]

const W = 640
const H = 240
const CX = W / 2
const CY = 112
const R = 92

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
  /** 自动迭代进行中（后端 status=iterating）：回流虚线脉冲动画 + 强调 */
  iterating?: boolean
}

export default function ClosedLoopDiagram({ stages, currentStage = 1, iterationsCount = 0, iterating = false }: ClosedLoopDiagramProps) {
  const hasProject = !!stages && Object.keys(stages).length > 0
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-0">
        <h3 className="sec-label !mb-0">🔄 闭环迭代流程</h3>
        <div className="flex items-center gap-3 flex-wrap">
          {iterationsCount > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 font-medium">
              🔄 本项目已迭代 {iterationsCount} 轮
            </span>
          )}
          <Link to="/data-analysis"
            className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all font-medium">
            🤖 自动迭代 →
          </Link>
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
          const pad = 21
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

        {/* 回流虚线（评审→设计/文献/写作；数据分析→方法；与后端 target_stage 路由一致） */}
        {BACKFLOW.map(({ from, to, label }, i) => {
          const a = nodePos(from)
          const b = nodePos(to)
          // 回流弧线走环内空白区（中轴附近），控制点分档错开避免多条线重叠
          // 端点精确落在两节点圆边缘（沿 a→b 方向投影），箭头保证指到目标圆上
          const dx = b.x - a.x, dy = b.y - a.y
          const len = Math.hypot(dx, dy) || 1
          const ux = dx / len, uy = dy / len
          const rN = 15
          const x1 = a.x + ux * (rN + 2), y1 = a.y + uy * (rN + 2)
          const x2 = b.x - ux * (rN + 8), y2 = b.y - uy * (rN + 8)
          // 控制点取中点并向环心方向偏移；多条回流线按索引分档上下错开不重叠
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
          const cxq = mx + (CX - mx) * 0.55
          const cyq = my + (CY - my) * 0.65 + (i - 1.5) * 8
          const lit = iterationsCount > 0 || iterating
          return (
            <g key={i}>
              <path d={`M ${x1} ${y1} Q ${cxq} ${cyq} ${x2} ${y2}`}
                fill="none"
                stroke={lit ? 'rgba(217,119,6,.7)' : 'rgba(217,119,6,.3)'}
                strokeWidth={lit ? 1.6 : 1} strokeDasharray="5 4"
                className={iterating ? 'gx-iter-pulse' : undefined}
                markerEnd="url(#cl-arrow-dash)" />
              <text x={cxq} y={cyq - 3} textAnchor="middle" fontSize="6.5"
                fill={lit ? 'rgba(180,83,9,.85)' : 'rgba(180,83,9,.45)'}
                style={{ pointerEvents: 'none' }} fontFamily="inherit">{label}</text>
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
              <circle cx={x} cy={y} r="15" fill={style.fill} stroke={style.ring} strokeWidth="1.2" />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize="11" style={{ pointerEvents: 'none' }}>{n.icon}</text>
              {st === 'running' && <circle cx={x} cy={y} r="19" fill="none" stroke="rgba(245,158,11,.5)" strokeWidth="1.3" className="animate-pulse" />}
              {/* 状态小圆点（右上角） */}
              <circle cx={x + 13} cy={y - 13} r="3.5" fill={style.color} stroke="white" strokeWidth="1" />
              <text x={x} y={y + 29} textAnchor="middle" fontSize="9" className="fill-slate-500">{n.label}</text>
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
      <div className="flex items-center justify-center gap-3 mt-1 text-[9.5px] text-slate-500 flex-wrap">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 已完成</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-indigo-400" /> 当前阶段（可点击）</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> 运行中</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-300" /> 未解锁</span>
        <span className="text-amber-500">⤺ 虚线 = 自动闭环回流（改设计 / 补文献 / 修写作 / 调方法）</span>
      </div>
      {iterating && (
        <p className="text-center text-[9.5px] text-amber-600 mt-1 animate-pulse">🔄 自动迭代进行中：分析 → 诊断 → 按问题修订 → 重跑 → 评审确认</p>
      )}
      <style>{`.gx-iter-pulse { animation: gxDashPulse 1.6s ease-in-out infinite; } @keyframes gxDashPulse { 0%,100% { stroke-dashoffset: 0; opacity: .75; } 50% { stroke-dashoffset: -18; opacity: 1; } }`}</style>
    </div>
  )
}
