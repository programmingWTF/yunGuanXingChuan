/**
 * 云观星传 - ② 文献综述（产出物查看页）
 * 展示文献归类、综述正文与 Research Gap
 */
import { StageLayout, StatusBadge, NoProjectHint, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 2, icon: '📚', title: '文献综述', en: 'LITERATURE REVIEW',
  description: '文献归类梳理，识别研究 Gap（未覆盖的视角/方法/对象）',
}

export default function Literature() {
  const { projectId, status, rec, running, error, exec } = useStageExec(2)

  const output = (rec?.output ?? null) as {
    sections?: { theme: string; content: string }[]
    research_gap?: { description: string; missing_perspectives: string[]; suggestion: string }
    references?: { title: string; source: string; year: string }[]
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
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '生成中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {sections.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
              <div className="card p-4 space-y-2 self-start">
                <h3 className="sec-label !mb-2">文献归类</h3>
                {sections.map((s, i) => (
                  <a key={i} href={`#sec-${i}`}
                    className="block text-[12px] text-slate-300 hover:text-astro-300 py-1.5 px-2 rounded-lg hover:bg-white/[0.04] transition-colors">
                    ▸ {s.theme}
                  </a>
                ))}
                {output?.references && (
                  <div className="mt-4 pt-3 border-t border-white/[0.06]">
                    <p className="sec-label !mb-2">参考文献（{output.references.length}）</p>
                    {output.references.map((r, i) => (
                      <p key={i} className="text-[10px] text-slate-500 mb-1">
                        {r.year && <span className="text-slate-600">[{r.year}]</span>} {r.title}
                        {r.source && <span className="text-slate-600"> — {r.source}</span>}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {sections.map((s, i) => (
                  <div key={i} id={`sec-${i}`} className="card p-5">
                    <h4 className="text-sm font-medium text-astro-300 mb-2">{s.theme}</h4>
                    <p className="text-[13px] text-slate-300 leading-relaxed whitespace-pre-wrap">{s.content}</p>
                  </div>
                ))}
                {gap && (
                  <div className="card p-5 border-flare-400/40 bg-flare-500/[0.04]">
                    <h4 className="text-sm font-medium text-flare-300 mb-2">🔍 Research Gap 研究空白</h4>
                    <p className="text-[13px] text-slate-200 leading-relaxed">{gap.description}</p>
                    {gap.missing_perspectives?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {gap.missing_perspectives.map((m, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-flare-500/10 border border-flare-400/30 text-flare-300">缺：{m}</span>
                        ))}
                      </div>
                    )}
                    {gap.suggestion && <p className="text-[11px] text-slate-400 mt-3">💡 建议：{gap.suggestion}</p>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </StageLayout>
  )
}
