/**
 * 云观星传 - ② 文献综述（产出物查看页）
 * 展示文献归类、综述正文与 Research Gap
 */
import { StageLayout, StageSources, StatusBadge, NoProjectHint, useStageExec, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 2, icon: '📚', title: '文献综述', en: 'LITERATURE REVIEW',
  description: '文献归类梳理，识别研究 Gap 与理论关系图',
}

interface TheoryRelation {
  source: string
  relation: string
  target: string
}

/** 理论关系图（SVG 节点-连线，数据来自产出物 theory_relations）
 * 布局修正（issue #59）：按节点累计宽度排布 + 最小间距，物理上避免节点重叠；
 * 长名自动换行（不截断）；连线从节点底部偏向目标侧引出，关系标签错开下沉，避免交叉遮挡。 */
function TheoryRelationGraph({ relations }: { relations: TheoryRelation[] }) {
  if (!relations || relations.length === 0) return null
  // 收集全部节点（去重，保持出现顺序）
  const nodes: string[] = []
  relations.forEach(r => {
    if (r.source && !nodes.includes(r.source)) nodes.push(r.source)
    if (r.target && !nodes.includes(r.target)) nodes.push(r.target)
  })
  if (nodes.length < 2) return null

  const W = 860
  const NODE_Y = 26
  const LINE_H = 18 // 每行文本高度
  const MIN_GAP = 28  // 节点最小水平间距
  const textW = (t: string) => t.length * 13 + 28  // 文本近似宽 + 内边距
  // 长名拆成多行（每行 ≤10 字），宽度按最长行计算
  const wrap = (name: string): string[] => {
    if (name.length <= 10) return [name]
    const half = Math.ceil(name.length / 2)
    return [name.slice(0, Math.min(10, half)), name.slice(Math.min(10, half))]
  }
  let rowsOf = nodes.map(wrap)
  let nodeW = rowsOf.map(rs => Math.max(84, ...rs.map(textW)))

  // 极端兜底：单行总宽仍溢出时，把每行字长上限压到 7，让超长名更多换行、变窄，尽量收进画布且不重叠
  if (nodes.length > 1) {
    const totalNode = nodeW.reduce((a, b) => a + b, 0)
    if (totalNode > W - 24 * (nodes.length - 1)) {
      const wrap2 = (name: string): string[] => {
        if (name.length <= 7) return [name]
        const out: string[] = []
        for (let k = 0; k < name.length; k += 7) out.push(name.slice(k, k + 7))
        return out
      }
      rowsOf = nodes.map(wrap2)
      nodeW = rowsOf.map(rs => Math.max(76, ...rs.map((t: string) => t.length * 11 + 24)))
    }
  }

  // 累积宽度布局：总宽 = Σ节点宽 + (n-1)*GAP，超 W 时收缩 GAP（不低于 10）
  const totalNode = nodeW.reduce((a, b) => a + b, 0)
  let gap = MIN_GAP
  if (nodes.length > 1) {
    const maxGap = Math.floor((W - totalNode) / (nodes.length - 1))
    if (maxGap < gap) gap = Math.max(10, maxGap)
  }
  const offsets: number[] = []
  let acc = 0
  nodeW.forEach((w) => { offsets.push(acc + w / 2); acc += w + gap })

  const nodeH = (rs: string[]) => rs.length * LINE_H + 12  // 节点矩形高度 = 文本总高 + 内边距
  const H = 170

  return (
    <div className="card p-4">
      <h3 className="sec-label !mb-1">🧭 理论关系图</h3>
      <p className="text-[10px] text-slate-400 mb-2">与选题相关的理论及其关联（承继 / 互补 / 对比 / 应用）</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="理论关系图">
        {/* 连线：从各自节点矩形底部引出（偏向目标侧），弧线下垂到节点下方空白区 */}
        {relations.map((r, i) => {
          const si = nodes.indexOf(r.source)
          const ti = nodes.indexOf(r.target)
          const sx = offsets[si], tx = offsets[ti]
          const dir = tx >= sx ? 1 : -1
          const x1 = sx + dir * nodeW[si] * 0.22  // 连接点偏向目标侧，减少从节点中部引出
          const x2 = tx - dir * nodeW[ti] * 0.22
          const y1 = NODE_Y + nodeH(rowsOf[si])   // source 矩形底边
          const y2 = NODE_Y + nodeH(rowsOf[ti])   // target 矩形底边
          const cx = (x1 + x2) / 2
          const cy = Math.max(y1, y2) + 34        // 弧线控制点深度
          // 标签错开：按关系索引错开下沉，避开节点与其它弧线交叉
          const lblY = Math.max(y1, y2) + 12 + (i % 3) * 14
          return (
            <g key={i}>
              <path d={`M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`}
                fill="none" stroke="rgba(14,165,233,.45)" strokeWidth="1.5" />
              {r.relation && (
                <text x={cx} y={lblY} textAnchor="middle"
                  className="fill-slate-500" fontSize="10">{r.relation}</text>
              )}
            </g>
          )
        })}
        {/* 节点 */}
        {nodes.map((_, i) => {
          const x = offsets[i], w = nodeW[i], rs = rowsOf[i]
          const h = nodeH(rs)
          return (
            <g key={i}>
              <rect x={x - w / 2} y={NODE_Y} width={w} height={h} rx="10"
                fill="rgba(14,165,233,.08)" stroke="rgba(14,165,233,.4)" strokeWidth="1" />
              <text x={x} textAnchor="middle" className="fill-slate-700" fontSize="12">
                {rs.map((line, li) => (
                  <tspan key={line} x={x} y={NODE_Y + LINE_H + li * LINE_H}>{line}</tspan>
                ))}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export default function Literature() {
  const { projectId, status, rec, running, error, locked, confirmRerun, rerunConfirmEl } = useStageExec(2)

  const output = (rec?.output ?? null) as {
    sections?: { theme: string; content: string }[]
    research_gap?: { description: string; missing_perspectives: string[]; suggestion: string }
    references?: { title: string; source: string; year: string }[]
    theory_relations?: TheoryRelation[]
  } | null
  const sections = output?.sections ?? []
  const gap = output?.research_gap

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'running' && (
              <button onClick={confirmRerun} disabled={running || locked}
                className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-indigo-400 hover:text-indigo-700 disabled:opacity-40 transition-all"
                title={locked ? '请先完成上一阶段并确认' : undefined}>
                  {running ? '生成中…' : status === 'pending' ? '开始生成' : '重新运行'}
                </button>
            )}
            {error && <span className="text-[11px] text-red-600">{error}</span>}
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />
          <StageSources output={rec?.output ?? null} />

          {sections.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
              <div className="card p-4 space-y-2 self-start">
                <h3 className="sec-label !mb-2">文献归类</h3>
                {sections.map((s, i) => (
                  <a key={i} href={`#sec-${i}`}
                    className="block text-[12px] text-slate-600 hover:text-indigo-700 py-1.5 px-2 rounded-lg hover:bg-slate-100 transition-colors">
                    ▸ {s.theme}
                  </a>
                ))}
                {output?.references && (
                  <div className="mt-4 pt-3 border-t border-slate-100">
                    <p className="sec-label !mb-2">参考文献（{output.references.length}）</p>
                    {output.references.map((r, i) => (
                      <p key={i} className="text-[10px] text-slate-500 mb-1">
                        {r.year && <span className="text-slate-400">[{r.year}]</span>} {r.title}
                        {r.source && <span className="text-slate-400"> — {r.source}</span>}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {sections.map((s, i) => (
                  <div key={i} id={`sec-${i}`} className="card p-5">
                    <h4 className="text-sm font-medium text-indigo-600 mb-2">{s.theme}</h4>
                    <p className="text-[13px] text-slate-600 leading-relaxed whitespace-pre-wrap">{s.content}</p>
                  </div>
                ))}
                {gap && (
                  <div className="card p-5 border-red-200 bg-red-50">
                    <h4 className="text-sm font-medium text-amber-600 mb-2">🔍 Research Gap 研究空白</h4>
                    <p className="text-[13px] text-slate-700 leading-relaxed">{gap.description}</p>
                    {gap.missing_perspectives?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {gap.missing_perspectives.map((m, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-red-50 border border-red-200 text-amber-600">缺：{m}</span>
                        ))}
                      </div>
                    )}
                    {gap.suggestion && <p className="text-[11px] text-slate-500 mt-3">💡 建议：{gap.suggestion}</p>}
                  </div>
                )}
                {/* 理论关系图（ChatGPT 方案：Gap 下方展示） */}
                <TheoryRelationGraph relations={output?.theory_relations ?? []} />
              </div>
            </div>
          )}
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}