import { useState } from 'react'
import { useStore } from '../store'
import type { Hypothesis } from '../api'

const frameworkNames: Record<string, string> = {
  competition: '竞争框架', cooperation: '合作框架', progress: '进步框架',
  threat: '威胁框架', development: '发展框架',
}

const frameworkColors: Record<string, string> = {
  competition: 'bg-orange-500/20 text-orange-400',
  cooperation: 'bg-yellow-500/20 text-yellow-400',
  progress: 'bg-cyan-500/20 text-cyan-400',
  threat: 'bg-red-500/20 text-red-400',
  development: 'bg-green-500/20 text-green-400',
}

function Hypotheses() {
  const { state } = useStore()
  const [frameworkFilter, setFrameworkFilter] = useState('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const result = state.result
  const hypotheses: Hypothesis[] = result?.hypotheses || []

  const filtered = frameworkFilter === 'all'
    ? hypotheses
    : hypotheses.filter(h => h.framework === frameworkFilter)

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-6xl mb-4">💡</div>
        <h3 className="text-xl font-bold text-gray-300 mb-2">暂无假设数据</h3>
        <p className="text-gray-500">运行分析后，假设生成 Agent 将基于科学事实和语境分析产出传播假设</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-star-blue">💡 假设浏览</h2>
          <p className="text-sm text-gray-400 mt-1">共 {hypotheses.length} 条假设（AI Scientist 范式：假设→验证→迭代）</p>
        </div>
        <select
          value={frameworkFilter}
          onChange={e => setFrameworkFilter(e.target.value)}
          className="bg-space-dark border border-star-blue/30 rounded-lg px-4 py-2 text-white"
        >
          <option value="all">全部框架</option>
          <option value="competition">竞争框架</option>
          <option value="cooperation">合作框架</option>
          <option value="progress">进步框架</option>
          <option value="threat">威胁框架</option>
          <option value="development">发展框架</option>
        </select>
      </div>

      {filtered.length === 0 && (
        <div className="card p-8 text-center text-gray-500">当前筛选条件下无假设</div>
      )}

      <div className="space-y-4">
        {filtered.map(h => {
          const expanded = expandedId === h.hypothesis_id
          return (
            <div key={h.hypothesis_id} className="card p-6 cursor-pointer" onClick={() => setExpandedId(expanded ? null : h.hypothesis_id)}>
              {/* 头部 */}
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded-full text-sm bg-star-blue/20 text-star-blue font-mono">{h.hypothesis_id}</span>
                  <span className={`px-3 py-1 rounded-full text-sm ${frameworkColors[h.framework] || 'bg-gray-500/20 text-gray-400'}`}>
                    {frameworkNames[h.framework] || h.framework}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-400">置信度</div>
                  <div className="text-xl font-bold text-star-gold">{(h.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>

              {/* 假设陈述 */}
              <p className="text-lg mb-3">{h.statement}</p>

              {/* 元信息 */}
              <div className="flex gap-4 text-sm text-gray-400">
                <span>🌍 {h.target_countries?.join(', ') || '-'}</span>
                <span>📎 {h.evidence_chain?.length || 0} 条证据</span>
                <span>🔗 {h.kg_entities_involved?.length || 0} 个KG实体</span>
              </div>

              {/* 置信度条 */}
              <div className="mt-4 h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-star-blue to-star-gold rounded-full transition-all duration-700"
                  style={{ width: `${h.confidence * 100}%` }}
                />
              </div>

              {/* 展开详情 */}
              {expanded && (
                <div className="mt-4 pt-4 border-t border-white/10 space-y-3" onClick={e => e.stopPropagation()}>
                  <div>
                    <h4 className="text-sm font-bold text-star-gold mb-1">验证路径</h4>
                    <p className="text-sm text-gray-300">{h.verification_path || '-'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-star-gold mb-1">可证伪标准</h4>
                    <p className="text-sm text-gray-300">{h.falsification_criteria || '-'}</p>
                  </div>
                  {h.evidence_chain && h.evidence_chain.length > 0 && (
                    <div>
                      <h4 className="text-sm font-bold text-star-gold mb-1">证据链</h4>
                      <div className="space-y-2">
                        {h.evidence_chain.map((ev, i) => (
                          <div key={i} className="p-3 bg-white/5 rounded-lg text-sm">
                            <div className="flex justify-between mb-1">
                              <span className="text-star-blue">{ev.source}</span>
                              <span className="text-gray-500">{ev.evidence_type} | 相关度 {(ev.relevance * 100).toFixed(0)}%</span>
                            </div>
                            <p className="text-gray-300 italic">"{ev.quote}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {h.kg_entities_involved && h.kg_entities_involved.length > 0 && (
                    <div>
                      <h4 className="text-sm font-bold text-star-gold mb-1">涉及KG实体</h4>
                      <div className="flex flex-wrap gap-2">
                        {h.kg_entities_involved.map((ent, i) => (
                          <span key={i} className="px-2 py-1 rounded bg-purple-500/20 text-purple-300 text-xs">{ent}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-3 text-xs text-gray-500 text-center">{expanded ? '点击收起 ▲' : '点击展开详情 ▼'}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Hypotheses
