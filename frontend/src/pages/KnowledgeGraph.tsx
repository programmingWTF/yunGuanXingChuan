/**
 * 云观星传 V2.0 — 知识图谱
 * 三库知识中心 · 实体关系图谱 · 力导向可视化
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import { useStore } from '../store'
import { getKnowledgeGraph, getKGStats, searchEntities } from '../api'

const typeColors: Record<string, string> = {
  mission: '#38d4f8',
  body: '#fbbf24',
  technology: '#34d399',
  organization: '#ff6b35',
  person: '#fb7185',
  event: '#a78bfa',
}

const typeNames: Record<string, string> = {
  mission: '任务', body: '天体', technology: '技术',
  organization: '机构', person: '人物', event: '事件',
}

interface KGNode { name: string; type: string; attributes?: Record<string, unknown> }
interface KGEdge { source: string; target: string; predicate?: string; relation?: string; confidence?: number }

function KnowledgeGraph() {
  const { state } = useStore()
  const [nodes, setNodes] = useState<KGNode[]>([])
  const [edges, setEdges] = useState<KGEdge[]>([])
  const [stats, setStats] = useState<{ node_count: number; edge_count: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ name: string; type: string }[]>([])

  const loadKG = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [graphData, statsData] = await Promise.all([
        getKnowledgeGraph(),
        getKGStats(),
      ])
      setNodes(graphData.nodes || [])
      setEdges(graphData.edges || [])
      const s = statsData as Record<string, unknown>
      setStats({ node_count: (s.total_entities as number) ?? (s.node_count as number) ?? 0, edge_count: (s.total_relations as number) ?? (s.edge_count as number) ?? 0 })
    } catch {
      const result = state.result
      if (result?.science_facts) {
        const entities = result.science_facts.entities || []
        const relations = result.science_facts.relations || []
        setNodes(entities.map(e => ({ name: e.name, type: e.entity_type, attributes: e.attributes })))
        setEdges(relations.map(r => ({ source: r.subject, target: r.object, predicate: r.predicate, confidence: r.confidence })))
        setStats({ node_count: entities.length, edge_count: relations.length })
      } else {
        setError('无法加载知识图谱数据，请确认后端已启动或先运行分析')
      }
    } finally {
      setLoading(false)
    }
  }, [state.result])

  useEffect(() => { loadKG() }, [loadKG])

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults([]); return }
    try {
      const res = await searchEntities(searchQuery.trim())
      setSearchResults(res.results || [])
    } catch {
      const q = searchQuery.toLowerCase()
      setSearchResults(nodes.filter(n => n.name.toLowerCase().includes(q)).map(n => ({ name: n.name, type: n.type })))
    }
  }

  const chartRef = useRef<ECharts | null>(null)
  const handleChartReady = useCallback((instance: ECharts) => { chartRef.current = instance }, [])

  const graphOption = {
    stateAnimation: { duration: 800, easing: 'cubicInOut' },
    tooltip: {
      backgroundColor: 'rgba(6,13,28,0.95)',
      borderColor: 'rgba(56,212,248,0.3)',
      textStyle: { color: '#dce7f5' },
      formatter: (params: { dataType: string; data: Record<string, unknown> }) => {
        if (params.dataType === 'node') {
          const d = params.data as { name: string; category?: string }
          return `<b>${d.name}</b><br/>类型: ${typeNames[d.category || ''] || d.category || ''}`
        }
        if (params.dataType === 'edge') {
          const d = params.data as { source: string; target: string; value?: string }
          const rel = d.value || ''
          return `${d.source} <b>${rel ? '→ ' + rel + ' →' : '→'}</b> ${d.target}`
        }
        return ''
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      animationDuration: 1200,
      animationEasing: 'cubicInOut',
      animationDelay: (idx: number) => idx * 60,
      stateAnimation: { duration: 800, easing: 'cubicInOut' },
      force: {
        repulsion: 400,
        edgeLength: [80, 200],
        gravity: 0.1,
        friction: 0.9,
        layoutAnimation: true,
        initSpeed: 3,
      },
      data: nodes.map(n => ({
        name: n.name,
        symbolSize: n.type === 'mission' ? 40 : 24,
        itemStyle: {
          color: typeColors[n.type] || '#64748b',
          borderColor: 'rgba(255,255,255,0.5)',
          borderWidth: 1,
          shadowBlur: 10,
          shadowColor: typeColors[n.type] || '#64748b',
        },
        category: n.type,
      })),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
        value: e.predicate || e.relation || '',
        lineStyle: { width: 2, opacity: 0.5 },
      })),
      label: { show: true, color: '#cbd5e1', fontSize: 10, position: 'right', distance: 5 },
      edgeLabel: {
        show: true, fontSize: 9, color: '#64748b',
        formatter: (params: { data: { value?: string } }) => params.data.value || '',
      },
      lineStyle: { color: 'source', curveness: 0.2, opacity: 0.5, width: 2 },
      emphasis: {
        focus: 'adjacency',
        itemStyle: { borderWidth: 2, shadowBlur: 16, shadowColor: 'rgba(56,212,248,0.6)' },
        lineStyle: { width: 3.5, opacity: 1 },
        label: { show: true },
      },
      blur: {
        itemStyle: { opacity: 0.15 },
        lineStyle: { opacity: 0.08 },
        label: { opacity: 0.15 },
      },
      scaleLimit: { min: 0.3, max: 3 },
    }],
    backgroundColor: 'transparent',
  }

  const typeCounts: Record<string, number> = {}
  nodes.forEach(n => { typeCounts[n.type] = (typeCounts[n.type] || 0) + 1 })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <p className="sec-label mb-1">Knowledge Graph</p>
          <h2 className="font-display text-2xl font-bold text-white">知识图谱</h2>
          <p className="text-xs text-slate-500 mt-1.5">三库知识中心 · 实体关系网络 · 力导向布局</p>
        </div>
        <button onClick={loadKG} className="btn-ghost text-sm">⟳ 刷新数据</button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索实体（如：嫦娥六号、CNSA、JWST）..."
          className="input-field flex-1"
        />
        <button onClick={handleSearch} className="btn-primary text-sm">搜索</button>
      </div>

      {/* 搜索结果 */}
      {searchResults.length > 0 && (
        <div className="panel p-4">
          <h3 className="text-[11px] font-bold text-nova-400 mb-2.5">搜索结果（{searchResults.length}）</h3>
          <div className="flex flex-wrap gap-2">
            {searchResults.map((r, i) => (
              <span key={i} className="px-3 py-1 rounded-md text-xs border"
                style={{ backgroundColor: `${typeColors[r.type] || '#64748b'}1a`, color: typeColors[r.type] || '#94a3b8', borderColor: `${typeColors[r.type] || '#64748b'}40` }}>
                {r.name} · {typeNames[r.type] || r.type}
              </span>
            ))}
          </div>
        </div>
      )}

      {error && <div className="panel p-4 text-flare-400 text-sm">{error}</div>}
      {loading && <div className="panel p-4 text-astro-300 text-sm animate-pulse">加载知识图谱数据中...</div>}

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="panel p-5 text-center">
          <div className="stat-num text-3xl text-astro-300">{stats?.node_count ?? nodes.length}</div>
          <div className="text-xs text-slate-500 mt-1">实体总数</div>
        </div>
        <div className="panel p-5 text-center">
          <div className="stat-num text-3xl text-nova-400">{stats?.edge_count ?? edges.length}</div>
          <div className="text-xs text-slate-500 mt-1">关系总数</div>
        </div>
        {Object.entries(typeCounts).slice(0, 2).map(([type, count]) => (
          <div key={type} className="panel p-5 text-center">
            <div className="stat-num text-3xl" style={{ color: typeColors[type] || '#94a3b8' }}>{count}</div>
            <div className="text-xs text-slate-500 mt-1">{typeNames[type] || type}</div>
          </div>
        ))}
      </div>

      {/* 图谱可视化 */}
      {nodes.length > 0 ? (
        <div className="panel p-4">
          <ReactECharts
            option={graphOption}
            style={{ height: 600 }}
            onChartReady={handleChartReady}
            opts={{ renderer: 'canvas' }}
            notMerge={false}
          />
        </div>
      ) : (
        !loading && !error && (
          <div className="panel p-12 text-center text-slate-600 text-sm">
            暂无图谱数据。请确认后端已启动，或先在研究工作台运行分析任务。
          </div>
        )
      )}

      {/* 图例 */}
      <div className="panel p-5">
        <h3 className="text-[11px] font-bold text-astro-300 mb-3">图例说明</h3>
        <div className="flex gap-6 text-sm flex-wrap">
          {Object.entries(typeNames).map(([type, name]) => (
            <span key={type} className="flex items-center gap-2 text-slate-400">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: typeColors[type], boxShadow: `0 0 8px ${typeColors[type]}` }} />
              {name} <span className="text-slate-600 font-mono text-xs">{type}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export default KnowledgeGraph
