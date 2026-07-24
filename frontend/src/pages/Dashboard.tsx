import ReactECharts from 'echarts-for-react'
import { useStore } from '../store'

function loadParliamentEval() {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return null
    const d = JSON.parse(r)
    return d?.final_strategies?.pipeline_evaluation || null
  } catch { return null }
}

/** 空状态提示 */
function EmptyState() {
  const { state } = useStore()
  const isRunning = state.phase === 'submitting' || state.phase === 'running'

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-6xl mb-4">{isRunning ? '⏳' : '🔭'}</div>
      <h3 className="text-xl font-bold text-gray-300 mb-2">
        {isRunning ? 'Pipeline 正在分析中...' : '暂无分析数据'}
      </h3>
      <p className="text-gray-500 max-w-md">
        {isRunning
          ? '系统正在执行：科学理解 → 语境分析 → 假设生成 → 校验 → 策略转译 → 评测迭代'
          : '请在上方输入科技议题（如"嫦娥六号"），点击"开始分析"运行完整 Pipeline'}
      </p>
      {isRunning && (
        <div className="mt-6 flex gap-2">
          {['科学理解', '语境分析', '假设生成', '校验', '策略', '评测'].map((s, i) => (
            <span key={s} className="px-3 py-1 rounded-full text-xs bg-star-blue/10 text-star-blue animate-pulse" style={{ animationDelay: `${i * 0.2}s` }}>
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ParliamentFallbackDashboard() {
  const eval_ = loadParliamentEval()
  const dims = [{k:'factual_accuracy',l:'事实准确',i:'🔬'},{k:'strategic_actionability',l:'策略可行',i:'🎯'},{k:'audience_fit',l:'受众匹配',i:'👥'},{k:'cultural_sensitivity',l:'文化敏感',i:'🌍'},{k:'narrative_fluency',l:'叙事流畅',i:'✍️'}]

  // 从议会结果中提取更多数据
  let parliamentData: { topic?: string; total_rounds?: number; motion_count?: number; vote_count?: number; strategy_count?: number; verify_count?: number; search_sources?: { url: string; title: string; content: string; score: number; source: string }[] } | null = null
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (r) {
      const d = JSON.parse(r)
      const fs = d?.final_strategies || {}
      const ps = fs.pipeline_strategies
      let strategyCount = 0
      if (Array.isArray(ps)) strategyCount = ps.length
      else if (ps?.strategies && Array.isArray(ps.strategies)) strategyCount = ps.strategies.length
      else if (Array.isArray(fs.strategies)) strategyCount = fs.strategies.length
      parliamentData = {
        topic: d?.topic,
        total_rounds: d?.total_rounds || 0,
        motion_count: d?.motions?.length || 0,
        vote_count: d?.votes?.length || 0,
        strategy_count: strategyCount,
        verify_count: (fs.pipeline_verification || []).length,
        search_sources: fs.search_sources || [],
      }
    }
  } catch { /* ignore */ }

  if (!eval_ && !parliamentData) return <EmptyState />

  const vals = dims.map(d => eval_?.[d.k] || 0)
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length
  const hasScores = vals.some(v => v > 0)

  return (
    <div className="space-y-6 max-w-3xl mx-auto mt-8">
      {parliamentData && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-bold text-gray-300 mb-3">🏛️ 认知议会分析概览{parliamentData.topic ? `：${parliamentData.topic}` : ''}</h3>
          <div className="grid grid-cols-5 gap-3">
            {[
              { l: '辩论轮次', v: parliamentData.total_rounds, i: '⚔️' },
              { l: '动议数', v: parliamentData.motion_count, i: '📜' },
              { l: '表决数', v: parliamentData.vote_count, i: '🗳️' },
              { l: '策略数', v: parliamentData.strategy_count, i: '📋' },
              { l: '校验数', v: parliamentData.verify_count, i: '✅' },
            ].map(s => (
              <div key={s.l} className="bg-white/5 rounded-lg p-3 text-center">
                <div className="text-lg">{s.i}</div>
                <div className="text-xl font-bold text-white">{s.v ?? 0}</div>
                <div className="text-[10px] text-gray-400">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {hasScores && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-bold text-gray-300 mb-4">📊 五维评分（来自认知议会分析）</h3>
          <div className="grid grid-cols-5 gap-3">
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
          <div className="mt-4 text-center text-xs text-gray-400">加权平均:<span className={`font-bold ${avg >= 75 ? 'text-green-400' : 'text-yellow-400'}`}>{avg.toFixed(1)}</span> · 详细结果请查看 🏛️ 认知议会页面</div>
        </div>
      )}
      {/* 联网搜索来源 */}
      {parliamentData?.search_sources && parliamentData.search_sources.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-bold text-gray-300 mb-3">
            🌐 联网搜索内容
            <span className="text-xs font-normal text-gray-400 ml-2">(TavilySearch + QwenWebSearch)</span>
          </h3>
          <div className="space-y-2">
            {parliamentData.search_sources.map((source, i) => (
              <a key={i} href={source.url || undefined} target="_blank" rel="noopener noreferrer"
                className={`block p-3 bg-white/5 rounded-lg transition-colors group ${source.url ? 'hover:bg-white/10 cursor-pointer' : 'cursor-default'}`}>
                <div className="flex items-start gap-2">
                  <span className="text-star-blue text-xs mt-0.5">🔗</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        source.source === 'TavilySearch' ? 'bg-blue-500/20 text-blue-300' : 'bg-purple-500/20 text-purple-300'
                      }`}>
                        {source.source === 'TavilySearch' ? 'TavilySearch' : 'QwenWebSearch'}
                      </span>
                      <span className="text-sm text-white group-hover:text-star-blue transition-colors truncate">{source.title}</span>
                    </div>
                    {source.url && <div className="text-xs text-gray-500 truncate mt-0.5">{source.url}</div>}
                    {source.content && <div className="text-xs text-gray-400 mt-1 line-clamp-2">{source.content}</div>}
                  </div>
                  {source.score > 0 && <span className="text-xs text-gray-600 whitespace-nowrap">相关度 {(source.score * 100).toFixed(0)}%</span>}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Dashboard() {
  const { state } = useStore()
  const result = state.result

  if (!result) return <ParliamentFallbackDashboard />

  const { context_analysis, science_facts, hypotheses, strategies, evaluation } = result

  // 框架分布饼图
  const frameworkDist = context_analysis?.framework_distribution || {}
  const frameworkColors: Record<string, string> = {
    competition: '#FF6B35', cooperation: '#FFD700', progress: '#00D4FF',
    threat: '#FF4444', development: '#4CAF50',
  }
  const frameworkNames: Record<string, string> = {
    competition: '竞争框架', cooperation: '合作框架', progress: '进步框架',
    threat: '威胁框架', development: '发展框架',
  }
  const pieData = Object.entries(frameworkDist).map(([key, value]) => ({
    value: typeof value === 'number' ? value : 0,
    name: frameworkNames[key] || key,
    itemStyle: { color: frameworkColors[key] || '#888' },
  }))

  const pieOption = {
    title: { text: '传播框架分布', left: 'center', textStyle: { color: '#E0E0E0' } },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: pieData.length > 0 ? pieData : [{ value: 1, name: '暂无数据', itemStyle: { color: '#333' } }],
      label: { color: '#E0E0E0' },
    }],
    backgroundColor: 'transparent',
  }

  // 情感分析柱状图
  const countries = (context_analysis?.country_analysis || []).map((c: Record<string, unknown>) => (c.country as string) || '')
  const sentimentData = (context_analysis?.country_analysis || []).map((c: Record<string, unknown>) => {
    // 兼容两种字段格式：sentiment_distribution.positive 或 positive_ratio
    const dist = c.sentiment_distribution as Record<string, number> | undefined
    return {
      positive: (dist?.positive ?? (c.positive_ratio as number) ?? 0),
      neutral: (dist?.neutral ?? (c.neutral_ratio as number) ?? 0),
      negative: (dist?.negative ?? (c.negative_ratio as number) ?? 0),
    }
  })

  const barOption = {
    title: { text: '各国情感倾向', left: 'center', textStyle: { color: '#E0E0E0' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: countries.length ? countries : ['暂无'], axisLabel: { color: '#E0E0E0' } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#E0E0E0' } },
    series: [
      { name: '正面', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.positive * 100)), itemStyle: { color: '#4CAF50' } },
      { name: '中性', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.neutral * 100)), itemStyle: { color: '#FFD700' } },
      { name: '负面', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.negative * 100)), itemStyle: { color: '#FF6B35' } },
    ],
    legend: { textStyle: { color: '#E0E0E0' }, top: 30 },
    backgroundColor: 'transparent',
  }

  // 五维评分雷达图
  const radarOption = {
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
      }],
    }],
    backgroundColor: 'transparent',
  }

  const weightedTotal = (
    evaluation.factual_accuracy * 0.30 +
    evaluation.strategic_actionability * 0.25 +
    evaluation.audience_fit * 0.20 +
    evaluation.cultural_sensitivity * 0.15 +
    evaluation.narrative_fluency * 0.10
  ).toFixed(1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-star-blue">📊 数据驾驶舱</h2>
        <span className="text-sm text-gray-400">议题：{result.topic} | {result.timestamp.slice(0, 19).replace('T', ' ')}</span>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-5 gap-4">
        {[
          { label: '科学事实', value: String(science_facts?.key_facts?.length || 0), icon: '🔬' },
          { label: '传播假设', value: String(hypotheses?.length || 0), icon: '💡' },
          { label: '传播策略', value: String(strategies?.length || 0), icon: '📋' },
          { label: '迭代轮数', value: String(result.iteration_count), icon: '🔄' },
          { label: '加权总分', value: weightedTotal, icon: '🏆' },
        ].map((item, i) => (
          <div key={i} className="card p-4 text-center">
            <div className="text-3xl mb-2">{item.icon}</div>
            <div className="text-2xl font-bold text-star-blue">{item.value}</div>
            <div className="text-sm text-gray-400">{item.label}</div>
          </div>
        ))}
      </div>

      {/* 图表 */}
      <div className="grid grid-cols-2 gap-6">
        <div className="card p-4">
          <ReactECharts option={pieOption} style={{ height: 300 }} />
        </div>
        <div className="card p-4">
          <ReactECharts option={barOption} style={{ height: 300 }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="card p-4">
          <ReactECharts option={radarOption} style={{ height: 320 }} />
        </div>
        {/* 关键叙事 & 跨文化差异 */}
        <div className="card p-4 space-y-4">
          <div>
            <h3 className="text-lg font-bold text-star-gold mb-2">关键叙事点</h3>
            <ul className="space-y-1 text-sm text-gray-300">
              {(context_analysis?.key_narratives || []).map((n, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-star-blue">•</span>{n}
                </li>
              ))}
              {!(context_analysis?.key_narratives?.length) && <li className="text-gray-500">暂无</li>}
            </ul>
          </div>
          <div>
            <h3 className="text-lg font-bold text-star-gold mb-2">跨文化差异</h3>
            <ul className="space-y-1 text-sm text-gray-300">
              {(context_analysis?.cross_cultural_differences || []).map((d, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-star-orange">△</span>{d}
                </li>
              ))}
              {!(context_analysis?.cross_cultural_differences?.length) && <li className="text-gray-500">暂无</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* 科学事实列表 */}
      <div className="card p-4">
        <h3 className="text-lg font-bold text-star-gold mb-3">科学事实提取</h3>
        <div className="grid grid-cols-2 gap-2">
          {(science_facts?.key_facts || []).map((fact, i) => (
            <div key={i} className="flex items-start gap-2 p-2 bg-white/5 rounded-lg text-sm">
              <span className="text-star-blue font-mono text-xs mt-0.5">F{i + 1}</span>
              <span>{fact}</span>
            </div>
          ))}
          {!(science_facts?.key_facts?.length) && <span className="text-gray-500 text-sm">暂无事实数据</span>}
        </div>
      </div>

      {/* 联网搜索来源 */}
      {result.search_sources && result.search_sources.length > 0 && (
        <div className="card p-4">
          <h3 className="text-lg font-bold text-star-gold mb-3">
            🌐 联网搜索内容
            <span className="text-sm font-normal text-gray-400 ml-2">(TavilySearch + QwenWebSearch)</span>
          </h3>
          <div className="space-y-2">
            {result.search_sources.map((source, i) => (
              <a
                key={i}
                href={source.url || undefined}
                target="_blank"
                rel="noopener noreferrer"
                className={`block p-3 bg-white/5 rounded-lg transition-colors group ${source.url ? 'hover:bg-white/10 cursor-pointer' : 'cursor-default'}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-star-blue text-xs mt-0.5">🔗</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        source.source === 'TavilySearch'
                          ? 'bg-blue-500/20 text-blue-300'
                          : 'bg-purple-500/20 text-purple-300'
                      }`}>
                        {source.source === 'TavilySearch' ? 'TavilySearch' : 'QwenWebSearch'}
                      </span>
                      <span className="text-sm text-white group-hover:text-star-blue transition-colors truncate">
                        {source.title}
                      </span>
                    </div>
                    {source.url && (
                      <div className="text-xs text-gray-500 truncate mt-0.5">{source.url}</div>
                    )}
                    {source.content && (
                      <div className="text-xs text-gray-400 mt-1 line-clamp-2">{source.content}</div>
                    )}
                  </div>
                  {source.score > 0 && (
                    <span className="text-xs text-gray-600 whitespace-nowrap">
                      相关度 {(source.score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
