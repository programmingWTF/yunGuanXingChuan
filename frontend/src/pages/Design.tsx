/**
 * 云观星传 - ③ 研究设计（产出物查看页）
 * 展示 RQ / H 列表与 AI 质量检验评分
 */
import { StageLayout, ScoreBar, StatusBadge, NoProjectHint, useStageExec, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 3, icon: '🎯', title: '研究设计', en: 'RESEARCH DESIGN',
  description: '凝练研究问题 RQ 与假设 H，输出问题质量检验报告',
}

export default function Design() {
  const { projectId, status, rec, running, error, exec } = useStageExec(3)

  const output = (rec?.output ?? null) as {
    research_questions?: { id: string; text: string }[]
    hypotheses?: { id: string; statement: string; hypothesis_type: string }[]
    quality_report?: { clarity: number; innovativeness: number; operability: number; comments: string[] }
  } | null
  const questions = output?.research_questions ?? []
  const hypotheses = output?.hypotheses ?? []
  const quality = output?.quality_report

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'running' && (
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '生成中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />

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
        </div>
      )}
    </StageLayout>
  )
}
