/**
 * 云观星传 V2.0 — 传播策略
 * Communicator Agent · 分众叙事 · 五维评分 · 迭代反馈
 */
import { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useStore } from '../store'
import type { Strategy } from '../api'

const personaNames: Record<string, string> = {
  scientist: '科学家', collaborator: '合作者', storyteller: '讲述者', communicator: '沟通者',
}
const personaStyles: Record<string, string> = {
  scientist: 'Nature / Science 期刊风格', collaborator: '联合国报告风格',
  storyteller: '国家地理 / 纪录片风格', communicator: '智库 / 政策分析风格',
}
const personaColors: Record<string, string> = {
  scientist: 'text-astro-300 border-astro-500/30 bg-astro-500/10',
  collaborator: 'text-aurora-400 border-aurora-400/30 bg-aurora-400/10',
  storyteller: 'text-nova-400 border-nova-400/30 bg-nova-400/10',
  communicator: 'text-purple-300 border-purple-400/30 bg-purple-500/10',
}

function loadParliamentFallback() {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return null
    const d = JSON.parse(r)
    const fs = d?.final_strategies
    if (!fs) return null
    const ps = fs.pipeline_strategies as Record<string, unknown> | unknown[] | undefined
    let strategies: Strategy[] = []
    if (Array.isArray(ps)) {
      strategies = ps as Strategy[]
    } else if (ps && typeof ps === 'object') {
      const inner = (ps as Record<string, unknown>).strategies
      if (Array.isArray(inner)) strategies = inner as Strategy[]
    }
    if (strategies.length === 0 && Array.isArray(fs.strategies)) {
      strategies = fs.strategies as Strategy[]
    }
    const evaluation = fs.pipeline_evaluation || {}
    return {
      strategies,
      evaluation,
      iteration_count: d?.total_rounds || 0,
      topic: d?.topic || '',
      iteration_feedback: [] as { dimension: string; current_score: number; issue: string; suggestion: string; target_agent: string }[],
    }
  } catch { return null }
}

