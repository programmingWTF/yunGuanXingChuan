/**
 * 云观星传 - ⑦ 同行评审（产出物查看页）
 * 展示三审稿人评分与一键修改说明
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StageLayout, StageSources, ScoreBar, StatusBadge, NoProjectHint, useStageExec, StageActions, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'
import { useStore } from '../store'

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

/** 评审意见 → 目标页���由（issue #130）：涉及文献/综述/引用的意见去文献综述页，其余去研究设计页 */
function suggestionTarget(text: string): 'literature' | 'design' {
  return /文献|参考|综述|引用|出处|literature|citation|reference/i.test(text) ? 'literature' : 'design'
}

export default function Review() {
  const { projectId, status, rec, running, error, locked, exec, approve, confirmRerun, rerunConfirmEl } = useStageExec(7)
  const { setRevisionHint } = useStore()
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)

  /** 触发修改（issue #130）：携带该条评审意见跳转到对应页面作为修改提示 */
  const gotoRevise = (text: string, target: 'literature' | 'design') => {
    setRevisionHint({ text, source: 'review' })
    navigate(target === 'literature' ? '/literature' : '/design')
  }

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
            <StageActions
            stage={7}
            status={status}
            onRun={() => void exec({})}
            onApprove={approve}
            running={running}
            error={error}
            runLabel="开始评审"
          />
          </div>

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />
          <StageSources output={rec?.output ?? null} />

          {reviewers.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {reviewers.map((r, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">{r.reviewer_id}</p>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-600">{r.perspective}</span>
                  </div>
                  <div className="space-y-1.5">
                    <ScoreBar label="创新性" value={r.scores?.innovation ?? 0} color="bg-indigo-500" />
                    <ScoreBar label="方法规范" value={r.scores?.methodology ?? 0} />
                    <ScoreBar label="论证逻辑" value={r.scores?.argumentation ?? 0} color="bg-emerald-500" />
                    <ScoreBar label="文献覆盖" value={r.scores?.literature ?? 0} />
                    <ScoreBar label="学术语言" value={r.scores?.language ?? 0} color="bg-red-500" />
                  </div>
                  {r.suggestions?.length > 0 && (
                    <ul className="space-y-1.5 pt-2 border-t border-slate-100">
                      {r.suggestions.map((s, j) => {
                        const text = typeof s === 'string' ? s : JSON.stringify(s)
                        const target = suggestionTarget(text)
                        return (
                          <li key={j} className="text-[11px] text-slate-500 leading-relaxed flex items-start gap-1.5">
                            <span className="flex-1 min-w-0">· {text}</span>
                            <button
                              onClick={() => gotoRevise(text, target)}
                              title="携带该条评审意见跳转，作为对应页面的修改提示（闭环迭代 issue #130）"
                              className={`shrink-0 text-[9px] px-2 py-0.5 rounded border transition-all ${
                                target === 'literature'
                                  ? 'border-sky-200 text-sky-600 hover:bg-sky-50'
                                  : 'border-indigo-200 text-indigo-600 hover:bg-indigo-50'
                              }`}
                            >
                              {target === 'literature' ? '📚 触发修改' : '✏️ 触发修改'}
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          {output?.revision_notes && (
            <div className="card p-5 border-emerald-200">
              <div className="flex items-center justify-between mb-2">
                <h3 className="sec-label !mb-0">📝 一键修改说明</h3>
                <button onClick={handleCopy} className="text-[11px] px-2.5 py-1 rounded-lg border border-slate-200 text-slate-600 hover:border-indigo-400 hover:text-indigo-700 transition-all">
                  {copied ? '已复制 ✓' : '复制'}
                </button>
              </div>
              <p className="text-[13px] text-slate-700 leading-relaxed whitespace-pre-wrap">{output.revision_notes}</p>
              {/* issue #130 闭环迭代：一键修改说明整体也可作为提示跳转 */}
              <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100">
                <button onClick={() => gotoRevise(output!.revision_notes!, 'design')}
                  className="text-[11px] px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-600 hover:bg-indigo-50 transition-all">
                  ✏️ 按修改说明去研究设计 →
                </button>
                <button onClick={() => gotoRevise(output!.revision_notes!, 'literature')}
                  className="text-[11px] px-3 py-1.5 rounded-lg border border-sky-200 text-sky-600 hover:bg-sky-50 transition-all">
                  📚 去补充文献检索 →
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}