/**
 * 云观星传 - ① 选题孵化（产出物查看页）
 * 一键全流程模式下自动生成，本页仅展示 AI 推荐的选题方向与评分
 */
import { StageLayout, ScoreBar, StatusBadge, NoProjectHint, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 1, icon: '💡', title: '选题孵化', en: 'RESEARCH INSPIRATION',
  description: '模拟多学者讨论，推荐选题方向并评估研究价值',
}

export default function Inspiration() {
  const { projectId, status, rec, running, error, exec } = useStageExec(1)

  const output = (rec?.output ?? null) as {
    directions?: { title: string; summary: string; research_value: number; existing_coverage: number; innovation_potential: number; reasons: string[]; keywords: string[] }[]
    discussion_summary?: string
  } | null
  const directions = output?.directions ?? []

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

          {directions.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {directions.map((d, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <p className="text-sm font-medium text-slate-100">{i + 1}. {d.title}</p>
                  <p className="text-[11px] text-slate-500">{d.summary}</p>
                  <div className="space-y-1.5">
                    <ScoreBar label="研究价值" value={d.research_value} color="bg-astro-400" />
                    <ScoreBar label="覆盖度" value={d.existing_coverage} color="bg-slate-400" />
                    <ScoreBar label="创新潜力" value={d.innovation_potential} color="bg-aurora-400" />
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {d.keywords?.map((k, j) => (
                      <span key={j} className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400">{k}</span>
                    ))}
                  </div>
                  {d.reasons?.length > 0 && (
                    <ul className="space-y-0.5">
                      {d.reasons.map((r, j) => <li key={j} className="text-[10px] text-slate-500">· {r}</li>)}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          {output?.discussion_summary && (
            <p className="text-[11px] text-slate-500 bg-white/[0.03] border border-white/10 rounded-lg p-3">
              <span className="text-slate-400 font-medium">学者讨论纪要：</span>{output.discussion_summary}
            </p>
          )}
          {directions.length === 0 && rec?.status === 'completed' && (
            <p className="text-[11px] text-slate-600">该阶段未生成方向卡片，可点击"重新生成本阶段"</p>
          )}
        </div>
      )}
    </StageLayout>
  )
}
