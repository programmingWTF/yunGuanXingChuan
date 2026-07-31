/**
 * 云观星传 V2.0 — 研究工作台
 * 科技议题输入 + AI Scientist 工作流启动 + 实时进度 + 历史研究记录
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  conveneParliament, stopParliament, getParliamentStatus, getParliamentResult, getParliamentHistory,
  type PhaseProgress,
} from '../api'

/* ── 工作流阶段（展示用） ── */
const WORKFLOW_AGENTS = [
  { key: 'planner', label: 'Planner', zh: '研究规划', icon: '🧭' },
  { key: 'retriever', label: 'Retriever', zh: '知识检索', icon: '🔬' },
  { key: 'reasoner', label: 'Reasoner', zh: '跨文化推理', icon: '🎭' },
  { key: 'verifier', label: 'Verifier', zh: '证据校验', icon: '🔍' },
  { key: 'communicator', label: 'Communicator', zh: '传播策略', icon: '📋' },
]

const KB_SOURCES = [
  { name: '国家天文台知识库', desc: '论文 · 观测数据 · 任务档案', icon: '🔭', status: '已接入' },
  { name: '国际媒体传播库', desc: 'BBC · Reuters · Nature · 新华社', icon: '🌐', status: '已接入' },
  { name: '南航科研案例库', desc: '导师成果 · 优秀案例 · 课程成果', icon: '🎓', status: '已接入' },
]

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
    setPhase('running'); setStatusMsg('正在启动 AI Scientist 工作流...'); setProgress(null)
    try {
      const { task_id } = await conveneParliament(t, maxRounds, maxPipelineRounds)
      setStatusMsg('AI Scientist 已启动，任务运行中...'); saveRunning(task_id, t)
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

  const running = phase === 'running'

  return (
    <div className="space-y-7">
      {/* ═══ 指令台：议题输入 ═══ */}
      <section className="relative overflow-hidden rounded-2xl border border-astro-500/20 bg-gradient-to-br from-abyss-700/90 via-abyss-800/95 to-abyss-900/95 shadow-panel">
        {/* 装饰：轨道环 */}
        <div className="absolute -right-24 -top-24 w-80 h-80 pointer-events-none opacity-40">
          <div className="radar-ring inset-0" />
          <div className="radar-ring inset-8" style={{ animationDelay: '0.8s' }} />
          <div className="radar-ring inset-16" style={{ animationDelay: '1.6s' }} />
          <div className="absolute inset-0 animate-[radarSpin_14s_linear_infinite]">
            <div className="absolute top-1/2 left-1/2 w-1/2 h-px origin-left bg-gradient-to-r from-astro-400/60 to-transparent" />
          </div>
        </div>
        {/* 装饰：扫描线 */}
        {running && <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-astro-400/10 to-transparent animate-scanline pointer-events-none" />}

        <div className="relative px-10 pt-10 pb-9">
          <p className="sec-label mb-3">Cloud Astro Narrator · Mission Console</p>
          <h2 className="font-display text-[34px] leading-tight font-bold text-white mb-2">
            AI Scientist <span className="text-astro-300">for Science Communication</span>
          </h2>
          <p className="text-sm text-slate-400 mb-8 max-w-xl">
            输入科技议题，启动多智能体研究工作流 —— 三库检索 · 图谱构建 · 证据校验 · 国际传播分析
          </p>

          <form onSubmit={handleConvene} className="max-w-3xl">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-astro-400/70 text-sm">⌖</span>
                <input
                  type="text" value={topic} onChange={e => setTopic(e.target.value)}
                  placeholder="输入科技议题：JWST / FAST / 嫦娥七号 / 天问二号..."
                  disabled={running}
                  className="input-field pl-10 py-3.5 text-[15px] rounded-xl"
                />
              </div>
              <button type="submit" disabled={running || !topic.trim()}
                className="btn-primary px-8 py-3.5 text-[15px] rounded-xl whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? <><span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> 运行中</> : <>▶ 开始分析</>}
              </button>
              {running && (
                <button type="button" onClick={async () => {
                  const r = loadRunning(); if (r) await stopParliament(r.taskId)
                  stopPolling(); clearRunning(); setPhase('idle'); setStatusMsg(''); setProgress(null)
                }}
                  className="px-5 py-3.5 rounded-xl border border-flare-400/30 text-flare-400 text-sm hover:bg-flare-500/10 transition-colors whitespace-nowrap">
                  ■ 停止
                </button>
              )}
            </div>

            {/* 参数行 */}
            <div className="flex items-center gap-5 mt-4">
              <label className="flex items-center gap-2 text-xs text-slate-500">
                辩论轮次
                <select value={maxRounds} onChange={e => setMaxRounds(Number(e.target.value))} disabled={running}
                  className="appearance-none bg-abyss-900/90 border border-astro-500/20 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-astro-400/60 cursor-pointer [&>option]:bg-abyss-900">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} 轮</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-500">
                评测轮次
                <select value={maxPipelineRounds} onChange={e => setMaxPipelineRounds(Number(e.target.value))} disabled={running}
                  className="appearance-none bg-abyss-900/90 border border-astro-500/20 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-astro-400/60 cursor-pointer [&>option]:bg-abyss-900">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} 轮</option>)}
                </select>
              </label>
              {statusMsg && (
                <span className={`text-xs ${phase === 'error' ? 'text-flare-400' : 'text-astro-300'}`}>
                  {running && <span className="inline-block w-1.5 h-1.5 rounded-full bg-astro-400 animate-pulse mr-1.5" />}{statusMsg}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* Agent 流水线条 */}
        <div className="relative border-t border-white/[0.06] bg-abyss-950/50 px-10 py-4">
          <div className="flex items-center gap-0">
            {WORKFLOW_AGENTS.map((a, i) => (
              <div key={a.key} className="flex items-center">
                <div className={`flex items-center gap-2.5 px-4 py-2 rounded-lg transition-all duration-500 ${running ? 'bg-astro-500/10 shadow-[0_0_14px_rgba(12,184,232,0.12)]' : 'hover:bg-white/[0.04]'}`}
                  style={running ? { animationDelay: `${i * 0.3}s` } : undefined}>
                  <span className="text-lg">{a.icon}</span>
                  <div>
                    <p className="text-[11px] font-mono font-semibold text-astro-300 leading-none">{a.label}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{a.zh}</p>
                  </div>
                  {running && <span className="w-1.5 h-1.5 rounded-full bg-astro-400 animate-ping" />}
                </div>
                {i < WORKFLOW_AGENTS.length - 1 && (
                  <svg width="36" height="12" className="mx-1 shrink-0">
                    <line x1="0" y1="6" x2="30" y2="6" stroke="rgba(56,212,248,0.3)" strokeWidth="1.5" className={running ? 'flow-line' : ''} />
                    <path d="M30 2 L36 6 L30 10" fill="none" stroke="rgba(56,212,248,0.4)" strokeWidth="1.5" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ 实时进度 ═══ */}
      {running && progress && <ProgressTree progress={progress} />}

      {/* ═══ 三库知识源 + 统计 ═══ */}
      <section className="grid grid-cols-3 gap-5">
        {KB_SOURCES.map((kb, i) => (
          <div key={kb.name} className="panel panel-beam p-5 group cursor-default animate-rise" style={{ animationDelay: `${i * 0.08}s` }}>
            <div className="flex items-start justify-between mb-3">
              <span className="text-2xl group-hover:scale-110 transition-transform duration-300 inline-block">{kb.icon}</span>
              <span className="chip text-aurora-400 border-aurora-400/20 bg-aurora-400/5">● {kb.status}</span>
            </div>
            <h3 className="text-sm font-bold text-white mb-1">{kb.name}</h3>
            <p className="text-[11px] text-slate-500">{kb.desc}</p>
          </div>
        ))}
      </section>

      {/* ═══ 历史研究记录 ═══ */}
      <section className="panel panel-beam p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-bold text-white">历史研究记录</h3>
            <span className="sec-label">Research Log</span>
          </div>
          {summary && summary.total_runs > 0 && (
            <div className="flex gap-5 text-[11px] text-slate-500">
              <span>累计 <b className="stat-num text-white text-sm">{summary.total_runs}</b> 次</span>
              <span>平均 <b className="stat-num text-white text-sm">{summary.avg_rounds}</b> 轮</span>
              <span>平均评分 <b className="stat-num text-astro-300 text-sm">{summary.avg_score ?? '-'}</b></span>
            </div>
          )}
        </div>

        {history.length === 0 ? (
          <div className="text-center py-10">
            <div className="text-3xl mb-3 opacity-40">🛰️</div>
            <p className="text-sm text-slate-600">暂无历史研究记录 —— 输入议题，开始第一次 AI Scientist 研究任务</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {history.map((h, i) => (
              <button key={h.task_id} onClick={() => loadRecord(h.task_id)}
                className="w-full flex items-center justify-between p-4 rounded-xl bg-white/[0.02] hover:bg-astro-500/[0.06] border border-white/[0.05] hover:border-astro-500/25 transition-all duration-300 text-left group animate-rise"
                style={{ animationDelay: `${i * 0.05}s` }}>
                <div className="flex items-center gap-4">
                  <div className="w-9 h-9 rounded-lg bg-astro-500/10 border border-astro-500/20 flex items-center justify-center text-sm group-hover:shadow-[0_0_12px_rgba(12,184,232,0.25)] transition-shadow">◈</div>
                  <div>
                    <span className="text-white text-sm font-medium group-hover:text-astro-300 transition-colors">{h.topic}</span>
                    <span className="text-slate-600 text-xs ml-3 font-mono">{h.completed_at?.slice(0, 16).replace('T', ' ')}</span>
                  </div>
                </div>
                <div className="flex gap-2.5 text-xs items-center">
                  <span className="chip text-slate-400">{h.total_rounds} 轮辩论</span>
                  <span className="chip text-slate-400">{h.pass_rate}% 通过</span>
                  {h.avg_score && <span className="chip text-nova-400 border-nova-400/20 bg-nova-400/5">{h.avg_score} 分</span>}
                  <span className="text-astro-400/60 group-hover:text-astro-300 group-hover:translate-x-1 transition-all duration-300 font-medium">查看 →</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

/* ═══════════ 树状进度图 ═══════════ */
export function ProgressTree({ progress, readonly }: { progress: { phases: PhaseProgress[]; current_round: number; total_rounds: number; pipeline_round?: number }; readonly?: boolean }) {
  const [modal, setModal] = useState<{ title: string; content: string } | null>(null)

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
    <section className="panel panel-beam p-6">
      <div className="flex items-center gap-3 mb-6">
        <h3 className="text-sm font-bold text-white">{readonly ? 'AI Scientist 工作流回顾' : 'AI Scientist 实时工作流'}</h3>
        <span className="sec-label">Execution Trace</span>
        {!readonly && (
          <span className="ml-auto flex items-center gap-2 text-[11px] text-astro-300">
            <span className="w-2 h-2 rounded-full bg-astro-400 animate-ping" /> 执行中
          </span>
        )}
      </div>

      <div className="space-y-5">
        {progress.phases.map(phase => {
          const isDebate = phase.key === 'debate'
          const isPipeline = phase.key === 'pipeline'
          const done = phase.status === 'completed'
          const phaseRunning = phase.status === 'running'
          return (
            <div key={phase.key}>
              <div className="flex items-center gap-3 mb-2.5">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-base border-2 shrink-0 transition-all duration-500 ${
                  done ? 'bg-aurora-400/15 border-aurora-400/50 text-aurora-400' :
                  phaseRunning ? 'bg-astro-500/15 border-astro-400 text-astro-300 shadow-[0_0_14px_rgba(12,184,232,0.3)] animate-pulse' :
                  'bg-white/[0.03] border-slate-700 text-slate-600'
                }`}>{phase.icon}</div>
                <div>
                  <span className={`text-sm font-bold ${done ? 'text-aurora-400' : phaseRunning ? 'text-astro-300' : 'text-slate-500'}`}>{phase.label}</span>
                  {phase.message && <span className="text-xs text-slate-500 ml-2.5">{phase.message}</span>}
                </div>
              </div>

              {!isDebate && !isPipeline && (
                <div className="ml-4 pl-4 border-l border-white/10 space-y-1">
                  {(phase.sub_steps as typeof debateSubSteps || []).map(ss => (
                    <div key={ss.key} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                      className="flex items-center gap-2.5 py-1 cursor-pointer hover:bg-white/[0.04] rounded-md px-2 -mx-2 transition-colors">
                      <span className={`text-xs ${ss.status === 'completed' ? 'text-aurora-400' : ss.status === 'running' ? 'text-astro-300 animate-pulse' : 'text-slate-600'}`}>{ss.icon}</span>
                      <span className={`text-[11px] ${ss.status === 'completed' ? 'text-aurora-400/80' : ss.status === 'running' ? 'text-astro-300' : 'text-slate-600'}`}>{ss.label}</span>
                    </div>
                  ))}
                </div>
              )}

              {isDebate && (
                <div className="ml-4 space-y-3">
                  {debateRounds.map(({ round, steps }) => {
                    const isRoundDone = round < progress.current_round || done
                    const isRoundRunning = round === progress.current_round && phaseRunning
                    return (
                      <div key={round}>
                        <div className={`inline-flex items-center gap-1.5 mb-2 px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold ${
                          isRoundDone ? 'bg-aurora-400/10 text-aurora-400 border border-aurora-400/20' :
                          isRoundRunning ? 'bg-astro-500/10 text-astro-300 border border-astro-500/25' :
                          'bg-white/[0.03] text-slate-600 border border-white/[0.05]'
                        }`}>
                          ⚔ R{round}
                          {isRoundDone && <span>✓</span>}
                          {isRoundRunning && <span className="animate-pulse">●</span>}
                        </div>
                        <div className="pl-3 border-l border-white/10 space-y-2">
                          {steps.length > 0 ? steps.map((ss, i) => (
                            <div key={`${ss.key}-${i}`} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                              className="cursor-pointer hover:bg-white/[0.04] rounded-lg px-2.5 py-2 transition-colors">
                              <div className="flex items-center gap-2">
                                <span className={`text-xs ${ss.status === 'completed' ? 'text-aurora-400' : ss.status === 'running' ? 'text-astro-300 animate-pulse' : 'text-slate-600'}`}>{ss.icon}</span>
                                <span className={`text-[11px] font-medium ${ss.status === 'completed' ? 'text-aurora-400/80' : ss.status === 'running' ? 'text-astro-300' : 'text-slate-600'}`}>{ss.label}</span>
                                {ss.detail && <span className="text-[10px] text-slate-600">{ss.detail}</span>}
                              </div>
                              {ss.status === 'completed' && ss.full_content && (
                                <p className={`mt-1.5 text-[11px] text-slate-400 leading-relaxed pl-5 whitespace-pre-wrap ${readonly ? '' : 'line-clamp-3'}`}>
                                  {readonly ? ss.full_content : (ss.full_content.length > 200 ? ss.full_content.slice(0, 200) + '...' : ss.full_content)}
                                </p>
                              )}
                            </div>
                          )) : (
                            <div className="text-[10px] text-slate-600 py-1">等待中...</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  {debateRounds.length === 0 && <div className="text-xs text-slate-600 py-2">等待辩论开始...</div>}
                </div>
              )}

              {isPipeline && (
                <div className="ml-4 space-y-3">
                  <div className="pl-4 border-l border-white/10 space-y-1">
                    {standaloneSteps.map(ss => (
                      <div key={ss.key} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                        className="flex items-center gap-2.5 py-1 cursor-pointer hover:bg-white/[0.04] rounded-md px-2 -mx-2 transition-colors">
                        <span className={`text-xs ${ss.status === 'completed' ? 'text-aurora-400' : ss.status === 'running' ? 'text-astro-300 animate-pulse' : 'text-slate-600'}`}>{ss.icon}</span>
                        <span className={`text-[11px] ${ss.status === 'completed' ? 'text-aurora-400/80' : ss.status === 'running' ? 'text-astro-300' : 'text-slate-600'}`}>{ss.label}</span>
                      </div>
                    ))}
                  </div>
                  {pipelineRounds.length > 0 && (
                    <div className="flex items-start gap-3 overflow-x-auto pb-2">
                      {pipelineRounds.map(({ round, steps }) => {
                        const allDone = steps.every(s => s.status === 'completed')
                        const anyRunning = steps.some(s => s.status === 'running')
                        return (
                          <div key={round} className="shrink-0">
                            <div className={`flex items-center gap-1.5 mb-2 px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold ${
                              allDone ? 'bg-aurora-400/10 text-aurora-400 border border-aurora-400/20' :
                              anyRunning ? 'bg-astro-500/10 text-astro-300 border border-astro-500/25' :
                              'bg-white/[0.03] text-slate-600 border border-white/[0.05]'
                            }`}>
                              🔄 R{round}
                              {allDone && <span>✓</span>}
                              {anyRunning && <span className="animate-pulse">●</span>}
                            </div>
                            <div className="pl-2.5 border-l border-white/10 space-y-1 min-w-[180px]">
                              {steps.map((ss, i) => (
                                <div key={`${ss.key}-${i}`} onClick={() => openModal(ss.label, ss.full_content, ss.detail)}
                                  className="flex items-center gap-2 py-1 cursor-pointer hover:bg-white/[0.04] rounded-md px-1.5 transition-colors">
                                  <span className={`text-xs ${ss.status === 'completed' ? 'text-aurora-400' : ss.status === 'running' ? 'text-astro-300 animate-pulse' : 'text-slate-600'}`}>{ss.icon}</span>
                                  <span className={`text-[11px] ${ss.status === 'completed' ? 'text-aurora-400/80' : ss.status === 'running' ? 'text-astro-300' : 'text-slate-600'}`}>{ss.label}</span>
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

      {(progress.current_round > 0 || (progress.pipeline_round || 0) > 0) && (
        <div className="mt-5 pt-4 border-t border-white/[0.06] text-xs text-slate-500 font-mono">
          {(progress.pipeline_round || 0) > 0
            ? `▸ PIPELINE ROUND ${progress.pipeline_round} — 校验 + 策略迭代`
            : `▸ DEBATE ROUND ${progress.current_round} — 多智能体辩论`}
        </div>
      )}

      {modal && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in" onClick={() => setModal(null)}>
          <div className="panel max-w-2xl w-full mx-4 max-h-[72vh] flex flex-col border-astro-500/30" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08]">
              <h4 className="text-sm font-bold text-white">{modal.title}</h4>
              <button onClick={() => setModal(null)} className="text-slate-500 hover:text-white text-lg leading-none transition-colors">✕</button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <pre className="text-xs text-slate-300 whitespace-pre-wrap break-words font-mono leading-relaxed">{modal.content}</pre>
            </div>
          </div>
        </div>,
        document.body
      )}
    </section>
  )
}
