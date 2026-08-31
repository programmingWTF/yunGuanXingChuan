/**
 * 云观星传 - 闭环迭代流程示意图（issue #130，交互版 v3 精准几何重构）
 *
 * v3（2026-09-01 桂鱼反馈：桌面端过大 + 箭头错乱 → 彻底重做几何）：
 * - 正圆等距布局（去掉椭圆压扁），节点均分 360°/7，坐标数学精确
 * - 环向箭头：沿相邻圆心连线方向，端点精确投影到两节点圆边缘
 * - 回流线：每条走独立通道（环内/环外/短弧分档），控制点=中点沿法向偏移，
 *   不交叉不压节点；标签白底防压线
 * - SVG 限制 max-width 居中显示，桌面端不再被撑到巨大
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

/** 回流虚线（stage 号）：与后端 auto_iterate 的 target_stage 路由语义一致 */
type BFlow = { from: number; to: number; label: string; chan: 'inner' | 'outer' | 'short' }
const BACKFLOW: BFlow[] = [
  { from: 7, to: 3, label: '按评审意见修改设计', chan: 'inner' },  // 评审→设计（环内长弧）
  { from: 7, to: 2, label: '补充文献检索', chan: 'outer' },       // 评审→文献（环外弧）
  { from: 7, to: 6, label: '按评审意见修订写作', chan: 'short' }, // 评审→写作（相邻短弧）
  { from: 5, to: 4, label: '按诊断调整方法', chan: 'short' },     // 分析→方法（相邻短弧）
]

const W = 640
const H = 300
const CX = W / 2
const CY = 148
const R = 102        // 节点环半径
const rN = 16        // 节点圆半径
const N = NODES.length

/** 节点中心坐标：正圆均分，第 0 个正上方，顺时针 */
function nodePos(i: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + (i * 2 * Math.PI) / N
  return { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) }
}

/** 由 stage 号取节点索引（stage 1..7 → 0..6） */
const idxOf = (stage: number) => (stage - 1 + N) % N

/** 两节点间的弦向量 */
function chord(a: { x: number; y: number }, b: { x: number; y: number }) {
  const dx = b.x - a.x, dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  return { dx, dy, len, ux: dx / len, uy: dy / len }
}

/** 阶段状态（与 ResearchPipeline 同口径） */
function stageState(stage: number, stages: Record<string, WorkflowStageRecord> | null | undefined, currentStage: number): 'done' | 'active' | 'running' | 'locked' {
  if (!stages) return 'locked'
  const rec = stages[String(stage)]
  if (rec && rec.status === 'completed') return 'done'
  if (stage < currentStage) return 'done'
  if (stage === currentStage) return rec && rec.status === 'running' ? 'running' : 'active'
  return 'locked'
}

const STATE_STYLE: Record<string, { ring: string; fill: string; color: string }> = {
  done:    { ring: 'rgba(16,185,129,.7)', fill: '#ecfdf5', color: '#059669' },
  active:  { ring: 'rgba(99,102,241,.75)', fill: '#eef2ff', color: '#4f46e5' },
  running: { ring: 'rgba(245,158,11,.8)', fill: '#fffbeb', color: '#d97706' },
  locked:  { ring: 'rgba(148,163,184,.45)', fill: '#f8fafc', color: '#94a3b8' },
}

interface ClosedLoopDiagramProps {
  stages?: Record<string, WorkflowStageRecord> | null
  currentStage?: number
  iterationsCount?: number
  iterating?: boolean
}

