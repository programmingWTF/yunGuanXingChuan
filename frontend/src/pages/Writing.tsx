/**
 * 云观星传 - ⑥ 学术写作（产出物查看 + 章节级 AI 润色）
 * Notion 式分栏：左目录 / 右正文；每章支持 AI 润色（独立接口，不修改已确认产出物）
 */
import { useState } from 'react'
import { StageLayout, StageSources, StatusBadge, NoProjectHint, useStageExec, StageActions, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'
import { polishWorkflowSection } from '../api'

const INFO: StageInfo = {
  stage: 6, icon: '✍️', title: '学术写作', en: 'ACADEMIC WRITING',
  description: '整合前期产出，按标准论文结构生成初稿（支持章节润色与风格蒸馏）',
}

export default function Writing() {
  const { projectId, status, rec, running, error, locked, exec, approve, confirmRerun, rerunConfirmEl } = useStageExec(6)
  const [activeSection, setActiveSection] = useState(0)
  const [instruction, setInstruction] = useState('')
  const [polishing, setPolishing] = useState(false)
  const [polishResult, setPolishResult] = useState<{ section: string; content: string } | null>(null)
  const [polishError, setPolishError] = useState('')

  const output = (rec?.output ?? null) as {
    title?: string
    sections?: { section: string; content: string }[]
    style_notes?: string[]
  } | null
  const sections = output?.sections ?? []
  const active = sections[activeSection]

  /** AI 润色当前章节（返回润色后正文，不覆盖已确认产出物） */
  const handlePolish = async () => {
    if (!projectId || !active) return
    setPolishing(true)
    setPolishError('')
    try {
      const result = await polishWorkflowSection(projectId, active.section, active.content, instruction)
      setPolishResult(result)
    } catch {
      setPolishError('润色失败，请确认后端已启动后重试')
    } finally {
      setPolishing(false)
    }
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            <StageActions
            stage={6}
            status={status}
            onRun={() => void exec({})}
            onApprove={approve}
            running={running}
            error={error}
            runLabel="开始写作"
          />
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />
          <StageSources output={rec?.output ?? null} />

          {sections.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-lg font-bold text-slate-800 mb-4 text-center">{output?.title}</h3>
              <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-4">
                <nav className="space-y-1 self-start sticky top-20">
                  {sections.map((s, i) => (
                    <button key={i} onClick={() => { setActiveSection(i); setPolishResult(null); setPolishError('') }}
                      className={`w-full text-left text-[12px] px-3 py-2 rounded-lg transition-colors ${activeSection === i ? 'bg-indigo-50 text-indigo-600 border border-indigo-200' : 'text-slate-500 hover:text-slate-600 hover:bg-slate-100'
                        }`}>
                      {s.section}
                    </button>
                  ))}
                </nav>
                {active && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-sm font-medium text-slate-700">{active.section}</h4>
                      {/* AI 润色操作区 */}
                      <div className="flex items-center gap-2 shrink-0">
                        <input
                          value={instruction}
                          onChange={e => setInstruction(e.target.value)}
                          placeholder="润色要求（可选），如：更简洁、突出创新点"
                          className="input-field !w-52 !bg-slate-50 !rounded-lg !text-[11px] !px-2.5 !py-1.5"
                        />
                        <button onClick={handlePolish} disabled={polishing}
                          className="text-[11px] px-3 py-1.5 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-40 transition-all">
                          {polishing ? '⏳ 润色中…' : '✨ AI 润色'}
                        </button>
                      </div>
                    </div>

                    {/* 原文 */}
                    <p className="text-[13px] text-slate-600 leading-relaxed whitespace-pre-wrap">{active.content}</p>

                    {/* 润色结果（不落盘，可对比/复制） */}
                    {polishResult && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-medium text-emerald-600">✨ 润色结果（未写入产出物，可复制使用）</p>
                          <button onClick={() => navigator.clipboard?.writeText(polishResult.content)}
                            className="text-[10px] px-2 py-1 rounded border border-slate-200 text-slate-600 hover:border-emerald-400 hover:text-emerald-700 transition-all">
                            复制
                          </button>
                        </div>
                        <p className="text-[13px] text-slate-700 leading-relaxed whitespace-pre-wrap">{polishResult.content}</p>
                      </div>
                    )}
                    {polishError && <p className="text-[11px] text-red-600">{polishError}</p>}
                  </div>
                )}
              </div>
              {output?.style_notes && output.style_notes.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-100">
                  <p className="sec-label !mb-1">风格蒸馏说明</p>
                  {output.style_notes.map((n, i) => <p key={i} className="text-[10px] text-slate-500">· {n}</p>)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}