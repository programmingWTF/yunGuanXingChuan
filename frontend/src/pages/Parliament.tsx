/**
 * 云观星传 V2.0 — AI Scientist 工作流结果页
 * 多智能体辩论记录 · 表决 · 策略 · 评分
 */
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { DeliberationTranscript, FinalReport } from '../api'
import { ProgressTree } from './TaskCenter'

const AGENT_META: Record<string, { label: string; role: string; color: string }> = {
  scientist: { label: 'Retriever', role: '知识检索', color: 'text-astro-300 border-astro-500/30 bg-astro-500/10' },
  skeptic: { label: 'Verifier', role: '证据校验', color: 'text-flare-400 border-flare-400/30 bg-flare-500/10' },
  humanist: { label: 'Reasoner', role: '跨文化推理', color: 'text-purple-300 border-purple-400/30 bg-purple-500/10' },
  strategist: { label: 'Communicator', role: '传播策略', color: 'text-nova-400 border-nova-400/30 bg-nova-400/10' },
  evaluator: { label: 'Planner', role: '研究规划', color: 'text-aurora-400 border-aurora-400/30 bg-aurora-400/10' },
  speaker: { label: '议长', role: '主持裁定', color: 'text-slate-300 border-slate-500/30 bg-slate-500/10' },
}
const STANCE_STYLES: Record<string, string> = {
  support: 'text-aurora-400', oppose: 'text-flare-400', amend: 'text-nova-400',
  question: 'text-purple-300', clarify: 'text-astro-300',
}
const STANCE_ICONS: Record<string, string> = {
  support: '▲', oppose: '▼', amend: '✎', question: '?', clarify: '◦',
}

export default function Parliament() {
  const [transcript, setTranscript] = useState<DeliberationTranscript | null>(null)
  const [progressSnapshot, setProgressSnapshot] = useState<{ phases: any[]; current_round: number; total_rounds: number; pipeline_round?: number } | null>(null)
  const [expandedRound, setExpandedRound] = useState<number | null>(1)
  const [expandedSpeaker, setExpandedSpeaker] = useState<string | null>(null)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('ygxc_latest_parliament')
      if (raw) {
        const data = JSON.parse(raw)
        setTranscript(data)
        if (data.progress_snapshot) setProgressSnapshot(data.progress_snapshot)
      }
    } catch { /* ignore */ }
  }, [])

  if (!transcript) {
    return (
      <div className="panel p-16 text-center">
        <div className="text-5xl mb-5 opacity-50">⬡</div>
        <h3 className="text-lg font-bold text-white mb-2">AI Scientist 工作流</h3>
        <p className="text-sm text-slate-500 mb-7">暂无工作流结果 —— 请先在研究工作台启动分析任务</p>
        <Link to="/" className="btn-primary inline-flex px-7 py-3">◈ 前往研究工作台</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {progressSnapshot && progressSnapshot.phases && (
        <ProgressTree progress={progressSnapshot} readonly />
      )}
      <ResultView transcript={transcript} expandedRound={expandedRound} expandedSpeaker={expandedSpeaker}
        onToggleRound={r => setExpandedRound(expandedRound === r ? null : r)}
        onToggleSpeaker={s => { if (s === null || s === expandedSpeaker) setExpandedSpeaker(null); else setExpandedSpeaker(s) }} />
    </div>
  )
}

