/**
 * 云观星传 - ⑥ 学术写作
 * Notion 式左右分栏：左目录（摘要/引言/文献/方法/结果/讨论/结论）右正文（可编辑），导出
 */
import { useState } from 'react'
import { StageLayout, StageActions, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 6, icon: '✍️', title: '学术写作', en: 'ACADEMIC WRITING',
  description: '整合前期产出，按标准论文结构生成初稿（支持风格蒸馏）',
}

export default function Writing() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(6)
  const [styleSample, setStyleSample] = useState('')
  const [activeSection, setActiveSection] = useState(0)
  const [edited, setEdited] = useState<Record<string, string>>({})

  const output = (rec?.output ?? null) as {
    title?: string
    sections?: { section: string; content: string }[]
    style_notes?: string[]
  } | null
  const sections = output?.sections ?? []
  const active = sections[activeSection]

  const handleRun = async () => {
    await exec({ style_sample: styleSample.trim() || undefined })
    setEdited({})
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区：风格蒸馏 */}
          <div className="card p-5">
            <div className="flex flex-col md:flex-row gap-3">
              <textarea
                value={styleSample}
                onChange={e => setStyleSample(e.target.value)}
                placeholder="（可选）风格蒸馏：粘贴目标学者的已发表论文片段，AI 将学习其学术话语体系，减少 AI 味"
                rows={2}
                className="flex-1 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60 resize-none"
              />
              <button onClick={handleRun} disabled={running}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '写作中…' : '生成论文初稿 →'}
              </button>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={approve} running={running} error={error} />
            </div>
          </div>

          {sections.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-lg font-bold text-white mb-4 text-center">{output?.title}</h3>
              {/* 左右分栏 */}
              <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-4">
                {/* 左：目录 */}
                <nav className="space-y-1 self-start sticky top-20">
                  {sections.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveSection(i)}
                      className={`w-full text-left text-[12px] px-3 py-2 rounded-lg transition-colors ${
                        activeSection === i ? 'bg-astro-500/15 text-astro-300 border border-astro-400/30' : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                      }`}
                    >
                      {s.section}
                    </button>
                  ))}
                </nav>
                {/* 右：正文（可编辑） */}
                {active && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-slate-200">{active.section}</h4>
                    <textarea
                      value={edited[active.section] ?? active.content}
                      onChange={e => setEdited(prev => ({ ...prev, [active.section]: e.target.value }))}
                      rows={12}
                      className="w-full rounded-lg bg-white/[0.03] border border-white/10 px-4 py-3 text-[13px] leading-relaxed text-slate-200 focus:outline-none focus:border-astro-400/60 resize-y"
                    />
                  </div>
                )}
              </div>
              {output?.style_notes && output.style_notes.length > 0 && (
                <div className="mt-4 pt-3 border-t border-white/[0.06]">
                  <p className="sec-label !mb-1">风格蒸馏说明</p>
                  {output.style_notes.map((n, i) => <p key={i} className="text-[10px] text-slate-500">· {n}</p>)}
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
