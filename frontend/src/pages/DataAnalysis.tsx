/**
 * 云观星传 - ⑤ 数据分析（产出物查看页）
 * 展示编码类目分布 / 词云 / 研究发现 / 初步解读
 */
import { StageLayout, StatusBadge, NoProjectHint, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 5, icon: '📊', title: '数据分析', en: 'DATA ANALYSIS',
  description: '内容/文本/框架分析结果与初步解读（一键模式下为框架性分析）',
}

function HBar({ label, value, color = 'bg-astro-400' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-400 w-20 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="text-[10px] font-mono text-slate-400 w-6 text-right">{value}</span>
    </div>
  )
}

export default function DataAnalysis() {
  const { projectId, status, rec, running, error, exec } = useStageExec(5)

  const output = (rec?.output ?? null) as {
    coding_table?: { category: string; count: number }[]
    findings?: { finding: string; evidence: string; confidence: number }[]
    interpretation?: string
  } | null
  const codingTable = output?.coding_table ?? []
  const findings = output?.findings ?? []
  const maxCount = Math.max(1, ...codingTable.map(c => c.count))

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'completed' && status !== 'running' && (
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '分析中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {codingTable.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card p-4">
                <h4 className="sec-label !mb-2">词云（类目权重）</h4>
                <div className="flex flex-wrap items-center justify-center gap-2 p-4 min-h-24">
                  {codingTable.map((c, i) => {
                    const size = 12 + Math.min(14, Math.round((c.count / maxCount) * 14))
                    return (
                      <span key={i} style={{ fontSize: size }}
                        className={c.count / maxCount > 0.7 ? 'text-astro-300' : c.count / maxCount > 0.4 ? 'text-aurora-300' : 'text-slate-400'}>
                        {c.category}
                      </span>
                    )
                  })}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">类目 / 框架分布</h4>
                <div className="space-y-2">
                  {codingTable.map((c, i) => (
                    <HBar key={i} label={c.category} value={Math.round((c.count / maxCount) * 100)} color={i % 2 ? 'bg-aurora-400' : 'bg-astro-400'} />
                  ))}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">研究发现（传播路径线索）</h4>
                <div className="space-y-2">
                  {findings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${f.confidence >= 0.7 ? 'bg-aurora-400' : f.confidence >= 0.4 ? 'bg-astro-400' : 'bg-slate-500'}`} />
                      <p className="text-[11px] text-slate-300 leading-snug">{f.finding}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">传播路径 / 证据</h4>
                <div className="space-y-2">
                  {findings.map((f, i) => (
                    f.evidence && <p key={i} className="text-[10px] text-slate-500 leading-snug">"{f.evidence}"</p>
                  ))}
                </div>
              </div>
            </div>
          )}
          {output?.interpretation && (
            <div className="card p-5 border-astro-400/25">
              <h4 className="sec-label !mb-2">初步解读</h4>
              <p className="text-[13px] text-slate-300 leading-relaxed">{output.interpretation}</p>
            </div>
          )}
        </div>
      )}
    </StageLayout>
  )
}
