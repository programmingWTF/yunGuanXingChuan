/**
 * 云观星传 - 闭环迭代流程示意图（issue #130）
 *
 * 首页展示：7 阶段环形闭环 —— 选题孵化 → 文献综述 → 研究设计 → 方法推荐 →
 * 数据分析 → 学术写作 → 同行评审 →（虚线回流箭头回到 文献综述 / 研究设计）。
 *
 * 纯展示组件（无状态、无数据依赖），评审第一眼能看到「分析 → 诊断 → 修改 → 再分析」的
 * 闭环迭代能力。节点/箭头全部 SVG 绘制，随容器宽度自适应。
 */

/** 环上 7 个阶段节点（顺时针，从顶部开始） */
const NODES = [
  { label: '选题孵化', icon: '💡' },
  { label: '文献综述', icon: '📚' },
  { label: '研究设计', icon: '🎯' },
  { label: '方法推荐', icon: '🧪' },
  { label: '数据分析', icon: '📊' },
  { label: '学术写作', icon: '✍️' },
  { label: '同行评审', icon: '👨‍⚖️' },
]

/** 回流虚线：同行评审 → 研究设计（主回流），同行评审 → 文���综述（分支回流） */
const BACKFLOW = [
  { from: 6, to: 2, label: '按评审意见修改设计' },
  { from: 6, to: 1, label: '补充文献检索' },
]

const W = 860
const H = 300
const CX = W / 2
const CY = 138
const R = 108

/** 节点在环上的坐标（第 0 个在正上方，顺时针排布） */
function nodePos(i: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + (i * 2 * Math.PI) / NODES.length
  return { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) * 0.78 }
}

export default function ClosedLoopDiagram() {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h3 className="sec-label !mb-0">🔄 闭环迭代流程</h3>
        <span className="text-[10px] text-slate-400">分析 → 诊断 → 修改 → 再分析，研究在循环中逐轮提升</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="闭环迭代流程示意图">
        <defs>
          <marker id="cl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(99,102,241,.55)" />
          </marker>
          <marker id="cl-arrow-dash" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill="rgba(217,119,6,.6)" />
          </marker>
        </defs>

        {/* 环向实线箭头（相邻节点） */}
        {NODES.map((_, i) => {
          const a = nodePos(i)
          const b = nodePos((i + 1) % NODES.length)
          const dx = b.x - a.x
          const dy = b.y - a.y
          const len = Math.hypot(dx, dy) || 1
          const pad = 34 // 节点圆半径 + 余量
          const x1 = a.x + (dx / len) * pad
          const y1 = a.y + (dy / len) * pad
          const x2 = b.x - (dx / len) * (pad + 8)
          const y2 = b.y - (dy / len) * (pad + 8)
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="rgba(99,102,241,.4)" strokeWidth="2" markerEnd="url(#cl-arrow)" />
          )
        })}

        {/* 回流虚线（同行评审 → 研究设计 / 文献综述） */}
        {BACKFLOW.map(({ from, to, label }, i) => {
          const a = nodePos(from)
          const b = nodePos(to)
          // 从评审节点下方引出，弧线绕环���下沿回到目标节点上方
          const midX = (a.x + b.x) / 2
          const midY = Math.max(a.y, b.y) + (i === 0 ? 92 : 58)
          return (
            <g key={i}>
              <path d={`M ${a.x} ${a.y + 30} Q ${midX} ${midY} ${b.x} ${b.y - 26}`}
                fill="none" stroke="rgba(217,119,6,.55)" strokeWidth="1.8" strokeDasharray="7 5"
                markerEnd="url(#cl-arrow-dash)" />
              <text x={midX} y={midY - (i === 0 ? 8 : -14)} textAnchor="middle" fontSize="10.5"
                className="fill-amber-600" opacity="0.9">{label}</text>
            </g>
          )
        })}

        {/* 节点 */}
        {NODES.map((n, i) => {
          const { x, y } = nodePos(i)
          return (
            <g key={n.label}>
              <circle cx={x} cy={y} r="24" fill="white" stroke="rgba(99,102,241,.45)" strokeWidth="1.5" />
              <text x={x} y={y + 5} textAnchor="middle" fontSize="16">{n.icon}</text>
              <text x={x} y={y + 42} textAnchor="middle" fontSize="11.5" className="fill-slate-600">{n.label}</text>
            </g>
          )
        })}
      </svg>

      {/* 闭环说明（三步一句话） */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2">
        <p className="text-[10.5px] text-slate-500 rounded-lg bg-indigo-50/60 border border-indigo-100 px-3 py-2">📊 <b className="text-slate-600">分析</b>：数据分析产出指标与 AI 诊断建议</p>
        <p className="text-[10.5px] text-slate-500 rounded-lg bg-amber-50/60 border border-amber-100 px-3 py-2">👨‍⚖️ <b className="text-slate-600">诊断</b>：同行评审三审稿人给出修改意见</p>
        <p className="text-[10.5px] text-slate-500 rounded-lg bg-emerald-50/60 border border-emerald-100 px-3 py-2">🔁 <b className="text-slate-600">回流</b>：一键携带意见回到研究设计 / 文献综述，开启下一轮</p>
      </div>
    </div>
  )
}
