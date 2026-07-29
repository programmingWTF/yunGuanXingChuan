/**
 * 云观星传 V2.0 — 研究假设
 * 可验证传播假设 · 证据链 · 置信度
 */
import { useState } from 'react'
import { useStore } from '../store'
import type { Hypothesis } from '../api'

const frameworkNames: Record<string, string> = {
  competition: '竞争框架', cooperation: '合作框架', progress: '进步框架',
  threat: '威胁框架', development: '发展框架',
  fact_claim: '事实主张', hypothesis: '假设', value_judgment: '价值判断',
  policy_recommendation: '政策建议', causal: '因果推断',
}

const frameworkColors: Record<string, string> = {
  competition: 'text-flare-400 border-flare-400/25 bg-flare-500/5',
  cooperation: 'text-nova-400 border-nova-400/25 bg-nova-400/5',
  progress: 'text-astro-300 border-astro-500/25 bg-astro-500/5',
  threat: 'text-red-400 border-red-400/25 bg-red-500/5',
  development: 'text-aurora-400 border-aurora-400/25 bg-aurora-400/5',
  fact_claim: 'text-blue-300 border-blue-400/25 bg-blue-500/5',
  hypothesis: 'text-purple-300 border-purple-400/25 bg-purple-500/5',
  value_judgment: 'text-pink-300 border-pink-400/25 bg-pink-500/5',
  policy_recommendation: 'text-teal-300 border-teal-400/25 bg-teal-500/5',
  causal: 'text-amber-300 border-amber-400/25 bg-amber-500/5',
}

function loadParliamentMotions(): Hypothesis[] {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return []
    const d = JSON.parse(r)
    const motions = d?.motions
    if (!motions || !Array.isArray(motions) || motions.length === 0) return []
    return motions.map((m: Record<string, unknown>, i: number) => ({
      hypothesis_id: (m.motion_id as string) || `M${i + 1}`,
      statement: (m.content as string) || '',
      framework: (m.motion_type as string) || 'progress',
      target_countries: [] as string[],
      evidence_chain: ((m.supporting_evidence as string[]) || []).map((e: string) => ({
        source: '工作流辩论', quote: e, relevance: 0.8, evidence_type: '辩论证据',
      })),
      verification_path: '工作流表决通过',
      confidence: (m.confidence as number) || 0.7,
      kg_entities_involved: [] as string[],
      falsification_criteria: '',
    }))
  } catch { return [] }
}

