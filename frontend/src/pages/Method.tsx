/**
 * 云观星传 - ④ 方法推荐
 * 方法卡片（适配度 %/类型/范文/操作步骤展开）
 */
import { useState } from 'react'
import { StageLayout, StageActions, ScoreBar, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 4, icon: '🧪', title: '方法推荐', en: 'RESEARCH METHOD',
  description: '按研究问题性质推荐方法，输出适配度评分与操作步骤',
}

export default function Method() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(4)
  const [expanded, setExpanded] = useState<number | null>(null)

  const output = (rec?.output ?? null) as {
    methods?: { name: string; method_type: string; fit_score: number; representative_papers: string[]; operation_steps: string[]; rationale: string }[]
  } | null
  const methods = output?.methods ?? []

  const handleRun = async () => {
    await exec({})
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区 */}
          <div className="card p-5">
            <h3 className="sec-label !mb-1">推荐研究方法</h3>
            <p className="text-[11px] text-slate-500 mb-3">自动带入 RQ 与研究假设，按量化/质性/混合匹配方法并评分</p>
            <div className="flex items-center gap-3">
              <button onClick={handleRun} disabled={running}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '推荐中…' : '推荐方法 →'}
              </button>
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={approve} running={running} error={error} />
            </div>
          </div>

          {/* 方法卡片 */}
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
                    <div>
                      <p className="text-[10px] text-slate-600 mb-1">代表论文</p>
                      <div className="flex flex-wrap gap-1.5">
                        {m.representative_papers.map((p, j) => (
                          <span key={j} className="text-[10px] px-2 py-0.5 rounded bg-astro-500/10 border border-astro-400/25 text-astro-300">{p}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => setExpanded(expanded === i ? null : i)}
                    className="text-[11px] text-astro-400 hover:text-astro-300 transition-colors"
                  >
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

          {rec?.status === 'awaiting_review' && <OutputView output={rec.output} />}
        </div>
      )}
    </StageLayout>
  )
}