export default function ClosedLoopDiagram({ stages, currentStage = 1, iterationsCount = 0, iterating = false }: ClosedLoopDiagramProps) {
  const hasProject = !!stages && Object.keys(stages).length > 0
  const lit = iterationsCount > 0 || iterating
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
      {/* 尺寸根治：max-w 限制 + 居中，桌面端不再被卡片宽度撑大 */}
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="闭环迭代流程示意图"
        className="w-full max-w-[580px] mx-auto block">
        <defs>
          <marker id="cl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(99,102,241,.55)" />
          </marker>
          <marker id="cl-arrow-dash" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(217,119,6,.7)" />
          </marker>
        </defs>

        {/* ── 环向实线箭头（相邻节点，端点=沿圆心连线投影到圆边缘） */}
        {NODES.map((n, i) => {
          const a = nodePos(i)
          const b = nodePos((i + 1) % N)
          const { ux, uy } = chord(a, b)
          const x1 = a.x + ux * (rN + 2)
          const y1 = a.y + uy * (rN + 2)
          const x2 = b.x - ux * (rN + 7)
          const y2 = b.y - uy * (rN + 7)
          const st = stageState(n.stage, stages, currentStage)
          const stroke = st === 'done' ? 'rgba(16,185,129,.55)' : st === 'running' ? 'rgba(245,158,11,.55)' : st === 'locked' ? 'rgba(148,163,184,.4)' : 'rgba(99,102,241,.5)'
          return (
            <line key={`fwd${i}`} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={stroke} strokeWidth="1.8" markerEnd="url(#cl-arrow)" />
          )
        })}

        {/* ── 回流虚线（每条独立通道，不重叠；端点精确投影到圆边缘） */}
        {BACKFLOW.map(({ from, to, label, chan }, i) => {
          const a = nodePos(idxOf(from))
          const b = nodePos(idxOf(to))
          const { len, ux, uy } = chord(a, b)
          // 端点：沿弦方向投影到两节点圆边缘（起点留 2px 间隙，终点留箭头余量 7px）
          const x1 = a.x + ux * (rN + 2), y1 = a.y + uy * (rN + 2)
          const x2 = b.x - ux * (rN + 7), y2 = b.y - uy * (rN + 7)
          // 控制点：中点 + 法向偏移，按通道取偏移量（环内负/环外正/短弧小偏移）
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
          const nx = -uy, ny = ux   // 法向（旋转 90°）
          const off = chan === 'inner' ? -len * 0.38 : chan === 'outer' ? len * 0.55 : len * 0.28
          const cxq = mx + nx * off, cyq = my + ny * off
          return (
            <g key={`bw${i}`}>
              <path d={`M ${x1} ${y1} Q ${cxq} ${cyq} ${x2} ${y2}`}
                fill="none"
                stroke={lit ? 'rgba(217,119,6,.7)' : 'rgba(217,119,6,.3)'}
                strokeWidth={lit ? 1.6 : 1} strokeDasharray="5 4"
                className={iterating ? 'gx-iter-pulse' : undefined}
                markerEnd="url(#cl-arrow-dash)" />
              <text x={cxq} y={cyq - 4} textAnchor="middle" fontSize="7"
                fill={lit ? 'rgba(180,83,9,.9)' : 'rgba(180,83,9,.55)'}
                style={{ pointerEvents: 'none', paintOrder: 'stroke', stroke: '#fff', strokeWidth: 3, strokeLinejoin: 'round' }}
                fontFamily="inherit">{label}</text>
            </g>
          )
        })}

        {/* 节点（可点击；状态着色 + 角标 + 标签） */}
        {NODES.map((n, i) => {
          const { x, y } = nodePos(i)
          const st = stageState(n.stage, stages, currentStage)
          const style = STATE_STYLE[st]
          const locked = st === 'locked'
          const circle = (
            <>
              <circle cx={x} cy={y} r={rN} fill={style.fill} stroke={style.ring} strokeWidth="1.2" />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize="11" style={{ pointerEvents: 'none' }}>{n.icon}</text>
              {st === 'running' && <circle cx={x} cy={y} r={rN + 3.5} fill="none" stroke="rgba(245,158,11,.5)" strokeWidth="1.3" className="animate-pulse" />}
              {/* 状态小圆点（右上角） */}
              <circle cx={x + 13} cy={y - 13} r="3.5" fill={style.color} stroke="white" strokeWidth="1" />
              <text x={x} y={y + rN + 13} textAnchor="middle" fontSize="9" className="fill-slate-500" style={{ pointerEvents: 'none' }}>{n.label}</text>
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