function StrategyPage() {
  const { state } = useStore()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const result = state.result || loadParliamentFallback()
  const strategies: Strategy[] = result?.strategies || []
  const evaluation = result?.evaluation

  if (!result) {
    return (
      <div className="panel p-16 text-center">
        <div className="text-5xl mb-5 opacity-50">▤</div>
        <h3 className="text-lg font-bold text-white mb-2">暂无传播策略</h3>
        <p className="text-sm text-slate-500">运行分析后，Communicator Agent 将基于假设与校验结果生成分众传播策略</p>
      </div>
    )
  }

  const radarOption = evaluation ? {
    radar: {
      indicator: [
        { name: '事实准确度', max: 100 },
        { name: '策略可操作性', max: 100 },
        { name: '受众适配度', max: 100 },
        { name: '文化敏感性', max: 100 },
        { name: '叙事流畅度', max: 100 },
      ],
      axisName: { color: '#94a3b8', fontSize: 11 },
      center: ['50%', '54%'],
      radius: '68%',
      splitLine: { lineStyle: { color: 'rgba(56,212,248,0.12)' } },
      splitArea: { areaStyle: { color: ['rgba(12,184,232,0.02)', 'rgba(12,184,232,0.05)'] } },
      axisLine: { lineStyle: { color: 'rgba(56,212,248,0.15)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          evaluation.factual_accuracy,
          evaluation.strategic_actionability,
          evaluation.audience_fit,
          evaluation.cultural_sensitivity,
          evaluation.narrative_fluency,
        ],
        name: '最终评分',
        areaStyle: { color: 'rgba(12,184,232,0.22)' },
        lineStyle: { color: '#38d4f8', width: 2 },
        itemStyle: { color: '#7de8ff' },
      }],
    }],
    backgroundColor: 'transparent',
  } : null

  const weightedTotal = evaluation ? (
    evaluation.factual_accuracy * 0.30 +
    evaluation.strategic_actionability * 0.25 +
    evaluation.audience_fit * 0.20 +
    evaluation.cultural_sensitivity * 0.15 +
    evaluation.narrative_fluency * 0.10
  ).toFixed(1) : '-'

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <p className="sec-label mb-1">Communication Strategy</p>
          <h2 className="font-display text-2xl font-bold text-white">传播策略</h2>
          <p className="text-xs text-slate-500 mt-1.5">共 {strategies.length} 条策略 · 迭代 {result.iteration_count} 轮 · 分众叙事适配</p>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-500">加权总分</div>
          <div className="stat-num text-3xl text-nova-400">{weightedTotal}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* 策略卡片列表 */}
        <div className="col-span-2 space-y-4">
          {strategies.length === 0 && (
            <div className="panel p-10 text-center text-slate-600 text-sm">暂无策略数据</div>
          )}
          {strategies.map((s, idx) => {
            const expanded = expandedId === s.strategy_id
            return (
              <div key={s.strategy_id}
                className="panel panel-beam p-6 cursor-pointer animate-rise"
                style={{ animationDelay: `${idx * 0.06}s` }}
                onClick={() => setExpandedId(expanded ? null : s.strategy_id)}>
                {/* 头部 */}
                <div className="flex justify-between items-start mb-3.5">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-astro-500/10 text-astro-300 border border-astro-500/25">{s.strategy_id}</span>
                    <span className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border ${personaColors[s.narrative_persona] || 'text-slate-400 border-slate-600/40 bg-slate-700/20'}`}>
                      {personaNames[s.narrative_persona] || s.narrative_persona}
                    </span>
                    <span className="text-[11px] text-slate-500">{personaStyles[s.narrative_persona] || ''}</span>
                  </div>
                  <span className="chip text-slate-300 whitespace-nowrap">👤 {s.target_audience}</span>
                </div>

                {/* 叙事角度 */}
                <p className="text-xs text-slate-400 mb-3">
                  <span className="text-astro-300 font-medium">叙事角度</span> · {s.narrative_angle}
                </p>

                {/* 示例文本 */}
                <div className="rounded-xl bg-white/[0.02] border-l-2 border-astro-500/40 p-4 mb-3.5 italic text-slate-300 text-sm leading-relaxed">
                  "{s.sample_text}"
                </div>

                {/* 渠道 */}
                <div className="flex flex-wrap gap-2">
                  {(s.channel_recommendation || []).map((c, i) => (
                    <span key={i} className="px-2.5 py-1 rounded-md text-[11px] text-astro-300 border border-astro-500/20 bg-astro-500/5">{c}</span>
                  ))}
                </div>

                {/* 展开详情 */}
                {expanded && (
                  <div className="mt-5 pt-5 border-t border-white/[0.07] space-y-4 animate-fade-in" onClick={e => e.stopPropagation()}>
                    <div>
                      <h4 className="text-[11px] font-bold text-nova-400 mb-2">核心信息</h4>
                      <ul className="space-y-1.5 text-sm text-slate-300">
                        {(s.key_messages || []).map((m, i) => <li key={i} className="flex gap-2"><span className="text-nova-400">◆</span>{m}</li>)}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-[11px] font-bold text-aurora-400 mb-2">文化适配</h4>
                      <ul className="space-y-1.5 text-sm text-slate-300">
                        {(s.cultural_adaptations || []).map((c, i) => <li key={i} className="flex gap-2"><span className="text-aurora-400">🌐</span>{c}</li>)}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-[11px] font-bold text-astro-300 mb-2">预期效果</h4>
                      <p className="text-sm text-slate-300 leading-relaxed">{s.expected_effect}</p>
                    </div>
                    {s.risks && s.risks.length > 0 && (
                      <div className="p-4 rounded-xl bg-flare-500/5 border border-flare-400/20">
                        <h4 className="text-[11px] font-bold text-flare-400 mb-2">风险提示</h4>
                        <ul className="space-y-1.5 text-sm text-flare-400/80">
                          {s.risks.map((r, i) => <li key={i} className="flex gap-2"><span>⚠</span>{r}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-3.5 text-[10px] text-slate-600 text-center">{expanded ? '▲ 收起' : '▼ 展开详情'}</div>
              </div>
            )
          })}
        </div>

        {/* 右侧雷达图 + 迭代反馈 */}
        <div className="space-y-4">
          {radarOption && (
            <div className="panel p-5">
              <p className="sec-label mb-1">Five-Dimension Score</p>
              <h3 className="font-display text-base font-bold text-white mb-2">五维评分</h3>
              <ReactECharts option={radarOption} style={{ height: 300 }} />
            </div>
          )}

          {result.iteration_feedback && result.iteration_feedback.length > 0 && (
            <div className="panel p-5">
              <p className="sec-label mb-1">Iteration Feedback</p>
              <h3 className="font-display text-base font-bold text-white mb-3">迭代改进建议</h3>
              <div className="space-y-3">
                {result.iteration_feedback.map((fb, i) => (
                  <div key={i} className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-sm">
                    <div className="flex justify-between mb-1.5">
                      <span className="text-astro-300 font-medium">{fb.dimension}</span>
                      <span className="text-slate-600 text-xs">→ {fb.target_agent}</span>
                    </div>
                    <p className="text-slate-300 mb-1.5 text-xs leading-relaxed">{fb.issue}</p>
                    <p className="text-aurora-400/80 text-xs leading-relaxed">💡 {fb.suggestion}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyPage
