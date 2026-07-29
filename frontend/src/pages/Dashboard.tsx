/**
 * 云观星传 V2.0 — 国际传播分析中心
 * 框架分布 · 各国情感 · 五维雷达 · 关键叙事 · 搜索来源
 */
import ReactECharts from 'echarts-for-react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'

function loadParliamentEval() {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return null
    const d = JSON.parse(r)
    return d?.final_strategies?.pipeline_evaluation || null
  } catch { return null }
}

/* ── 空状态 ── */
function EmptyState() {
  const { state } = useStore()
  const isRunning = state.phase === 'submitting' || state.phase === 'running'
  return (
    <div className="panel p-16 text-center">
      <div className="text-5xl mb-5 opacity-50">{isRunning ? '⏳' : '◉'}</div>
      <h3 className="text-lg font-bold text-white mb-2">{isRunning ? 'AI Scientist 正在分析中...' : '暂无传播分析数据'}</h3>
      <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
        {isRunning
          ? '知识检索 → 跨文化推理 → 假设生成 → 证据校验 → 传播策略 → 评测迭代'
          : '在研究工作台输入科技议题（如 JWST / 嫦娥七号），运行完整 AI Scientist 工作流后查看国际传播分析'}
      </p>
      {isRunning ? (
        <div className="flex gap-2 justify-center">
          {['知识检索', '跨文化推理', '假设生成', '证据校验', '传播策略', '评测迭代'].map((s, i) => (
            <span key={s} className="px-3 py-1.5 rounded-lg text-[11px] bg-astro-500/10 text-astro-300 border border-astro-500/20 animate-pulse" style={{ animationDelay: `${i * 0.2}s` }}>{s}</span>
          ))}
        </div>
      ) : (
        <Link to="/" className="btn-primary inline-flex px-7 py-3">◈ 前往研究工作台</Link>
      )}
    </div>
  )
}