/* ═══════════ 结果视图 ═══════════ */
function ResultView({ transcript: t, expandedRound, expandedSpeaker, onToggleRound, onToggleSpeaker }: {
  transcript: DeliberationTranscript
  expandedRound: number | null; expandedSpeaker: string | null
  onToggleRound: (r: number) => void; onToggleSpeaker: (s: string | null) => void
}) {
  const votes = t.votes; const rounds = t.rounds; const minority = t.minority_opinions; const fs = t.final_strategies
  const passRate = votes.length ? Math.round(votes.filter(v => v.result === 'passed').length / votes.length * 100) : 0

  return (
    <div className="space-y-6">
      {/* 最终总结报告 */}
      {t.final_report && <SummaryCard report={t.final_report} />}

      {/* 概览统计 */}
      <section className="panel panel-beam p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="sec-label mb-1">Deliberation Record</p>
            <h3 className="text-lg font-bold text-white">工作流记录：{t.topic}</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">{t.started_at?.slice(11, 19)} → {t.completed_at?.slice(11, 19)}</span>
        </div>
        <div className="grid grid-cols-5 gap-4">
          {[
            { l: '辩论轮次', v: t.total_rounds, c: 'text-astro-300' },
            { l: '动议数', v: t.motions.length, c: 'text-white' },
            { l: '表决数', v: votes.length, c: 'text-white' },
            { l: '少数派意见', v: minority.length, c: 'text-nova-400' },
            { l: '通过率', v: `${passRate}%`, c: passRate >= 60 ? 'text-aurora-400' : 'text-nova-400' },
          ].map(m => (
            <div key={m.l} className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4 text-center hover:border-astro-500/25 transition-colors">
              <div className={`stat-num text-2xl ${m.c}`}>{m.v}</div>
              <div className="text-[10px] text-slate-500 mt-1">{m.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 表决结果 */}
      {votes.length > 0 && (
        <section className="panel panel-beam p-6">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">表决结果 <span className="sec-label">Voting</span></h3>
          <div className="space-y-3">
            {votes.map(v => (
              <div key={v.motion_id} className="flex items-center gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-white/10 transition-colors">
                <span className={`text-lg ${v.result === 'passed' ? 'text-aurora-400' : v.result === 'rejected' ? 'text-flare-400' : 'text-nova-400'}`}>
                  {v.result === 'passed' ? '✓' : v.result === 'rejected' ? '✗' : '✎'}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-mono text-white">{v.motion_id}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-md font-medium ${v.result === 'passed' ? 'bg-aurora-400/10 text-aurora-400 border border-aurora-400/20' : 'bg-nova-400/10 text-nova-400 border border-nova-400/20'}`}>{v.result}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden flex">
                      <div className="h-full bg-aurora-400/70 transition-all duration-700" style={{ width: `${v.weighted_yes * 100}%` }} />
                      <div className="h-full bg-flare-400/60 transition-all duration-700" style={{ width: `${v.weighted_no * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 w-10 text-right">{(v.weighted_yes * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex gap-1.5">
                  {Object.entries(v.votes).map(([a, vo]) => {
                    const meta = AGENT_META[a]
                    return <span key={a} title={`${meta?.label || a}: ${vo}`} className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] border ${meta?.color || ''}`}>{vo === 'yes' ? '✓' : vo === 'no' ? '✗' : '–'}</span>
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 联网搜索来源 */}
      {fs?.search_sources && fs.search_sources.length > 0 && (
        <section className="panel p-5">
          <h3 className="text-xs font-bold text-slate-400 mb-3">🌐 联网搜索来源 <span className="font-mono text-slate-600">({fs.search_sources.length})</span></h3>
          <div className="flex flex-wrap gap-2">
            {fs.search_sources.slice(0, 10).map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-astro-500/[0.08] border border-white/[0.07] hover:border-astro-500/30 transition-all text-[11px] text-slate-300 max-w-[300px] group">
                <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${s.source === 'TavilySearch' ? 'bg-astro-400' : 'bg-purple-400'}`} />
                <span className="truncate group-hover:text-astro-300 transition-colors">{s.title || s.url}</span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* 辩论轮次 */}
      <section className="space-y-3">
        <div className="flex items-center gap-3 px-1">
          <h3 className="text-sm font-bold text-white">辩论轮次</h3>
          <span className="sec-label">Debate Rounds</span>
        </div>
        {rounds.map(r => (
          <div key={r.round_id} className="panel overflow-hidden">
            <button onClick={() => onToggleRound(r.round_id)}
              className="w-full flex items-center justify-between p-5 hover:bg-white/[0.03] transition-colors">
              <div className="flex items-center gap-4">
                <span className="w-9 h-9 rounded-full bg-astro-500/15 border border-astro-500/30 flex items-center justify-center text-sm font-mono font-bold text-astro-300">{r.round_id}</span>
                <div className="text-left">
                  <div className="text-sm text-white font-medium">{r.topic}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5 font-mono">{r.speeches.length} 条发言 · 权重 {Object.entries(r.speaker_weights).map(([k, v]) => `${AGENT_META[k]?.label || k} ${(v * 100).toFixed(0)}%`).join(' / ')}</div>
                </div>
              </div>
              <span className="text-slate-600 text-xs">{expandedRound === r.round_id ? '▲ 收起' : '▼ 展开'}</span>
            </button>
            {expandedRound === r.round_id && (
              <div className="px-5 pb-5 space-y-3 border-t border-white/[0.05] animate-fade-in">
                {r.speaker_rationale && (
                  <div className="mt-4 p-3 rounded-lg bg-astro-500/[0.06] border border-astro-500/20">
                    <span className="text-[10px] text-astro-300 font-semibold font-mono">SPEAKER RATIONALE · </span>
                    <span className="text-xs text-slate-300">{r.speaker_rationale}</span>
                  </div>
                )}
                {r.speeches.map((s, i) => {
                  const key = `${r.round_id}-${s.speaker}-${i}`
                  const meta = AGENT_META[s.speaker]
                  return (
                    <div key={key} className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-white/10 transition-colors">
                      <div className="flex items-center gap-3 mb-2">
                        <span className={`text-[11px] font-mono font-semibold px-2.5 py-1 rounded-md border ${meta?.color || 'text-slate-300 border-slate-600 bg-slate-700/30'}`}>
                          {meta?.label || s.speaker}
                        </span>
                        <span className="text-[10px] text-slate-600">{meta?.role}</span>
                        <span className={`text-[11px] font-medium ${STANCE_STYLES[s.stance] || STANCE_STYLES.clarify}`}>
                          {STANCE_ICONS[s.stance] || '◦'} {s.stance}
                        </span>
                        <button onClick={() => onToggleSpeaker(expandedSpeaker === key ? null : key)}
                          className="text-[10px] text-astro-400/60 hover:text-astro-300 ml-auto transition-colors">
                          {expandedSpeaker === key ? '收起' : '查看全文'}
                        </button>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {expandedSpeaker === key ? s.content : s.content.slice(0, 160) + (s.content.length > 160 ? '...' : '')}
                      </p>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </section>

      {/* 少数派意见 */}
      {minority.length > 0 && (
        <section className="panel p-6 border-l-4 border-l-nova-400/60">
          <h3 className="text-sm font-bold text-nova-400 mb-4">少数派意见 <span className="font-mono text-xs text-nova-400/60">({minority.length})</span></h3>
          <div className="space-y-3">
            {minority.map((mo, i) => {
              const meta = AGENT_META[mo.agent]
              return (
                <div key={i} className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
                  <div className="flex items-center gap-3 mb-1.5">
                    <span className={`text-[11px] font-mono font-semibold px-2.5 py-1 rounded-md border ${meta?.color || ''}`}>{meta?.label || mo.agent}</span>
                    <span className="text-[10px] font-mono text-slate-600">→ {mo.motion_id}</span>
                  </div>
                  <p className="text-sm text-slate-300">{mo.objection}</p>
                  {mo.why_overruled && <p className="text-xs text-slate-500 mt-2 pl-3 border-l-2 border-slate-700">议长回应：{mo.why_overruled}</p>}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Pipeline 结果摘要 + 跳转链接 */}
      {fs && (
        <section className="panel panel-beam p-6">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">Pipeline 产出 <span className="sec-label">Outputs</span></h3>
          <div className="grid grid-cols-3 gap-4">
            {fs.pipeline_evaluation && Object.keys(fs.pipeline_evaluation).length > 0 && (
              <Link to="/strategy" className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-astro-500/30 transition-all group">
                <div className="text-xs text-slate-500 mb-1">五维评分</div>
                <div className="stat-num text-2xl text-aurora-400">
                  {((fs.pipeline_evaluation.factual_accuracy || 0) * 0.3 + (fs.pipeline_evaluation.strategic_actionability || 0) * 0.25 + (fs.pipeline_evaluation.audience_fit || 0) * 0.2 + (fs.pipeline_evaluation.cultural_sensitivity || 0) * 0.15 + (fs.pipeline_evaluation.narrative_fluency || 0) * 0.1).toFixed(1)}
                </div>
                <div className="text-[10px] text-astro-400/60 mt-2 group-hover:text-astro-300 transition-colors">查看详情 →</div>
              </Link>
            )}
            {fs.pipeline_strategies && (
              <Link to="/strategy" className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-nova-400/30 transition-all group">
                <div className="text-xs text-slate-500 mb-1">传播策略</div>
                <div className="stat-num text-2xl text-nova-400">
                  {Array.isArray((fs.pipeline_strategies as Record<string, unknown>)?.strategies) ? ((fs.pipeline_strategies as Record<string, unknown>).strategies as unknown[]).length : 0} 条
                </div>
                <div className="text-[10px] text-nova-400/60 mt-2 group-hover:text-nova-300 transition-colors">查看详情 →</div>
              </Link>
            )}
            {fs.pipeline_verification && (fs.pipeline_verification as unknown[]).length > 0 && (
              <Link to="/verify" className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-aurora-400/30 transition-all group">
                <div className="text-xs text-slate-500 mb-1">证据校验</div>
                <div className="stat-num text-2xl text-astro-300">{(fs.pipeline_verification as unknown[]).length} 条</div>
                <div className="text-[10px] text-astro-400/60 mt-2 group-hover:text-astro-300 transition-colors">查看详情 →</div>
              </Link>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

/* ═══════════ 最终总结报告 ═══════════ */
function SummaryCard({ report }: { report: FinalReport }) {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-astro-500/25 bg-gradient-to-br from-abyss-700/90 to-abyss-900/95 shadow-panel">
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-astro-500 via-nova-400 to-astro-500 opacity-70" />
      <div className="p-7">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xl">📝</span>
          <h3 className="text-base font-bold text-white">最终总结报告</h3>
          <span className="text-[9px] font-mono tracking-widest px-2.5 py-1 rounded-full bg-astro-500/10 text-astro-300 border border-astro-500/25 uppercase">AI Scientist Output</span>
        </div>

        {report.one_line_takeaway && (
          <div className="mb-4 px-5 py-3.5 rounded-xl bg-astro-500/[0.08] border border-astro-500/25">
            <span className="text-[15px] font-bold text-astro-300">◈ {report.one_line_takeaway}</span>
          </div>
        )}

        {report.core_conclusion && (
          <p className="text-sm text-slate-300 leading-relaxed mb-5">{report.core_conclusion}</p>
        )}

        {report.top_strategies && report.top_strategies.length > 0 && (
          <div className="mb-5">
            <h4 className="text-xs font-bold text-slate-400 mb-3 flex items-center gap-2">TOP 策略推荐 <span className="sec-label">Priority Actions</span></h4>
            <div className="grid grid-cols-3 gap-3">
              {report.top_strategies.map(s => (
                <div key={s.rank} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-nova-400/30 transition-all group">
                  <span className="stat-num text-2xl text-nova-400/80 group-hover:text-nova-400 transition-colors">#{s.rank}</span>
                  <div className="text-sm text-white font-medium mt-1.5">{s.title}</div>
                  <div className="text-[11px] text-slate-500 mt-1">👥 {s.audience}</div>
                  <div className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">{s.action}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-5">
          {report.risk_warnings && report.risk_warnings.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-nova-400 mb-2.5">⚠ 风险提示</h4>
              <ul className="space-y-1.5">
                {report.risk_warnings.map((w, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                    <span className="text-nova-400 mt-0.5 shrink-0">▸</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.audience_recommendations && report.audience_recommendations.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-astro-300 mb-2.5">◉ 受众适配建议</h4>
              <ul className="space-y-1.5">
                {report.audience_recommendations.map((a, i) => (
                  <li key={i} className="text-xs text-slate-300">
                    <span className="text-astro-300 font-medium">{a.audience}</span>：{a.suggestion}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