function Hypotheses() {
  const { state } = useStore()
  const [frameworkFilter, setFrameworkFilter] = useState('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const result = state.result
  const hypotheses: Hypothesis[] = result?.hypotheses?.length ? result.hypotheses : loadParliamentMotions()

  const frameworkCounts = new Map<string, number>()
  for (const h of hypotheses) {
    const fw = (h.framework || '').trim() || 'unknown'
    frameworkCounts.set(fw, (frameworkCounts.get(fw) || 0) + 1)
  }

  const filtered = frameworkFilter === 'all'
    ? hypotheses
    : hypotheses.filter(h => ((h.framework || '').trim() || 'unknown') === frameworkFilter)

  if (!result && hypotheses.length === 0) {
    return (
      <div className="panel p-16 text-center">
        <div className="text-5xl mb-5 opacity-50">△</div>
        <h3 className="text-lg font-bold text-white mb-2">暂无研究假设</h3>
        <p className="text-sm text-slate-500">运行分析后，Planner Agent 将基于科学事实和语境分析产出可验证的传播研究假设</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <p className="sec-label mb-1">Research Hypotheses</p>
          <h2 className="font-display text-2xl font-bold text-white">研究假设</h2>
          <p className="text-xs text-slate-500 mt-1.5">共 {hypotheses.length} 条 · AI Scientist 范式：假设 → 验证 → 迭代</p>
        </div>
        <select value={frameworkFilter} onChange={e => setFrameworkFilter(e.target.value)}
          className="appearance-none bg-abyss-900/90 border border-astro-500/20 rounded-lg px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-astro-400/60 cursor-pointer [&>option]:bg-abyss-900">
          <option value="all">全部框架 ({hypotheses.length})</option>
          {[...frameworkCounts.entries()].map(([f, count]) => (
            <option key={f} value={f}>{frameworkNames[f] || f} ({count})</option>
          ))}
        </select>
      </div>

      {filtered.length === 0 && <div className="panel p-10 text-center text-slate-600 text-sm">当前筛选条件下无假设</div>}

      <div className="space-y-4">
        {filtered.map((h, idx) => {
          const expanded = expandedId === h.hypothesis_id
          return (
            <div key={h.hypothesis_id}
              className="panel panel-beam p-6 cursor-pointer animate-rise"
              style={{ animationDelay: `${idx * 0.06}s` }}
              onClick={() => setExpandedId(expanded ? null : h.hypothesis_id)}>
              <div className="flex justify-between items-start mb-3.5">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-astro-500/10 text-astro-300 border border-astro-500/25">{h.hypothesis_id}</span>
                  <span className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border ${frameworkColors[h.framework] || 'text-slate-400 border-slate-600/40 bg-slate-700/20'}`}>
                    {frameworkNames[h.framework] || h.framework}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-slate-500">置信度</div>
                  <div className={`stat-num text-2xl ${h.confidence >= 0.75 ? 'text-aurora-400' : h.confidence >= 0.5 ? 'text-nova-400' : 'text-flare-400'}`}>{(h.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>

              <p className="text-[15px] text-white leading-relaxed mb-3.5">{h.statement}</p>

              <div className="flex gap-5 text-[11px] text-slate-500">
                <span>🌍 {h.target_countries?.join(', ') || '-'}</span>
                <span>📎 {h.evidence_chain?.length || 0} 条证据</span>
                <span>✦ {h.kg_entities_involved?.length || 0} 个 KG 实体</span>
              </div>

              <div className="mt-4 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-700 ${h.confidence >= 0.75 ? 'bg-gradient-to-r from-astro-500 to-aurora-400' : 'bg-gradient-to-r from-astro-500 to-nova-400'}`}
                  style={{ width: `${h.confidence * 100}%` }} />
              </div>

              {expanded && (
                <div className="mt-5 pt-5 border-t border-white/[0.07] space-y-4 animate-fade-in" onClick={e => e.stopPropagation()}>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                      <h4 className="text-[11px] font-bold text-astro-300 mb-1.5">验证路径</h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{h.verification_path || '-'}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                      <h4 className="text-[11px] font-bold text-flare-400 mb-1.5">可证伪标准</h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{h.falsification_criteria || '-'}</p>
                    </div>
                  </div>
                  {h.evidence_chain && h.evidence_chain.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold text-nova-400 mb-2.5">证据链（{h.evidence_chain.length}）</h4>
                      <div className="space-y-2">
                        {h.evidence_chain.map((ev, i) => (
                          <div key={i} className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs">
                            <div className="flex justify-between mb-1.5">
                              <span className="text-astro-300 font-medium">{ev.source}</span>
                              <span className="text-slate-600 font-mono">{ev.evidence_type} · 相关度 {(ev.relevance * 100).toFixed(0)}%</span>
                            </div>
                            <p className="text-slate-400 italic leading-relaxed">"{ev.quote}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {h.kg_entities_involved && h.kg_entities_involved.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold text-purple-300 mb-2.5">涉及 KG 实体</h4>
                      <div className="flex flex-wrap gap-2">
                        {h.kg_entities_involved.map((ent, i) => (
                          <span key={i} className="px-2.5 py-1 rounded-md text-[11px] text-purple-300 border border-purple-400/25 bg-purple-500/5">{ent}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-3.5 text-[10px] text-slate-600 text-center">{expanded ? '▲ 收起' : '▼ 展开详情'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Hypotheses