/* ── 议会结果回退面板 ── */
function ParliamentFallbackDashboard() {
  const eval_ = loadParliamentEval()
  const dims = [
    { k: 'factual_accuracy', l: '事实准确', w: '30%' },
    { k: 'strategic_actionability', l: '策略可行', w: '25%' },
    { k: 'audience_fit', l: '受众匹配', w: '20%' },
    { k: 'cultural_sensitivity', l: '文化敏感', w: '15%' },
    { k: 'narrative_fluency', l: '叙事流畅', w: '10%' },
  ]

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
  const hasScores = vals.some(v => v > 0)
  const weighted = vals.reduce((acc, v, i) => acc + v * parseFloat(dims[i].w) / 100, 0)

  return (
    <div className="space-y-6">
      {parliamentData && (
        <section className="panel panel-beam p-6">
          <p className="sec-label mb-1">Analysis Overview</p>
          <h3 className="text-base font-bold text-white mb-5">AI Scientist 分析概览{parliamentData.topic ? `：${parliamentData.topic}` : ''}</h3>
          <div className="grid grid-cols-5 gap-4">
            {[
              { l: '辩论轮次', v: parliamentData.total_rounds },
              { l: '动议数', v: parliamentData.motion_count },
              { l: '表决数', v: parliamentData.vote_count },
              { l: '策略数', v: parliamentData.strategy_count },
              { l: '校验数', v: parliamentData.verify_count },
            ].map(s => (
              <div key={s.l} className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4 text-center hover:border-astro-500/25 transition-colors">
                <div className="stat-num text-2xl text-white">{s.v ?? 0}</div>
                <div className="text-[10px] text-slate-500 mt-1">{s.l}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {hasScores && (
        <section className="panel panel-beam p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">五维评分 <span className="sec-label">Evaluation</span></h3>
            <span className="text-[11px] text-slate-500">加权平均 <b className={`stat-num text-xl ${weighted >= 75 ? 'text-aurora-400' : 'text-nova-400'}`}>{weighted.toFixed(1)}</b></span>
          </div>
          <div className="grid grid-cols-5 gap-4">
            {dims.map((d, i) => (
              <div key={d.k} className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4 text-center">
                <div className={`stat-num text-3xl mb-1 ${vals[i] >= 75 ? 'text-aurora-400' : vals[i] >= 60 ? 'text-nova-400' : 'text-flare-400'}`}>{vals[i]}</div>
                <div className="text-[11px] text-slate-400">{d.l}</div>
                <div className="mt-2.5 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-1000 ${vals[i] >= 75 ? 'bg-aurora-400' : vals[i] >= 60 ? 'bg-nova-400' : 'bg-flare-400'}`} style={{ width: `${vals[i]}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 text-center">
            <Link to="/parliament" className="text-[11px] text-astro-400/70 hover:text-astro-300 transition-colors">查看完整工作流记录 →</Link>
          </div>
        </section>
      )}

      {parliamentData?.search_sources && parliamentData.search_sources.length > 0 && (
        <SearchSources sources={parliamentData.search_sources} />
      )}
    </div>
  )
}

/* ── 搜索来源列表 ── */
function SearchSources({ sources }: { sources: { url: string; title: string; content: string; score: number; source: string }[] }) {
  return (
    <section className="panel panel-beam p-6">
      <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
        🌐 联网搜索内容 <span className="sec-label">Tavily + QwenWebSearch</span>
      </h3>
      <div className="space-y-2.5">
        {sources.map((source, i) => (
          <a key={i} href={source.url || undefined} target="_blank" rel="noopener noreferrer"
            className={`block p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] transition-all group ${source.url ? 'hover:border-astro-500/30 hover:bg-astro-500/[0.04] cursor-pointer' : 'cursor-default'}`}>
            <div className="flex items-start gap-3">
              <span className={`shrink-0 mt-1 w-2 h-2 rounded-full ${source.source === 'TavilySearch' ? 'bg-astro-400' : 'bg-purple-400'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2.5">
                  <span className={`text-[9px] font-mono px-2 py-0.5 rounded border ${source.source === 'TavilySearch' ? 'text-astro-300 border-astro-500/25 bg-astro-500/5' : 'text-purple-300 border-purple-400/25 bg-purple-500/5'}`}>
                    {source.source === 'TavilySearch' ? 'TAVILY' : 'QWEN'}
                  </span>
                  <span className="text-sm text-white group-hover:text-astro-300 transition-colors truncate">{source.title}</span>
                </div>
                {source.url && <div className="text-[11px] text-slate-600 truncate mt-1 font-mono">{source.url}</div>}
                {source.content && <div className="text-xs text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">{source.content}</div>}
              </div>
              {source.score > 0 && <span className="text-[10px] font-mono text-slate-600 whitespace-nowrap">相关度 {(source.score * 100).toFixed(0)}%</span>}
            </div>
          </a>
        ))}
      </div>
    </section>
  )
}

/* ── 主面板 ── */
function Dashboard() {
  const { state } = useStore()
  const result = state.result

  if (!result) return <ParliamentFallbackDashboard />

  const { context_analysis, science_facts, hypotheses, strategies, evaluation } = result

  const frameworkDist = context_analysis?.framework_distribution || {}
  const frameworkColors: Record<string, string> = {
    competition: '#fb7185', cooperation: '#fbbf24', progress: '#38d4f8',
    threat: '#f43f5e', development: '#34d399',
  }
  const frameworkNames: Record<string, string> = {
    competition: '竞争框架', cooperation: '合作框架', progress: '进步框架',
    threat: '威胁框架', development: '发展框架',
  }
  const pieData = Object.entries(frameworkDist).map(([key, value]) => ({
    value: typeof value === 'number' ? value : 0,
    name: frameworkNames[key] || key,
    itemStyle: { color: frameworkColors[key] || '#64748b' },
  }))

  const pieOption = {
    title: { text: '传播框架分布', left: 'center', textStyle: { color: '#e2e8f0', fontSize: 13, fontWeight: 600 } },
    tooltip: { trigger: 'item', backgroundColor: '#0e1c38', borderColor: 'rgba(56,212,248,0.3)', textStyle: { color: '#e2e8f0' } },
    series: [{
      type: 'pie', radius: ['42%', '70%'], center: ['50%', '56%'],
      data: pieData.length > 0 ? pieData : [{ value: 1, name: '暂无数据', itemStyle: { color: '#1e293b' } }],
      label: { color: '#94a3b8', fontSize: 11 },
      itemStyle: { borderColor: '#0a1428', borderWidth: 2 },
    }],
    backgroundColor: 'transparent',
  }

  const countries = (context_analysis?.country_analysis || []).map((c: Record<string, unknown>) => (c.country as string) || '')
  const sentimentData = (context_analysis?.country_analysis || []).map((c: Record<string, unknown>) => {
    const dist = c.sentiment_distribution as Record<string, number> | undefined
    return {
      positive: (dist?.positive ?? (c.positive_ratio as number) ?? 0),
      neutral: (dist?.neutral ?? (c.neutral_ratio as number) ?? 0),
      negative: (dist?.negative ?? (c.negative_ratio as number) ?? 0),
    }
  })

  const barOption = {
    title: { text: '各国情感倾向', left: 'center', textStyle: { color: '#e2e8f0', fontSize: 13, fontWeight: 600 } },
    tooltip: { trigger: 'axis', backgroundColor: '#0e1c38', borderColor: 'rgba(56,212,248,0.3)', textStyle: { color: '#e2e8f0' } },
    grid: { left: 40, right: 20, top: 60, bottom: 30 },
    xAxis: { type: 'category', data: countries.length ? countries : ['暂无'], axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
    series: [
      { name: '正面', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.positive * 100)), itemStyle: { color: '#34d399' }, barWidth: 22 },
      { name: '中性', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.neutral * 100)), itemStyle: { color: '#fbbf24' } },
      { name: '负面', type: 'bar', stack: 'total', data: sentimentData.map(d => Math.round(d.negative * 100)), itemStyle: { color: '#fb7185' } },
    ],
    legend: { textStyle: { color: '#94a3b8' }, top: 28 },
    backgroundColor: 'transparent',
  }

  const radarOption = {
    title: { text: '五维评分', left: 'center', textStyle: { color: '#e2e8f0', fontSize: 13, fontWeight: 600 } },
    radar: {
      indicator: [
        { name: '事实准确度', max: 100 }, { name: '策略可操作性', max: 100 },
        { name: '受众适配度', max: 100 }, { name: '文化敏感性', max: 100 }, { name: '叙事流畅度', max: 100 },
      ],
      axisName: { color: '#94a3b8', fontSize: 10 },
      center: ['50%', '58%'],
      splitArea: { areaStyle: { color: ['rgba(56,212,248,0.02)', 'rgba(56,212,248,0.04)'] } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          evaluation.factual_accuracy, evaluation.strategic_actionability,
          evaluation.audience_fit, evaluation.cultural_sensitivity, evaluation.narrative_fluency,
        ],
        name: '最终评分',
        areaStyle: { color: 'rgba(12,184,232,0.18)' },
        lineStyle: { color: '#38d4f8', width: 2 },
        itemStyle: { color: '#38d4f8' },
      }],
    }],
    backgroundColor: 'transparent',
  }

  const weightedTotal = (
    evaluation.factual_accuracy * 0.30 + evaluation.strategic_actionability * 0.25 +
    evaluation.audience_fit * 0.20 + evaluation.cultural_sensitivity * 0.15 + evaluation.narrative_fluency * 0.10
  ).toFixed(1)

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-end justify-between">
        <div>
          <p className="sec-label mb-1">International Communication Analysis</p>
          <h2 className="font-display text-2xl font-bold text-white">国际传播分析中心</h2>
        </div>
        <span className="text-xs font-mono text-slate-500">议题：{result.topic} · {result.timestamp.slice(0, 19).replace('T', ' ')}</span>
      </div>

      {/* 统计条 */}
      <div className="grid grid-cols-5 gap-4">
        {[
          { label: '科学事实', value: String(science_facts?.key_facts?.length || 0), c: 'text-astro-300' },
          { label: '传播假设', value: String(hypotheses?.length || 0), c: 'text-white' },
          { label: '传播策略', value: String(strategies?.length || 0), c: 'text-white' },
          { label: '迭代轮数', value: String(result.iteration_count), c: 'text-white' },
          { label: '加权总分', value: weightedTotal, c: Number(weightedTotal) >= 75 ? 'text-aurora-400' : 'text-nova-400' },
        ].map((item, i) => (
          <div key={i} className="panel panel-beam p-4 text-center animate-rise" style={{ animationDelay: `${i * 0.06}s` }}>
            <div className={`stat-num text-3xl ${item.c}`}>{item.value}</div>
            <div className="text-[11px] text-slate-500 mt-1">{item.label}</div>
          </div>
        ))}
      </div>

      {/* 图表行 */}
      <div className="grid grid-cols-2 gap-5">
        <div className="panel panel-beam p-5"><ReactECharts option={pieOption} style={{ height: 300 }} /></div>
        <div className="panel panel-beam p-5"><ReactECharts option={barOption} style={{ height: 300 }} /></div>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <div className="panel panel-beam p-5"><ReactECharts option={radarOption} style={{ height: 320 }} /></div>
        <div className="panel panel-beam p-6 space-y-6">
          <div>
            <h3 className="text-sm font-bold text-nova-400 mb-3 flex items-center gap-2">关键叙事点 <span className="sec-label">Key Narratives</span></h3>
            <ul className="space-y-2">
              {(context_analysis?.key_narratives || []).map((n, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
                  <span className="text-astro-400 mt-0.5 shrink-0">▸</span>{n}
                </li>
              ))}
              {!(context_analysis?.key_narratives?.length) && <li className="text-slate-600 text-sm">暂无</li>}
            </ul>
          </div>
          <div className="divider-glow" />
          <div>
            <h3 className="text-sm font-bold text-nova-400 mb-3 flex items-center gap-2">跨文化差异 <span className="sec-label">Cross-Cultural</span></h3>
            <ul className="space-y-2">
              {(context_analysis?.cross_cultural_differences || []).map((d, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
                  <span className="text-nova-400 mt-0.5 shrink-0">△</span>{d}
                </li>
              ))}
              {!(context_analysis?.cross_cultural_differences?.length) && <li className="text-slate-600 text-sm">暂无</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* 科学事实 */}
      <section className="panel panel-beam p-6">
        <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">科学事实提取 <span className="sec-label">Science Facts</span></h3>
        <div className="grid grid-cols-2 gap-3">
          {(science_facts?.key_facts || []).map((fact, i) => (
            <div key={i} className="flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-astro-500/20 transition-colors text-sm">
              <span className="text-astro-300 font-mono text-xs mt-0.5 shrink-0">F{i + 1}</span>
              <span className="text-slate-300 leading-relaxed">{fact}</span>
            </div>
          ))}
          {!(science_facts?.key_facts?.length) && <span className="text-slate-600 text-sm">暂无事实数据</span>}
        </div>
      </section>

      {/* 搜索来源 */}
      {result.search_sources && result.search_sources.length > 0 && <SearchSources sources={result.search_sources} />}
    </div>
  )
}

export default Dashboard
