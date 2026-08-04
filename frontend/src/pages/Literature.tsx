/**
 * 云观星传 - ② 文献综述
 * 左侧文献归类（主题/时间/方法论）+ 右侧综述正文 + Research Gap 高亮
 */
import { useState } from 'react'
import { StageLayout, StageActions, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 2, icon: '📚', title: '文献综述', en: 'LITERATURE REVIEW',
  description: '文献归类梳理，识别研究 Gap（未覆盖的视角/方法/对象）',
}

export default function Literature() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(2)
  const [direction, setDirection] = useState('')

  const output = (rec?.output ?? null) as {
    sections?: { theme: string; content: string }[]
    research_gap?: { description: string; missing_perspectives: string[]; suggestion: string }
    references?: { title: string; source: string; year: string }[]
  } | null
  const sections = output?.sections ?? []
  const gap = output?.research_gap

  const handleRun = async () => {
    await exec({ direction: direction || undefined })
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区 */}
          <div className="card p-5">
            <h3 className="sec-label !mb-3">研究主题</h3>
            <div className="flex flex-col md:flex-row gap-3">
              <input
                value={direction}
                onChange={e => setDirection(e.target.value)}
                placeholder="可指定选题方向（留空使用上一阶段选定的方向）"
                className="flex-1 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60"
              />
              <button onClick={handleRun} disabled={running}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '综述中…' : '生成文献综述 →'}
              </button>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={approve} running={running} error={error} />
            </div>
          </div>

          {/* 综述内容 */}
          {sections.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5">
              {/* 左侧：文献归类 */}
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

              {/* 右侧：综述正文 + Gap */}
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
                    {gap.suggestion && (
                      <p className="text-[11px] text-slate-400 mt-3">💡 建议：{gap.suggestion}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {rec?.status === 'awaiting_review' && <OutputView output={rec.output} />}
        </div>
      )}
    </StageLayout>
  )
}
