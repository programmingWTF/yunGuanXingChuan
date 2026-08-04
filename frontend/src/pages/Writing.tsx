/**
 * 云观星传 - ⑥ 学术写作（产出物查看页）
 * Notion 式分栏展示论文初稿章节
 */
import { useState } from 'react'
import { StageLayout, StatusBadge, NoProjectHint, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 6, icon: '✍️', title: '学术写作', en: 'ACADEMIC WRITING',
  description: '整合前期产出，按标准论文结构生成初稿',
}

export default function Writing() {
  const { projectId, status, rec, running, error, exec } = useStageExec(6)
  const [activeSection, setActiveSection] = useState(0)

  const output = (rec?.output ?? null) as {
    title?: string
    sections?: { section: string; content: string }[]
    style_notes?: string[]
  } | null
  const sections = output?.sections ?? []
  const active = sections[activeSection]

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {status !== 'running' && (
              <button onClick={() => exec({})} disabled={running}
                className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-slate-300 hover:border-astro-400/60 hover:text-astro-300 disabled:opacity-40 transition-all">
                {running ? '写作中…' : '重新生成本阶段'}
              </button>
            )}
            {error && <span className="text-[11px] text-flare-400">{error}</span>}
          </div>

          {sections.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-lg font-bold text-white mb-4 text-center">{output?.title}</h3>
              <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-4">
                <nav className="space-y-1 self-start sticky top-20">
                  {sections.map((s, i) => (
                    <button key={i} onClick={() => setActiveSection(i)}
                      className={`w-full text-left text-[12px] px-3 py-2 rounded-lg transition-colors ${
                        activeSection === i ? 'bg-astro-500/15 text-astro-300 border border-astro-400/30' : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                      }`}>
                      {s.section}
                    </button>
                  ))}
                </nav>
                {active && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-slate-200">{active.section}</h4>
                    <p className="text-[13px] text-slate-300 leading-relaxed whitespace-pre-wrap">{active.content}</p>
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
        </div>
      )}
    </StageLayout>
  )
}
