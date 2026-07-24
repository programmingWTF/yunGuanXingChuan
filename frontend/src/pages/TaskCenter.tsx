/**
 * 云观星传 - 任务中心
 * 任务输入 + 实时进度 + 历史任务管理
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  conveneParliament, stopParliament, getParliamentStatus, getParliamentResult, getParliamentHistory,
  type PhaseProgress,
} from '../api'

export default function TaskCenter() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [maxRounds, setMaxRounds] = useState(5)
  const [maxPipelineRounds, setMaxPipelineRounds] = useState(3)
  const [phase, setPhase] = useState<'idle' | 'running' | 'error'>('idle')
  const [statusMsg, setStatusMsg] = useState('')
  const [progress, setProgress] = useState<{ phases: PhaseProgress[]; current_round: number; total_rounds: number; pipeline_round: number } | null>(null)
  const [history, setHistory] = useState<{ task_id: string; topic: string; total_rounds: number; motion_count: number; vote_count: number; passed_count: number; pass_rate: number; minority_count: number; avg_score: number | null; completed_at: string }[]>([])
  const [summary, setSummary] = useState<{ total_runs: number; avg_rounds: number; avg_motions: number; avg_minority: number; avg_score: number | null; total_votes: number } | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const TASK_KEY = 'ygxc_parliament_task'
  const saveRunning = (taskId: string, t: string) => localStorage.setItem(TASK_KEY, JSON.stringify({ taskId, topic: t }))
  const clearRunning = () => localStorage.removeItem(TASK_KEY)
  const loadRunning = (): { taskId: string; topic: string } | null => {
    try { const r = localStorage.getItem(TASK_KEY); return r ? JSON.parse(r) : null } catch { return null }
  }

  const stopPolling = useCallback(() => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
  }, [])

  const loadHistory = useCallback(() => {
    getParliamentHistory().then(({ history, summary }) => { setHistory(history); setSummary(summary) }).catch(() => {})
  }, [])

  const resumePolling = useCallback((taskId: string, t: string) => {
    stopPolling(); setTopic(t); setPhase('running'); setStatusMsg('恢复任务连接中...'); saveRunning(taskId, t)
    let notFoundCount = 0
    pollingRef.current = setInterval(async () => {
      try {
        const status = await getParliamentStatus(taskId)
        if (status.status === 'not_found') {
          notFoundCount++
          if (notFoundCount >= 2) { stopPolling(); clearRunning(); setPhase('idle'); setStatusMsg(''); setProgress(null) }
          return
        }
        notFoundCount = 0
        if (status.progress) setProgress(status.progress)
        if (status.status === 'completed' && status.has_result) {
          stopPolling(); clearRunning()
          const result = await getParliamentResult(taskId)
          setPhase('idle'); setStatusMsg(''); setProgress(null)
          if (result) { localStorage.setItem('ygxc_latest_parliament', JSON.stringify(result)); navigate('/parliament') }
          loadHistory()
        } else if (status.status === 'stopped' || status.status.startsWith('error')) {
          stopPolling(); clearRunning(); setPhase('idle'); setStatusMsg(status.status === 'stopped' ? '' : status.status)
        }
      } catch { /* keep polling */ }
    }, 2000)
  }, [stopPolling, loadHistory, navigate])

  useEffect(() => { loadHistory(); const r = loadRunning(); if (r) resumePolling(r.taskId, r.topic) }, [resumePolling])
  useEffect(() => () => stopPolling(), [stopPolling])

  const handleConvene = async (e: React.FormEvent) => {
    e.preventDefault(); const t = topic.trim(); if (!t) return
    setPhase('running'); setStatusMsg('正在召集议会...'); setProgress(null)
    try {
      const { task_id } = await conveneParliament(t, maxRounds, maxPipelineRounds)
      setStatusMsg('议会已召集，任务运行中...'); saveRunning(task_id, t)
      pollingRef.current = setInterval(async () => {
        try {
          const status = await getParliamentStatus(task_id)
          if (status.progress) setProgress(status.progress)
          if (status.status === 'completed' && status.has_result) {
            stopPolling(); clearRunning()
            const result = await getParliamentResult(task_id)
            setPhase('idle'); setStatusMsg(''); setProgress(null)
            if (result) { localStorage.setItem('ygxc_latest_parliament', JSON.stringify(result)); navigate('/parliament') }
            loadHistory()
          } else if (status.status.startsWith('error')) {
            stopPolling(); clearRunning(); setPhase('error'); setStatusMsg(status.status)
          }
        } catch { /* keep polling */ }
      }, 2000)
    } catch (err) {
      setPhase('error'); setStatusMsg(err instanceof Error ? err.message : '无法连接后端')
    }
  }

  const loadRecord = async (taskId: string) => {
    try {
      const r = await getParliamentResult(taskId)
      if (r) { localStorage.setItem('ygxc_latest_parliament', JSON.stringify(r)); navigate('/parliament') }
    } catch { setStatusMsg('加载失败') }
  }

  return (
    <div className="space-y-5">
      {/* ===== 任务输入 ===== */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
          🚀 新建任务 <span className="text-xs text-gray-400 font-normal">Task Center</span>
        </h2>
        <form onSubmit={handleConvene} className="space-y-4">
          {/* 议题输入 */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">科技议题</label>
            <input type="text" value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="输入议题，如：嫦娥七号月球南极探测、天问二号小行星采样..."
              disabled={phase === 'running'}
              className="w-full bg-[#0d1f3c]/80 border border-star-blue/25 rounded-xl px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-star-blue/70 focus:ring-1 focus:ring-star-blue/30 transition-all disabled:opacity-50" />
          </div>
          {/* 参数选择 */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400">辩论轮次</label>
              <select value={maxRounds} onChange={e => setMaxRounds(Number(e.target.value))} disabled={phase === 'running'}
                className="appearance-none bg-[#0d1f3c]/80 border border-star-blue/25 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-star-blue/70 focus:ring-1 focus:ring-star-blue/30 transition-all disabled:opacity-50 cursor-pointer [&>option]:bg-[#0a1628] [&>option]:text-white">
                {Array.from({ length: 10 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} 轮</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400">评测轮次</label>
              <select value={maxPipelineRounds} onChange={e => setMaxPipelineRounds(Number(e.target.value))} disabled={phase === 'running'}
                className="appearance-none bg-[#0d1f3c]/80 border border-star-blue/25 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-star-blue/70 focus:ring-1 focus:ring-star-blue/30 transition-all disabled:opacity-50 cursor-pointer [&>option]:bg-[#0a1628] [&>option]:text-white">
                {Array.from({ length: 10 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} 轮</option>)}
              </select>
            </div>
            <div className="flex-1" />
            <button type="submit" disabled={phase === 'running' || !topic.trim()}
              className="btn-primary px-6 py-2.5 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed">
              {phase === 'running' ? '⏳ 运行中...' : '🏛️ 启动认知议会'}
            </button>
            {phase === 'running' && (
              <button type="button" onClick={async () => {
                const r = loadRunning(); if (r) await stopParliament(r.taskId)
                stopPolling(); clearRunning(); setPhase('idle'); setStatusMsg(''); setProgress(null)
              }}
                className="px-4 py-2.5 rounded-lg border border-red-500/30 text-red-400 text-sm hover:bg-red-500/10 transition-colors whitespace-nowrap">
                ⏹ 停止
              </button>
            )}
          </div>
        </form>
        {statusMsg && <div className={`mt-3 text-sm ${phase === 'error' ? 'text-red-400' : 'text-star-blue'}`}>{statusMsg}</div>}
      </div>

      {/* ===== 实时进度 ===== */}
      {phase === 'running' && progress && <ProgressTree progress={progress} />}

      {/* ===== 历史任务 ===== */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-gray-200 flex items-center gap-2">📜 历史任务</h3>
          {summary && summary.total_runs > 0 && (
            <div className="flex gap-4 text-[11px] text-gray-500">
              <span>累计 <b className="text-white">{summary.total_runs}</b> 次</span>
              <span>平均 <b className="text-white">{summary.avg_rounds}</b> 轮</span>
              <span>平均评分 <b className="text-star-blue">{summary.avg_score ?? '-'}</b></span>
            </div>
          )}
        </div>
        {history.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-sm">暂无历史任务</div>
        ) : (
          <div className="space-y-2">
            {history.map(h => (
              <button key={h.task_id} onClick={() => loadRecord(h.task_id)}
                className="w-full flex items-center justify-between p-3.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.07] border border-white/5 hover:border-star-blue/20 transition-all text-left group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-star-blue/10 flex items-center justify-center text-sm group-hover:bg-star-blue/20 transition-colors">🏛️</div>
                  <div>
                    <span className="text-white text-sm font-medium">{h.topic}</span>
                    <span className="text-gray-600 text-xs ml-2">{h.completed_at?.slice(0, 16).replace('T', ' ')}</span>
                  </div>
                </div>
                <div className="flex gap-3 text-xs text-gray-500 items-center">
                  <span className="px-2 py-0.5 rounded-md bg-white/5">{h.total_rounds}轮</span>
                  <span className="px-2 py-0.5 rounded-md bg-white/5">{h.pass_rate}%通过</span>
                  {h.avg_score && <span className="px-2 py-0.5 rounded-md bg-star-blue/10 text-star-blue">{h.avg_score}分</span>}
                  <span className="text-star-blue/60 group-hover:text-star-blue transition-colors">查看 →</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ========== 树状进度图 ========== */
export function ProgressTree({ progress, readonly }: { progress: { phases: PhaseProgress[]; current_round: number; total_rounds: number; pipeline_round?: number }; readonly?: boolean }) {
  const [modal, setModal] = useState<{ title: string; content: string } | null>(null)

  // === 辩论轮次分组 ===
  const debatePhase = progress.phases.find(p => p.key === 'debate')
  const debateSubSteps = (debatePhase?.sub_steps || []) as { key: string; status: string; label: string; icon: string; detail?: string; full_content?: string }[]
  const debateRounds: { round: number; steps: typeof debateSubSteps }[] = []
  const roundMap = new Map<number, typeof debateSubSteps>()
  for (const ss of debateSubSteps) {
    const match = ss.key.match(/R(\d+)/)
    const rnum = match ? parseInt(match[1], 10) : (progress.current_round || 1)
    if (!roundMap.has(rnum)) roundMap.set(rnum, [])
    roundMap.get(rnum)!.push(ss)
  }
  for (const rnum of [...roundMap.keys()].sort((a, b) => a - b)) {
    debateRounds.push({ round: rnum, steps: roundMap.get(rnum)! })
  }
  if (!roundMap.has(progress.current_round) && progress.current_round > 0 && !readonly) {
    debateRounds.push({ round: progress.current_round, steps: [] })
    debateRounds.sort((a, b) => a.round - b.round)
  }

  // === Pipeline 轮次分组 ===
  const pipelinePhase = progress.phases.find(p => p.key === 'pipeline')
  const pipelineSubSteps = (pipelinePhase?.sub_steps || []) as { key: string; status: string; label: string; icon: string; detail?: string; full_content?: string }[]
  const standaloneSteps = pipelineSubSteps.filter(ss => ss.key === 'search' || ss.key === 'verification')
  const roundSteps = pipelineSubSteps.filter(ss => ss.key !== 'search' && ss.key !== 'verification')
  const pipelineRoundMap = new Map<number, typeof roundSteps>()
  for (const ss of roundSteps) {
    const match = ss.key.match(/r(\d+)/)
    const rnum = match ? parseInt(match[1], 10) : 1
    if (!pipelineRoundMap.has(rnum)) pipelineRoundMap.set(rnum, [])
    pipelineRoundMap.get(rnum)!.push(ss)
  }
  const pipelineRounds: { round: number; steps: typeof roundSteps }[] = []
  for (const rnum of [...pipelineRoundMap.keys()].sort((a, b) => a - b)) {
    pipelineRounds.push({ round: rnum, steps: pipelineRoundMap.get(rnum)! })
  }

  const openModal = (title: string, content?: string, detail?: string) => {
    setModal({ title, content: content || detail || '（该步骤暂无详细输出）' })
  }

  return (
    <div className="glass-card p-6">
      <h3 className="text-base font-bold text-white mb-5 flex items-center gap-2">
        🌳 {readonly ? '分析流程回顾' : '实时分析流程'}
        {!readonly && <span className="text-xs text-star-blue animate-pulse">● 进行中</span>}
      </h3>
      <div className="space-y-4">
        {progress.phases.map(phase => {
          const isDebate = phase.key === 'debate'
          const isPipeline = phase.key === 'pipeline'
          const done = phase.status === 'completed'
          const running = phase.status === 'running'
          return (
            <div key={phase.key}>
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-base border-2 shrink-0 ${
                  done ? 'bg-green-500/20 border-green-500/50 text-green-400' :
                  running ? 'bg-star-blue/20 border-star-blue text-star-blue animate-pulse' :
                  'bg-white/5 border-gray-700 text-gray-600'
                }`}>{phase.icon}</div>
                <div>
                  <span className={`text-sm font-bold ${done ? 'text-green-400' : running ? 'text-star-blue' : 'text-gray-500'}`}>{phase.label}</span>
                  {phase.message && <span className="text-xs text-gray-500 ml-2">{phase.message}</span>}
                </div>
                {running && <span className="text-star-blue text-xs ml-auto animate-pulse">进行中...</span>}
              </div>

              {/* === 开幕阶段：垂直列表 === */}
              {!isDebate && !isPipeline && (
                <div className="ml-4 pl-4 border-l-2 border-white/10 space-y-1">
                  {(phase.sub_steps as typeof debateSubSteps || []).map(ss => (
                    <div key={ss.key} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                      className="flex items-center gap-2 py-0.5 cursor-pointer hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
                      <span className={`text-xs ${ss.status === 'completed' ? 'text-green-400' : ss.status === 'running' ? 'text-star-blue animate-pulse' : 'text-gray-600'}`}>{ss.icon}</span>
                      <span className={`text-[11px] ${ss.status === 'completed' ? 'text-green-400/80' : ss.status === 'running' ? 'text-star-blue' : 'text-gray-600'}`}>{ss.label}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* === 辩论阶段：横向多轮 === */}
              {isDebate && (
                <div className="ml-4 flex items-start gap-3 overflow-x-auto pb-2">
                  {debateRounds.map(({ round, steps }) => {
                    const isRoundDone = round < progress.current_round || done
                    const isRoundRunning = round === progress.current_round && running
                    return (
                      <div key={round} className="shrink-0">
                        <div className={`flex items-center gap-1.5 mb-1.5 px-2 py-1 rounded-md text-[11px] font-medium ${
                          isRoundDone ? 'bg-green-500/10 text-green-400' :
                          isRoundRunning ? 'bg-star-blue/10 text-star-blue' :
                          'bg-white/5 text-gray-600'
                        }`}>
                          <span>⚔️</span> R{round}
                          {isRoundDone && <span className="text-green-500">✓</span>}
                          {isRoundRunning && <span className="animate-pulse">●</span>}
                        </div>
                        <div className="pl-2 border-l-2 border-white/10 space-y-1 min-w-[160px]">
                          {steps.length > 0 ? steps.map((ss, i) => (
                            <div key={`${ss.key}-${i}`} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                              className="flex items-center gap-2 py-0.5 cursor-pointer hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
                              <span className={`text-xs ${ss.status === 'completed' ? 'text-green-400' : ss.status === 'running' ? 'text-star-blue animate-pulse' : 'text-gray-600'}`}>{ss.icon}</span>
                              <span className={`text-[11px] ${ss.status === 'completed' ? 'text-green-400/80' : ss.status === 'running' ? 'text-star-blue' : 'text-gray-600'}`}>{ss.label}</span>
                            </div>
                          )) : (
                            <div className="text-[10px] text-gray-600 py-1">等待中...</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  {debateRounds.length === 0 && (
                    <div className="text-xs text-gray-600 py-2">等待辩论开始...</div>
                  )}
                </div>
              )}

              {/* === Pipeline 阶段：搜索/校验独立 + 策略/评测横向多轮 === */}
              {isPipeline && (
                <div className="ml-4 space-y-3">
                  {/* 搜索 + 校验 独立显示 */}
                  <div className="pl-4 border-l-2 border-white/10 space-y-1">
                    {standaloneSteps.map(ss => (
                      <div key={ss.key} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                        className="flex items-center gap-2 py-0.5 cursor-pointer hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
                        <span className={`text-xs ${ss.status === 'completed' ? 'text-green-400' : ss.status === 'running' ? 'text-star-blue animate-pulse' : 'text-gray-600'}`}>{ss.icon}</span>
                        <span className={`text-[11px] ${ss.status === 'completed' ? 'text-green-400/80' : ss.status === 'running' ? 'text-star-blue' : 'text-gray-600'}`}>{ss.label}</span>
                      </div>
                    ))}
                  </div>
                  {/* 策略 + 评测 横向多轮 */}
                  {pipelineRounds.length > 0 && (
                    <div className="flex items-start gap-3 overflow-x-auto pb-2">
                      {pipelineRounds.map(({ round, steps }) => {
                        const allDone = steps.every(s => s.status === 'completed')
                        const anyRunning = steps.some(s => s.status === 'running')
                        return (
                          <div key={round} className="shrink-0">
                            <div className={`flex items-center gap-1.5 mb-1.5 px-2 py-1 rounded-md text-[11px] font-medium ${
                              allDone ? 'bg-green-500/10 text-green-400' :
                              anyRunning ? 'bg-star-blue/10 text-star-blue' :
                              'bg-white/5 text-gray-600'
                            }`}>
                              <span>🔄</span> R{round}
                              {allDone && <span className="text-green-500">✓</span>}
                              {anyRunning && <span className="animate-pulse">●</span>}
                            </div>
                            <div className="pl-2 border-l-2 border-white/10 space-y-1 min-w-[180px]">
                              {steps.map((ss, i) => (
                                <div key={`${ss.key}-${i}`} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                                  className="flex items-center gap-2 py-0.5 cursor-pointer hover:bg-white/5 rounded px-1 -mx-1 transition-colors">
                                  <span className={`text-xs ${ss.status === 'completed' ? 'text-green-400' : ss.status === 'running' ? 'text-star-blue animate-pulse' : 'text-gray-600'}`}>{ss.icon}</span>
                                  <span className={`text-[11px] ${ss.status === 'completed' ? 'text-green-400/80' : ss.status === 'running' ? 'text-star-blue' : 'text-gray-600'}`}>{ss.label}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {/* 底部状态文字 */}
      {(progress.current_round > 0 || (progress.pipeline_round || 0) > 0) && (
        <div className="mt-4 text-xs text-gray-500">
          {(progress.pipeline_round || 0) > 0
            ? `当前: Pipeline 第 ${progress.pipeline_round} 轮校验+策略`
            : `当前: 第 ${progress.current_round} 轮辩论`}
        </div>
      )}

      {/* === 弹窗：显示 LLM 完整返回（Portal 渲染到 body 确保 viewport 居中） === */}
      {modal && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setModal(null)}>
          <div className="bg-[#0d1f3c] border border-star-blue/30 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
              <h4 className="text-sm font-bold text-white">{modal.title}</h4>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-white text-lg leading-none">&times;</button>
            </div>
            <div className="p-5 overflow-y-auto flex-1">
              <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words font-mono leading-relaxed">{modal.content}</pre>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
