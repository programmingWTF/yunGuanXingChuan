/**
 * 云观星传 - ④ 方法推荐（产出物查看页）
 * 展示方法卡片（适配度/类型/范文/操作步骤）
 */
import { useState } from 'react'
import { StageLayout, ScoreBar, StatusBadge, NoProjectHint, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 4, icon: '🧪', title: '方法推荐', en: 'RESEARCH METHOD',
  description: '按研究问题性质推荐方法，输出适配度评分与操作步骤',
}

export default function Method() {
  const { projectId, status, rec, running, error, exec } = useStageExec(4)
  const [expanded, setExpanded] = useState<number | null>(null)

  const output = (rec?.output ?? null) as {
    methods?: { name: string; method_type: string; fit_score: number; representative_papers: string[]; operation_steps: string[]; rationale: string }[]
  } | null
  const methods = output?.methods ?? []

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'completed' && status !== 'running' && (
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '生成中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {methods.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {methods.map((m, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-slate-100">{i + 1}. {m.name}</p>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-500 mt-1 inline-block">
                        {m.method_type === 'quantitative' ? '量化' : m.method_type === 'qualitative' ? '质性' : '混合'}
                      </span>
                    </div>
                    <ScoreBar label="适配度" value={m.fit_score} color="bg-astro-400" />
                  </div>
                  <p className="text-[11px] text-slate-400">{m.rationale}</p>
                  {m.representative_papers?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {m.representative_papers.map((p, j) => (
                        <span key={j} className="text-[10px] px-2 py-0.5 rounded bg-astro-500/10 border border-astro-400/25 text-astro-300">{p}</span>
                      ))}
                    </div>
                  )}
                  <button onClick={() => setExpanded(expanded === i ? null : i)}
                    className="text-[11px] text-astro-400 hover:text-astro-300 transition-colors">
                    {expanded === i ? '收起操作步骤 ▲' : '展开操作步骤 ▼'}
                  </button>
                  {expanded === i && m.operation_steps?.length > 0 && (
                    <ol className="space-y-1.5 pl-4 list-decimal">
                      {m.operation_steps.map((s, j) => (
                        <li key={j} className="text-[11px] text-slate-300 leading-relaxed">{s}</li>
                      ))}
                    </ol>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </StageLayout>
  )
}
