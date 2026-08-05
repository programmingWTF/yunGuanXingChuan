/**
 * 云观星传 - ② 文献综述（产出物查看页）
 * 展示文献归类、综述正文与 Research Gap
 */
import { StageLayout, StatusBadge, NoProjectHint, useStageExec, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 2, icon: '📚', title: '文献综述', en: 'LITERATURE REVIEW',
  description: '文献归类梳理，识别研究 Gap 与理论关系图',
}

interface TheoryRelation {
  source: string
  relation: string
  target: string
}

/** 理论关系图（SVG 节点-连线，数据来自产出物 theory_relations） */
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
  const H = 170
  const NODE_Y = 26
  const NODE_H = 34
  const nameOf = (name: string) => (name.length > 10 ? `${name.slice(0, 10)}…` : name)
  const xOf = (name: string) => (nodes.length === 1 ? W / 2 : 90 + (nodes.indexOf(name) * (W - 180)) / (nodes.length - 1))
  // 宽度按截断后的显示名计算，避免超长名超出 viewBox 错位
  const wOf = (name: string) => Math.max(84, nameOf(name).length * 13 + 28)

  return (
    <div className="card p-4">
      <h3 className="sec-label !mb-1">🧭 理论关系图</h3>
      <p className="text-[10px] text-slate-400 mb-2">与选题相关的理论及其关联（承继 / 互补 / 对比 / 应用）</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="理论关系图">
        {/* 连线 */}
        {relations.map((r, i) => {
          const x1 = xOf(r.source)
          const x2 = xOf(r.target)
          const cx = (x1 + x2) / 2
          return (
            <g key={i}>
              <path d={`M ${x1} ${NODE_Y + NODE_H} Q ${cx} ${NODE_Y + 74} ${x2} ${NODE_Y + NODE_H}`}
                fill="none" stroke="rgba(14,165,233,.45)" strokeWidth="1.5" />
              <text x={cx} y={NODE_Y + 78} textAnchor="middle"
                className="fill-slate-500" fontSize="10">{r.relation}</text>
            </g>
          )
        })}
        {/* 节点 */}
        {nodes.map((n, i) => {
          const x = xOf(n)
          const w = wOf(n)
          return (
            <g key={i}>
              <rect x={x - w / 2} y={NODE_Y} width={w} height={NODE_H} rx="10"
                fill="rgba(14,165,233,.08)" stroke="rgba(14,165,233,.4)" strokeWidth="1" />
              <text x={x} y={NODE_Y + NODE_H / 2 + 4} textAnchor="middle"
                className="fill-slate-700" fontSize="12">{nameOf(n)}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export default function Literature() {
  const { projectId, status, rec, running, error, confirmRerun, rerunConfirmEl } = useStageExec(2)

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
              <button onClick={confirmRerun} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-40 transition-all">
                {running ? '生成中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-red-600">{error}</span>}
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />

          {sections.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
              <div className="card p-4 space-y-2 self-start">
                <h3 className="sec-label !mb-2">文献归类</h3>
                {sections.map((s, i) => (
                  <a key={i} href={`#sec-${i}`}
                    className="block text-[12px] text-slate-600 hover:text-sky-700 py-1.5 px-2 rounded-lg hover:bg-slate-100 transition-colors">
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
                    <h4 className="text-sm font-medium text-sky-600 mb-2">{s.theme}</h4>
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
