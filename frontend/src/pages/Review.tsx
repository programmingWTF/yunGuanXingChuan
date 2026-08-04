/**
 * 云观星传 - ⑦ 同行评审（产出物查看页）
 * 展示三审稿人评分与一键修改说明
 */
import { useState } from 'react'
import { StageLayout, ScoreBar, StatusBadge, NoProjectHint, useStageExec, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 7, icon: '👨‍⚖️', title: '同行评审', en: 'PEER REVIEW',
  description: '模拟 3 位审稿人（方法/理论/实践专家）评审并生成修改建议',
}

interface ReviewerShape {
  reviewer_id: string
  perspective: string
  scores: { innovation: number; methodology: number; argumentation: number; literature: number; language: number }
  suggestions: string[]
}

export default function Review() {
  const { projectId, status, rec, running, error, exec } = useStageExec(7)
  const [copied, setCopied] = useState(false)

  const output = (rec?.output ?? null) as {
    reviewers?: ReviewerShape[]
    revision_notes?: string
  } | null
  const reviewers = output?.reviewers ?? []

  const handleCopy = async () => {
    if (!output?.revision_notes) return
    try {
      await navigator.clipboard.writeText(output.revision_notes)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'running' && (
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '评审中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />

          {reviewers.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {reviewers.map((r, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-100">{r.reviewer_id}</p>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-astro-500/10 border border-astro-400/25 text-astro-300">{r.perspective}</span>
                  </div>
                  <div className="space-y-1.5">
                    <ScoreBar label="创新性" value={r.scores?.innovation ?? 0} color="bg-astro-400" />
                    <ScoreBar label="方法规范" value={r.scores?.methodology ?? 0} />
                    <ScoreBar label="论证逻辑" value={r.scores?.argumentation ?? 0} color="bg-aurora-400" />
                    <ScoreBar label="文献覆盖" value={r.scores?.literature ?? 0} />
                    <ScoreBar label="学术语言" value={r.scores?.language ?? 0} color="bg-flare-400" />
                  </div>
                  {r.suggestions?.length > 0 && (
                    <ul className="space-y-1.5 pt-2 border-t border-white/[0.06]">
                      {r.suggestions.map((s, j) => (
                        <li key={j} className="text-[11px] text-slate-400 leading-relaxed">
                          · {typeof s === 'string' ? s : JSON.stringify(s)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          {output?.revision_notes && (
            <div className="card p-5 border-aurora-400/30">
              <div className="flex items-center justify-between mb-2">
                <h3 className="sec-label !mb-0">📝 一键修改说明</h3>
                <button onClick={handleCopy} className="text-[11px] px-2.5 py-1 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 transition-all">
                  {copied ? '已复制 ✓' : '复制'}
                </button>
              </div>
              <p className="text-[13px] text-slate-200 leading-relaxed whitespace-pre-wrap">{output.revision_notes}</p>
            </div>
          )}
        </div>
      )}
    </StageLayout>
  )
}
