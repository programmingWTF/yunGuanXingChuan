/**
 * 云观星传 - 认知议会结果页
 * 仅展示认知议会的辩论记录与策略结果
 */
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { DeliberationTranscript, FinalReport } from '../api'
import { ProgressTree } from './TaskCenter'

const AGENT_LABELS: Record<string, string> = {
  scientist: '🔬 科学家', skeptic: '🔍 质疑者', humanist: '🎭 人文学者',
  strategist: '📋 策略师', evaluator: '🏆 评估者', speaker: '🏛️ 议长',
}
const STANCE_STYLES: Record<string, string> = {
  support: 'text-green-400', oppose: 'text-red-400', amend: 'text-yellow-400',
  question: 'text-purple-400', clarify: 'text-blue-400',
}
const STANCE_ICONS: Record<string, string> = {
  support: '👍', oppose: '👎', amend: '✏️', question: '❓', clarify: '💬',
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
      <div className="glass-card p-12 text-center">
        <div className="text-4xl mb-4">🏛️</div>
        <h3 className="text-lg font-bold text-white mb-2">认知议会</h3>
        <p className="text-sm text-gray-400 mb-6">暂无议会结果。请先在任务中心启动认知议会任务。</p>
        <Link to="/" className="btn-primary inline-block px-6 py-2.5">🚀 前往任务中心</Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 流程图回顾 */}
      {progressSnapshot && progressSnapshot.phases && (
        <ProgressTree progress={progressSnapshot} readonly />
      )}
      <ResultView transcript={transcript} expandedRound={expandedRound} expandedSpeaker={expandedSpeaker}
        onToggleRound={r => setExpandedRound(expandedRound === r ? null : r)}
        onToggleSpeaker={s => { if (s === null || s === expandedSpeaker) setExpandedSpeaker(null); else setExpandedSpeaker(s) }} />
    </div>
  )
}

