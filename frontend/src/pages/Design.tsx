/**
 * 云观星传 - ③ 研究设计（产出物查看页）
 * 展示 RQ / H 列表与 AI 质量检验评分
 *
 * issue #129 闭环迭代：
 * - 顶部迭代提示条：从数据分析页跳转过来时展示 AI 诊断建议 + 当前设计版本号（V1/V2/V3…）
 * - 支持按建议编辑 RQ/H 并保存（design_version +1），形成「分析 → 诊断 → 修改 → 再分析」闭环
 */
import { useState } from 'react'
import { StageLayout, StageSources, ScoreBar, StatusBadge, NoProjectHint, useStageExec, StageActions, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'
import { useStore } from '../store'
import { saveDesignStage } from '../api'

const INFO: StageInfo = {
  stage: 3, icon: '🎯', title: '研究设计', en: 'RESEARCH DESIGN',
  description: '凝练研究问题 RQ 与假设 H，输出问题质量检验报告',
}

interface RQ { id: string; text: string }
interface HY { id: string; statement: string; hypothesis_type: string }

export default function Design() {
  const { projectId, status, rec, running, error, locked, exec, approve, confirmRerun, rerunConfirmEl } = useStageExec(3)
  const { currentProject, iterationSuggestion, setIterationSuggestion, revisionHint, setRevisionHint, loadProject } = useStore()

  // issue #129 闭环迭代：设计版本号 + 迭代记录（后端持久化）
  const designVersion = currentProject?.design_version ?? 1
  const iterations = currentProject?.iterations ?? []
  const [editing, setEditing] = useState(false)
  const [draftRQ, setDraftRQ] = useState<RQ[]>([])
  const [draftH, setDraftH] = useState<HY[]>([])
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  const output = (rec?.output ?? null) as {
    research_questions?: RQ[]
    hypotheses?: HY[]
    quality_report?: { clarity: number; innovativeness: number; operability: number; comments: string[] }
  } | null
  const questions = output?.research_questions ?? []
  const hypotheses = output?.hypotheses ?? []
  const quality = output?.quality_report

  /** 进入编辑模式：以当前产出物为草稿 */
  const startEdit = () => {
    setDraftRQ(questions.map(q => ({ ...q })))
    setDraftH(hypotheses.map(h => ({ ...h })))
    setEditing(true)
    setSaveMsg('')
  }

  const cancelEdit = () => {
    setEditing(false)
    setSaveMsg('')
  }

  /** 保存设计修改 → 后端更新产出物 + design_version +1（issue #129） */
  const saveEdit = async () => {
    if (!projectId) return
    setSaving(true)
    setSaveMsg('')
    try {
      await saveDesignStage(projectId, {
        research_questions: draftRQ,
        hypotheses: draftH,
        suggestion: iterationSuggestion?.text ?? '',
      })
      await loadProject(projectId)
      setEditing(false)
      setIterationSuggestion(null)
      setRevisionHint(null)
      setSaveMsg('✅ 设计已保存（版本 +1），可返回数据分析页重新分析')
    } catch (err: unknown) {
      setSaveMsg('❌ 保存失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  const setRqText = (i: number, text: string) =>
    setDraftRQ(prev => prev.map((q, idx) => (idx === i ? { ...q, text } : q)))
  const setHText = (i: number, statement: string) =>
    setDraftH(prev => prev.map((h, idx) => (idx === i ? { ...h, statement } : h)))

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            {/* issue #129：设计版本号徽章（V1/V2/V3…，保存/重跑后 +1） */}
            <span className="text-[10px] shrink-0 px-2.5 py-1 rounded-full border font-medium text-indigo-700 bg-indigo-50 border-indigo-200">
              设计版本 V{designVersion}
            </span>
            <StageActions
            stage={3}
            status={status}
            onRun={() => void exec({})}
            onApprove={approve}
            running={running}
            error={error}
            runLabel="开始设计"
          />
          </div>

          {/* issue #130：同行评审「触发修改」跳转过来的修改提示条 */}
          {revisionHint && !iterationSuggestion && (
            <div className="card p-4 !border-rose-200/80 bg-gradient-to-br from-rose-50/70 via-white to-white">
              <div className="flex items-start gap-3">
                <span className="text-lg shrink-0">👨‍⚖️</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-700 flex items-center flex-wrap gap-1.5">
                    来自同行评审的修改提示
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-600 border border-rose-200">评审意见</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-200">保存修改后 V{designVersion + 1}</span>
                  </p>
                  <p className="text-[11px] text-slate-600 mt-1.5 leading-relaxed">{revisionHint.text}</p>
                  <div className="flex gap-2 mt-2 flex-wrap">
                    <button onClick={startEdit} className="text-[11px] px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all">
                      ✏️ 按评审意见修改设计
                    </button>
                    <button onClick={() => setRevisionHint(null)} className="text-[11px] px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-all">
                      稍后处理
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* issue #129：迭代提示条（从数据分析页「去修改」跳转过来时展示 AI 建议） */}
          {iterationSuggestion && (
            <div className="card p-4 !border-amber-300/80 bg-gradient-to-br from-amber-50/80 via-white to-white">
              <div className="flex items-start gap-3">
                <span className="text-lg shrink-0">🔄</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-700 flex items-center flex-wrap gap-1.5">
                    迭代建议
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">来自第 {iterationSuggestion.iteration} 轮分析</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-200">当前 V{designVersion} · 保存后 V{designVersion + 1}</span>
                  </p>
                  <p className="text-[11px] text-slate-600 mt-1.5 leading-relaxed">{iterationSuggestion.text}</p>
                  <div className="flex gap-2 mt-2 flex-wrap">
                    <button onClick={startEdit} className="text-[11px] px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all">
                      ✏️ 按建议修改设计
                    </button>
                    <button onClick={() => setIterationSuggestion(null)} className="text-[11px] px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-all">
                      稍后处理
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />
          <StageSources output={rec?.output ?? null} />

          {questions.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="sec-label !mb-0">Research Question</h3>
                {/* 已确认产出物且非编辑态：提供「修改设计」入口（迭代闭环） */}
                {!editing && status === 'completed' && (
                  <button onClick={startEdit} className="text-[11px] px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-600 hover:bg-indigo-50 hover:border-indigo-300 transition-all">
                    ✏️ 修改设计（V{designVersion + 1}）
                  </button>
                )}
              </div>
              {questions.map((q, i) => (
                <div key={i} className="card p-4">
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 text-xs font-mono px-2 py-1 rounded bg-indigo-50 border border-indigo-200 text-indigo-600">{q.id}</span>
                    {editing ? (
                      <textarea
                        value={draftRQ[i]?.text ?? ''}
                        onChange={e => setRqText(i, e.target.value)}
                        rows={2}
                        className="input-field flex-1 !bg-slate-50 !rounded-lg !text-xs resize-none"
                      />
                    ) : (
                      <p className="text-sm text-slate-700 leading-relaxed">{q.text}</p>
                    )}
                  </div>
                </div>
              ))}
              {hypotheses.length > 0 && (
                <>
                  <h3 className="sec-label pt-2">Hypothesis</h3>
                  {hypotheses.map((h, i) => (
                    <div key={i} className="card p-4">
                      <div className="flex items-start gap-3">
                        <span className="shrink-0 text-xs font-mono px-2 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-600">{h.id}</span>
                        <div className="flex-1 min-w-0">
                          {editing ? (
                            <>
                              <textarea
                                value={draftH[i]?.statement ?? ''}
                                onChange={e => setHText(i, e.target.value)}
                                rows={2}
                                className="input-field w-full !bg-slate-50 !rounded-lg !text-xs resize-none"
                              />
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-50 text-slate-500 mt-1 inline-block">
                                {draftH[i]?.hypothesis_type === 'quantitative' ? '量化' : '质性'}
                              </span>
                            </>
                          ) : (
                            <>
                              <p className="text-sm text-slate-700 leading-relaxed">{h.statement}</p>
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-50 text-slate-500 mt-1 inline-block">{h.hypothesis_type === 'quantitative' ? '量化' : '质性'}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
              {quality && (
                <div className="card p-5 border-indigo-200">
                  <h3 className="sec-label !mb-3">AI 评价 · 问题质量检验</h3>
                  <div className="space-y-2">
                    <ScoreBar label="清晰度" value={quality.clarity} />
                    <ScoreBar label="创新性" value={quality.innovativeness} color="bg-emerald-500" />
                    <ScoreBar label="可操作性" value={quality.operability} color="bg-red-500" />
                  </div>
                  {quality.comments?.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {quality.comments.map((c, i) => <li key={i} className="text-[11px] text-slate-500">· {c}</li>)}
                    </ul>
                  )}
                </div>
              )}

              {/* issue #129：编辑态保存/取消操作条 */}
              {editing && (
                <div className="card p-4 !border-indigo-200 bg-indigo-50/40">
                  <p className="text-[11px] text-slate-600 leading-snug mb-2.5">
                    保存后设计版本将升级为 <span className="font-mono font-medium text-indigo-700">V{designVersion + 1}</span>，
                    回到数据分析页重新分析即可开启下一轮迭代（每次分析都会生成新的指标与诊断建议）。
                  </p>
                  <div className="flex items-center gap-2">
                    <button onClick={saveEdit} disabled={saving}
                      className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                      {saving ? '保存中…' : '💾 保存修改（V' + (designVersion + 1) + '）'}
                    </button>
                    <button onClick={cancelEdit} disabled={saving}
                      className="text-xs px-3.5 py-2 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700 disabled:opacity-40 transition-all">
                      取消
                    </button>
                    {saveMsg && <span className="text-[10px] text-slate-500">{saveMsg}</span>}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 无产出物但已有迭代记录：提示先完成设计 */}
          {questions.length === 0 && iterations.length > 0 && (
            <div className="card p-5 text-center border-amber-200/70">
              <p className="text-xs text-slate-500">
                🔄 已进入迭代闭环（已完成 {iterations.length} 轮）——请先运行研究设计，再按诊断建议修改并重新分析
              </p>
            </div>
          )}
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}
