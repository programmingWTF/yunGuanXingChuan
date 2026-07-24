import { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useStore } from '../store'
import type { Strategy } from '../api'

const personaNames: Record<string, string> = {
  scientist: '科学家', collaborator: '合作者', storyteller: '讲述者', communicator: '沟通者',
}
const personaStyles: Record<string, string> = {
  scientist: 'Nature/Science 期刊风格', collaborator: '联合国报告风格',
  storyteller: '国家地理/纪录片风格', communicator: '智库/政策分析风格',
}

function loadParliamentFallback() {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return null
    const d = JSON.parse(r)
    const fs = d?.final_strategies
    if (!fs) return null
    // pipeline_strategies 可能是 {strategies: [...]} 或直接是数组
    const ps = fs.pipeline_strategies as Record<string, unknown> | unknown[] | undefined
    let strategies: Strategy[] = []
    if (Array.isArray(ps)) {
      strategies = ps as Strategy[]
    } else if (ps && typeof ps === 'object') {
      const inner = (ps as Record<string, unknown>).strategies
      if (Array.isArray(inner)) strategies = inner as Strategy[]
    }
    // 如果 pipeline_strategies 没有数据，尝试从顶层 strategies 字段获取
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
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-6xl mb-4">📋</div>
        <h3 className="text-xl font-bold text-gray-300 mb-2">暂无策略数据</h3>
        <p className="text-gray-500">运行分析后，策略转译 Agent 将基于假设和校验结果生成分众传播策略</p>
      </div>
    )
  }

  // 雷达图
  const radarOption = evaluation ? {
    title: { text: '五维评分', left: 'center', textStyle: { color: '#E0E0E0' } },
    radar: {
      indicator: [
        { name: '事实准确度', max: 100 },
        { name: '策略可操作性', max: 100 },
        { name: '受众适配度', max: 100 },
        { name: '文化敏感性', max: 100 },
        { name: '叙事流畅度', max: 100 },
      ],
      axisName: { color: '#E0E0E0' },
      center: ['50%', '58%'],
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
        areaStyle: { color: 'rgba(0,212,255,0.2)' },
        lineStyle: { color: '#00D4FF' },
        itemStyle: { color: '#00D4FF' },
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
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-star-blue">📋 策略推演</h2>
          <p className="text-sm text-gray-400 mt-1">共 {strategies.length} 条策略 | 加权总分: {weightedTotal} | 迭代 {result.iteration_count} 轮</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* 策略卡片列表 */}
        <div className="col-span-2 space-y-4">
          {strategies.length === 0 && (
            <div className="card p-8 text-center text-gray-500">暂无策略数据</div>
          )}
          {strategies.map(s => {
            const expanded = expandedId === s.strategy_id
            return (
              <div key={s.strategy_id} className="card p-6 cursor-pointer" onClick={() => setExpandedId(expanded ? null : s.strategy_id)}>
                {/* 头部 */}
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-star-blue font-bold font-mono">{s.strategy_id}</span>
                    <span className="px-2 py-1 rounded bg-star-gold/20 text-star-gold text-sm">
                      {personaNames[s.narrative_persona] || s.narrative_persona}
                    </span>
                    <span className="text-xs text-gray-500">{personaStyles[s.narrative_persona] || ''}</span>
                  </div>
                  <span className="text-gray-400 text-sm">👤 {s.target_audience}</span>
                </div>

                {/* 叙事角度 */}
                <p className="text-sm text-gray-400 mb-2">📐 叙事角度: {s.narrative_angle}</p>

                {/* 示例文本 */}
                <div className="bg-white/5 rounded-lg p-4 mb-3 italic text-gray-300 text-sm leading-relaxed">
                  "{s.sample_text}"
                </div>

                {/* 渠道 */}
                <div className="flex flex-wrap gap-2 mb-2">
                  {(s.channel_recommendation || []).map((c, i) => (
                    <span key={i} className="px-2 py-1 rounded bg-star-blue/10 text-star-blue text-xs">{c}</span>
                  ))}
                </div>

                {/* 展开详情 */}
                {expanded && (
                  <div className="mt-4 pt-4 border-t border-white/10 space-y-3" onClick={e => e.stopPropagation()}>
                    <div>
                      <h4 className="text-sm font-bold text-star-gold mb-1">核心信息</h4>
                      <ul className="space-y-1 text-sm text-gray-300">
                        {(s.key_messages || []).map((m, i) => <li key={i}>• {m}</li>)}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-star-gold mb-1">文化适配</h4>
                      <ul className="space-y-1 text-sm text-gray-300">
                        {(s.cultural_adaptations || []).map((c, i) => <li key={i}>🌐 {c}</li>)}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-star-gold mb-1">预期效果</h4>
                      <p className="text-sm text-gray-300">{s.expected_effect}</p>
                    </div>
                    {s.risks && s.risks.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-red-400 mb-1">风险提示</h4>
                        <ul className="space-y-1 text-sm text-red-300/80">
                          {s.risks.map((r, i) => <li key={i}>⚠️ {r}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-2 text-xs text-gray-500 text-center">{expanded ? '收起 ▲' : '展开详情 ▼'}</div>
              </div>
            )
          })}
        </div>

        {/* 右侧雷达图 + 迭代反馈 */}
        <div className="space-y-4">
          {radarOption && (
            <div className="card p-4">
              <ReactECharts option={radarOption} style={{ height: 320 }} />
            </div>
          )}

          {/* 迭代反馈 */}
          {result.iteration_feedback && result.iteration_feedback.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-bold text-star-gold mb-3">迭代改进建议</h3>
              <div className="space-y-3">
                {result.iteration_feedback.map((fb, i) => (
                  <div key={i} className="p-3 bg-white/5 rounded-lg text-sm">
                    <div className="flex justify-between mb-1">
                      <span className="text-star-blue">{fb.dimension}</span>
                      <span className="text-gray-500">→ {fb.target_agent}</span>
                    </div>
                    <p className="text-gray-300 mb-1">{fb.issue}</p>
                    <p className="text-green-400/80 text-xs">💡 {fb.suggestion}</p>
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