/* ========== 结果视图 ========== */
function ResultView({ transcript: t, expandedRound, expandedSpeaker, onToggleRound, onToggleSpeaker }: {
  transcript: DeliberationTranscript
  expandedRound: number | null; expandedSpeaker: string | null
  onToggleRound: (r: number) => void; onToggleSpeaker: (s: string | null) => void
}) {
  const votes = t.votes; const rounds = t.rounds; const minority = t.minority_opinions; const fs = t.final_strategies
  const passRate = votes.length ? Math.round(votes.filter(v => v.result === 'passed').length / votes.length * 100) : 0

  return (
    <div className="space-y-4">
      {/* 最终总结报告 */}
      {t.final_report && <SummaryCard report={t.final_report} topic={t.topic} />}

      {/* 概览 */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-white">📋 议会记录: {t.topic}</h3>
          <span className="text-xs text-gray-400">{t.started_at?.slice(11, 19)}→{t.completed_at?.slice(11, 19)}</span>
        </div>
        <div className="grid grid-cols-5 gap-3">
          {[{ l: '辩论轮次', v: t.total_rounds, i: '⚔️' }, { l: '动议数', v: t.motions.length, i: '📜' }, { l: '表决数', v: votes.length, i: '🗳️' }, { l: '少数派', v: minority.length, i: '🔶' }, { l: '通过率', v: `${passRate}%`, i: '📊' }].map(m => (
            <div key={m.l} className="bg-white/5 rounded-lg p-3 text-center">
              <div className="text-xl">{m.i}</div><div className="text-lg font-bold text-white">{m.v}</div><div className="text-[10px] text-gray-400">{m.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 投票 */}
      {votes.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-bold text-gray-300 mb-3">🗳️ 表决结果</h3>
          <div className="space-y-2">
            {votes.map(v => (
              <div key={v.motion_id} className="flex items-center gap-3 p-3 rounded-lg bg-white/5">
                <span className="text-lg">{v.result === 'passed' ? '✅' : v.result === 'rejected' ? '❌' : v.result === 'amended' ? '⚠️' : '🔶'}</span>
                <div className="flex-1">
                  <span className="text-sm text-white">{v.motion_id}</span>
                  <span className={`text-xs ml-2 px-1.5 py-0.5 rounded ${v.result === 'passed' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{v.result}</span>
                  <div className="flex items-center gap-1 mt-1">
                    <div className="flex-1 h-2 rounded-full bg-gray-700 overflow-hidden flex">
                      <div className="h-full bg-green-500/70" style={{ width: `${v.weighted_yes * 100}%` }} />
                      <div className="h-full bg-red-500/70" style={{ width: `${v.weighted_no * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-gray-400">👍{(v.weighted_yes * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex gap-1">
                  {Object.entries(v.votes).map(([a, vo]) => (
                    <span key={a} className="text-xs">{vo === 'yes' ? '👍' : vo === 'no' ? '👎' : '⚪'}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 搜索来源 */}
      {fs?.search_sources && fs.search_sources.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-xs font-bold text-gray-400 mb-2">🌐 联网搜索来源 ({fs.search_sources.length})</h3>
          <div className="flex flex-wrap gap-2">
            {fs.search_sources.slice(0, 8).map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors text-[11px] text-gray-300 max-w-[280px]">
                <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${s.source === 'TavilySearch' ? 'bg-blue-400' : 'bg-purple-400'}`} />
                <span className="truncate">{s.title || s.url}</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* 辩论轮次 */}
      {rounds.map(r => (
        <div key={r.round_id} className="glass-card overflow-hidden">
          <button onClick={() => onToggleRound(r.round_id)}
            className="w-full flex items-center justify-between p-4 hover:bg-white/5">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-full bg-star-blue/20 flex items-center justify-center text-xs font-bold text-star-blue">{r.round_id}</span>
              <div className="text-left"><div className="text-sm text-white">{r.topic}</div>
                <div className="text-[10px] text-gray-400">{r.speeches.length}条发言 | 权重:{Object.entries(r.speaker_weights).map(([k, v]) => `${k}${(v * 100).toFixed(0)}%`).join(',')}</div>
              </div>
            </div>
            <span className="text-gray-500">{expandedRound === r.round_id ? '▲' : '▼'}</span>
          </button>
          {expandedRound === r.round_id && (
            <div className="px-4 pb-4 space-y-3 border-t border-white/5">
              {r.speaker_rationale && (
                <div className="mt-3 p-2.5 rounded-lg bg-star-blue/5 border border-star-blue/20">
                  <span className="text-[10px] text-star-blue font-medium">🏛️ 权重理由: </span>
                  <span className="text-xs text-gray-300">{r.speaker_rationale}</span>
                </div>
              )}
              {r.speeches.map((s, i) => {
                const key = `${r.round_id}-${s.speaker}-${i}`
                return (
                  <div key={key} className="p-3 rounded-lg bg-white/5">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-white">{AGENT_LABELS[s.speaker] || s.speaker}</span>
                      <span className={`text-[10px] ${STANCE_STYLES[s.stance] || STANCE_STYLES.clarify}`}>
                        {STANCE_ICONS[s.stance] || '💬'} {s.stance}
                      </span>
                      <button onClick={() => onToggleSpeaker(expandedSpeaker === key ? null : key)}
                        className="text-[10px] text-star-blue/60 hover:text-star-blue ml-auto">查看全文</button>
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {expandedSpeaker === key ? s.content : s.content.slice(0, 150) + (s.content.length > 150 ? '...' : '')}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ))}

      {/* 少数派 */}
      {minority.length > 0 && (
        <div className="glass-card p-5 border-l-4 border-yellow-500/50">
          <h3 className="text-sm font-bold text-yellow-400 mb-3">🔶 少数派意见 ({minority.length})</h3>
          <div className="space-y-3">
            {minority.map((mo, i) => (
              <div key={i} className="bg-white/5 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-white">{AGENT_LABELS[mo.agent] || mo.agent}</span>
                  <span className="text-[10px] text-gray-500">→ {mo.motion_id}</span>
                </div>
                <p className="text-sm text-gray-300">{mo.objection}</p>
                {mo.why_overruled && <p className="text-xs text-gray-500 mt-1">议长回应: {mo.why_overruled}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pipeline 结果 */}
      {fs && (
        <div className="space-y-4">
          {fs.pipeline_evaluation && Object.keys(fs.pipeline_evaluation).length > 0 && <EvalCard evaluation={fs.pipeline_evaluation} />}
          {fs.pipeline_strategies && <StrategyCard strategies={(fs.pipeline_strategies as Record<string, unknown>)?.strategies as Record<string, unknown>[] || []} minority={minority} />}
          {fs.pipeline_verification && (fs.pipeline_verification as unknown[]).length > 0 && <VerifyCard results={fs.pipeline_verification as Record<string, unknown>[]} />}
        </div>
      )}
    </div>
  )
}

function EvalCard({ evaluation: e }: { evaluation: Record<string, number> }) {
  const dims = [{ k: 'factual_accuracy', l: '事实准确', i: '🔬' }, { k: 'strategic_actionability', l: '策略可行', i: '🎯' }, { k: 'audience_fit', l: '受众匹配', i: '👥' }, { k: 'cultural_sensitivity', l: '文化敏感', i: '🌍' }, { k: 'narrative_fluency', l: '叙事流畅', i: '✍️' }]
  const vals = dims.map(d => e[d.k] || 0); const avg = vals.reduce((a, b) => a + b, 0) / vals.length
  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-bold text-gray-300 mb-4">📊 五维评分</h3>
      <div className="flex items-center gap-6">
        {/* 雷达图 */}
        <RadarChart values={vals} labels={dims.map(d => d.l)} />
        {/* 分数列表 */}
        <div className="flex-1 grid grid-cols-5 gap-3">
          {dims.map((d, i) => (
            <div key={d.k} className="text-center">
              <div className="text-lg">{d.i}</div>
              <div className={`text-lg font-bold mt-1 ${vals[i] >= 75 ? 'text-green-400' : vals[i] >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>{vals[i]}</div>
              <div className="text-[10px] text-gray-400">{d.l}</div>
              <div className="mt-1.5 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                <div className={`h-full rounded-full ${vals[i] >= 75 ? 'bg-green-500' : vals[i] >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${vals[i]}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 text-center text-xs text-gray-400">加权平均:<span className={`font-bold ${avg >= 75 ? 'text-green-400' : 'text-yellow-400'}`}>{avg.toFixed(1)}</span></div>
    </div>
  )
}

/* ========== SVG 雷达图 ========== */
function RadarChart({ values, labels, size = 140 }: { values: number[]; labels: string[]; size?: number }) {
  const n = values.length
  const cx = size / 2, cy = size / 2, r = size / 2 - 20
  const angleStep = (2 * Math.PI) / n
  const toPoint = (i: number, val: number) => {
    const angle = -Math.PI / 2 + i * angleStep
    const rad = (val / 100) * r
    return `${cx + rad * Math.cos(angle)},${cy + rad * Math.sin(angle)}`
  }
  // 背景网格
  const grids = [20, 40, 60, 80, 100].map(level =>
    values.map((_, i) => toPoint(i, level)).join(' ')
  )
  // 数据区域
  const dataPoints = values.map((v, i) => toPoint(i, v)).join(' ')
  return (
    <svg width={size} height={size} className="shrink-0">
      {grids.map((pts, i) => (
        <polygon key={i} points={pts} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      ))}
      {values.map((_, i) => {
        const [x, y] = toPoint(i, 100).split(',')
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
      })}
      <polygon points={dataPoints} fill="rgba(56,189,248,0.2)" stroke="rgba(56,189,248,0.8)" strokeWidth="2" />
      {values.map((v, i) => {
        const [x, y] = toPoint(i, v).split(',')
        return <circle key={i} cx={x} cy={y} r="3" fill="#38bdf8" />
      })}
      {labels.map((l, i) => {
        const angle = -Math.PI / 2 + i * angleStep
        const lx = cx + (r + 14) * Math.cos(angle)
        const ly = cy + (r + 14) * Math.sin(angle)
        return <text key={i} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" className="fill-gray-400 text-[8px]">{l}</text>
      })}
    </svg>
  )
}

/* ========== 最终总结报告卡片 ========== */
function SummaryCard({ report }: { report: FinalReport; topic?: string }) {
  return (
    <div className="glass-card p-6 border border-star-blue/20 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-star-blue/60 via-purple-500/60 to-cyan-400/60" />
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">📝</span>
        <h3 className="text-base font-bold text-white">最终总结报告</h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-star-blue/10 text-star-blue">认知议会输出</span>
      </div>
      {/* 一句话结论 */}
      {report.one_line_takeaway && (
        <div className="mb-3 px-4 py-2.5 rounded-xl bg-star-blue/10 border border-star-blue/20">
          <span className="text-sm font-bold text-star-blue">💡 {report.one_line_takeaway}</span>
        </div>
      )}
      {/* 核心结论 */}
      {report.core_conclusion && (
        <p className="text-sm text-gray-300 leading-relaxed mb-4">{report.core_conclusion}</p>
      )}
      {/* TOP3 策略 */}
      {report.top_strategies && report.top_strategies.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-bold text-gray-400 mb-2">🎯 TOP 策略推荐</h4>
          <div className="space-y-2">
            {report.top_strategies.map(s => (
              <div key={s.rank} className="flex items-start gap-3 p-3 rounded-lg bg-white/5">
                <span className="w-6 h-6 rounded-full bg-star-blue/20 flex items-center justify-center text-xs font-bold text-star-blue shrink-0">{s.rank}</span>
                <div>
                  <div className="text-sm text-white font-medium">{s.title}</div>
                  <div className="text-[11px] text-gray-400 mt-0.5">👥 {s.audience} · {s.action}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* 风险提示 + 受众建议 */}
      <div className="grid grid-cols-2 gap-4">
        {report.risk_warnings && report.risk_warnings.length > 0 && (
          <div>
            <h4 className="text-xs font-bold text-yellow-400 mb-2">⚠️ 风险提示</h4>
            <ul className="space-y-1">
              {report.risk_warnings.map((w, i) => (
                <li key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                  <span className="text-yellow-500 mt-0.5">•</span>{w}
                </li>
              ))}
            </ul>
          </div>
        )}
        {report.audience_recommendations && report.audience_recommendations.length > 0 && (
          <div>
            <h4 className="text-xs font-bold text-cyan-400 mb-2">👥 受众适配建议</h4>
            <ul className="space-y-1">
              {report.audience_recommendations.map((a, i) => (
                <li key={i} className="text-xs text-gray-300">
                  <span className="text-cyan-400 font-medium">{a.audience}</span>: {a.suggestion}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

function StrategyCard({ strategies, minority }: { strategies: Record<string, unknown>[]; minority: { agent: string; objection: string; motion_id: string }[] }) {
  if (!strategies || strategies.length === 0) return null
  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-bold text-gray-300 mb-3">📋 策略建议 ({strategies.length})</h3>
      <div className="space-y-3">
        {strategies.map((s, i) => (
          <div key={i} className="bg-white/5 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-star-blue">{(s.strategy_id as string) || `S${i + 1}`}</span>
              <span className="text-xs text-gray-400">{(s.target_audience as string) || ''}</span>
            </div>
            <p className="text-sm text-white font-medium mb-1">{(s.narrative_angle as string) || (s.narrative_persona as string) || ''}</p>
            {Array.isArray(s.key_messages) && (s.key_messages as string[])?.slice(0, 3).map((m, j) => (
              <p key={j} className="text-xs text-gray-300">• {m}</p>
            ))}
            {minority.length > 0 && (
              <div className="mt-2 p-2 rounded bg-yellow-500/10 border border-yellow-500/20">
                <span className="text-[10px] text-yellow-400 font-medium">⚠️ 少数派风险: </span>
                <span className="text-[10px] text-gray-400">{minority.slice(0, 2).map(m => m.objection).join('; ')}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function VerifyCard({ results }: { results: Record<string, unknown>[] }) {
  if (!results || results.length === 0) return null
  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-bold text-gray-300 mb-3">🔍 校验结果 ({results.length})</h3>
      <div className="space-y-2">
        {results.slice(0, 8).map((r, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/5">
            <span>{(r.verification_status as string) === 'verified' ? '✅' : (r.verification_status as string) === 'contradicted' ? '❌' : '⚠️'}</span>
            <div className="flex-1">
              <p className="text-xs text-white truncate">{(r.claim as string) || `校验项${i + 1}`}</p>
              <p className="text-[10px] text-gray-500">置信度:{((r.confidence as number) || 0) * 100}%</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
