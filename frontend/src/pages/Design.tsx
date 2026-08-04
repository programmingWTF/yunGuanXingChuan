/**
 * 云观星传 - ③ 研究设计
 * RQ 列表 + H 假设列表 + AI 质量检验（清晰度/创新性/可操作性评分）
 */
import { StageLayout, StageActions, ScoreBar, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 3, icon: '🎯', title: '研究设计', en: 'RESEARCH DESIGN',
  description: '凝练研究问题 RQ 与假设 H，输出问题质量检验报告',
}

export default function Design() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(3)

  const output = (rec?.output ?? null) as {
    research_questions?: { id: string; text: string }[]
    hypotheses?: { id: string; statement: string; hypothesis_type: string }[]
    quality_report?: { clarity: number; innovativeness: number; operability: number; comments: string[] }
  } | null
  const questions = output?.research_questions ?? []
  const hypotheses = output?.hypotheses ?? []
  const quality = output?.quality_report

  const handleRun = async () => {
    await exec({})
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区 */}
          <div className="card p-5">
            <h3 className="sec-label !mb-1">基于文献综述与 Gap 生成研究设计</h3>
            <p className="text-[11px] text-slate-500 mb-3">自动带入上一阶段的综述与 Gap，生成 1-3 个 RQ 与可选假设</p>
            <div className="flex items-center gap-3">
              <button onClick={handleRun} disabled={running}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '设计中…' : '生成研究设计 →'}
              </button>
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={approve} running={running} error={error} />
            </div>
          </div>

          {/* RQ */}
          {questions.length > 0 && (
            <div className="space-y-3">
              <h3 className="sec-label">Research Question</h3>
              {questions.map((q, i) => (
                <div key={i} className="card p-4">
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 text-xs font-mono px-2 py-1 rounded bg-astro-500/10 border border-astro-400/30 text-astro-300">{q.id}</span>
                    <p className="text-sm text-slate-200 leading-relaxed">{q.text}</p>
                  </div>
                </div>
              ))}

              {/* H */}
              {hypotheses.length > 0 && (
                <>
                  <h3 className="sec-label pt-2">Hypothesis</h3>
                  {hypotheses.map((h, i) => (
                    <div key={i} className="card p-4">
                      <div className="flex items-start gap-3">
                        <span className="shrink-0 text-xs font-mono px-2 py-1 rounded bg-aurora-500/10 border border-aurora-400/30 text-aurora-300">{h.id}</span>
                        <div>
                          <p className="text-sm text-slate-200 leading-relaxed">{h.statement}</p>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-500 mt-1 inline-block">{h.hypothesis_type === 'quantitative' ? '量化' : '质性'}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* 质量检验 */}
              {quality && (
                <div className="card p-5 border-astro-400/30">
                  <h3 className="sec-label !mb-3">AI 评价 · 问题质量检验</h3>
                  <div className="space-y-2">
                    <ScoreBar label="清晰度" value={quality.clarity} />
                    <ScoreBar label="创新性" value={quality.innovativeness} color="bg-aurora-400" />
                    <ScoreBar label="可操作性" value={quality.operability} color="bg-flare-400" />
                  </div>
                  {quality.comments?.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {quality.comments.map((c, i) => <li key={i} className="text-[11px] text-slate-500">· {c}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {rec?.status === 'awaiting_review' && <OutputView output={rec.output} />}
        </div>
      )}
    </StageLayout>
  )
}
