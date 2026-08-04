/**
 * 云观星传 - ① 选题孵化
 * 输入研究兴趣 → AI 推荐 3-5 个选题方向（研究价值/覆盖度/创新潜力评分）→ 选定进入文献综述
 */
import { useState } from 'react'
import { StageLayout, StageActions, ScoreBar, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 1, icon: '💡', title: '选题孵化', en: 'RESEARCH INSPIRATION',
  description: '输入研究兴趣，模拟多学者讨论，推荐选题方向并评估研究价值',
}

export default function Inspiration() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(1)
  const [interest, setInterest] = useState('')
  const [selected, setSelected] = useState('')

  const output = (rec?.output ?? null) as { directions?: { title: string; summary: string; research_value: number; existing_coverage: number; innovation_potential: number; reasons: string[]; keywords: string[] }[]; discussion_summary?: string } | null
  const directions = output?.directions ?? []

  const handleRun = async () => {
    if (!interest.trim()) return
    await exec({ topic: interest.trim(), interest: interest.trim() })
  }

  const handleSelect = async () => {
    if (!selected) return
    await exec({ topic: interest || rec?.output?.topic || '', selected_direction: selected, direction: selected })
    await approve()
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区 */}
          <div className="card p-5">
            <h3 className="sec-label !mb-3">请输入你的研究兴趣</h3>
            <div className="flex flex-col md:flex-row gap-3">
              <textarea
                value={interest}
                onChange={e => setInterest(e.target.value)}
                placeholder="例如：朱雀2号火箭的国际报道 / 嫦娥七号任务的全球媒体关注"
                rows={2}
                className="flex-1 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60 resize-none"
              />
              <button onClick={handleRun} disabled={running || !interest.trim()}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '讨论中…' : '开始讨论 →'}
              </button>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={handleSelect} running={running} error={error} runLabel="重新孵化选题" />
            </div>
          </div>

          {/* 推荐方向 */}
          {directions.length > 0 && (
            <div className="space-y-3">
              <h3 className="sec-label">AI 推荐方向</h3>
              {directions.map((d, i) => (
                <button
                  key={i}
                  onClick={() => setSelected(d.title)}
                  className={`w-full text-left rounded-xl border p-4 transition-all ${
                    selected === d.title ? 'border-astro-400/70 bg-astro-500/10' : 'border-white/10 bg-white/[0.02] hover:border-white/25'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-slate-100">{i + 1}. {d.title}</p>
                      <p className="text-[11px] text-slate-500 mt-1">{d.summary}</p>
                    </div>
                    {selected === d.title && <span className="text-astro-300 text-lg shrink-0">●</span>}
                  </div>
                  <div className="mt-3 space-y-1.5">
                    <ScoreBar label="研究价值" value={d.research_value} color="bg-astro-400" />
                    <ScoreBar label="覆盖度" value={d.existing_coverage} color="bg-slate-400" />
                    <ScoreBar label="创新潜力" value={d.innovation_potential} color="bg-aurora-400" />
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {d.keywords?.map((k, j) => (
                      <span key={j} className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400">{k}</span>
                    ))}
                  </div>
                  {d.reasons?.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {d.reasons.map((r, j) => <li key={j} className="text-[10px] text-slate-500">· {r}</li>)}
                    </ul>
                  )}
                </button>
              ))}
              {output?.discussion_summary && (
                <p className="text-[11px] text-slate-500 bg-white/[0.03] border border-white/10 rounded-lg p-3">
                  <span className="text-slate-400 font-medium">学者讨论纪要：</span>{output.discussion_summary}
                </p>
              )}
            </div>
          )}

          {/* 原始产出物 */}
          {rec?.status === 'awaiting_review' && <OutputView output={rec.output} />}
        </div>
      )}
    </StageLayout>
  )
}
