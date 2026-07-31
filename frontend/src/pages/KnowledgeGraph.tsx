/**
 * 云观星传 V2.0 — 知识图谱
 * 三库知识中心 · 实体关系图谱 · 力导向可视化 · 分区浏览
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import { useStore } from '../store'
import { getKnowledgeGraph, getKGStats, searchEntities, getKGComponents, getKGComponentGraph } from '../api'

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
interface ComponentInfo { id: number; label: string; hub_type: string; node_count: number; edge_count: number }

function KnowledgeGraph() {
  const { state } = useStore()
  const [nodes, setNodes] = useState<KGNode[]>([])
  const [edges, setEdges] = useState<KGEdge[]>([])
  const [stats, setStats] = useState<{ node_count: number; edge_count: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ name: string; type: string }[]>([])

  // 分区浏览状态
  const [components, setComponents] = useState<ComponentInfo[]>([])
  const [selectedComponent, setSelectedComponent] = useState<number | 'all'>(0)

  // 加载连通分量列表
  const loadComponents = useCallback(async () => {
    try {
      const data = await getKGComponents()
      setComponents(data.components || [])
    } catch {
      // 后端不支持时静默降级
    }
  }, [])

  // 加载指定分区的图谱数据
  const loadComponentGraph = useCallback(async (componentId: number | 'all') => {
    setLoading(true)
    setError('')
    try {
      let graphData: { nodes: KGNode[]; edges: KGEdge[] }
      if (componentId === 'all') {
        graphData = await getKnowledgeGraph()
      } else {
        graphData = await getKGComponentGraph(componentId)
      }
      setNodes(graphData.nodes || [])
      setEdges(graphData.edges || [])
    } catch {
      const result = state.result
      if (result?.science_facts) {
        const entities = result.science_facts.entities || []
        const relations = result.science_facts.relations || []
        setNodes(entities.map((e: { name: string; entity_type: string; attributes?: Record<string, unknown> }) => ({ name: e.name, type: e.entity_type, attributes: e.attributes })))
        setEdges(relations.map((r: { subject: string; object: string; predicate: string; confidence: number }) => ({ source: r.subject, target: r.object, predicate: r.predicate, confidence: r.confidence })))
      } else {
        setError('无法加载知识图谱数据，请确认后端已启动或先运行分析')
      }
    } finally {
      setLoading(false)
    }
  }, [state.result])

  // 初始加载：统计 + 分量列表 + 默认第一个分量
  useEffect(() => {
    (async () => {
      try {
        const statsData = await getKGStats()
        const s = statsData as Record<string, unknown>
        setStats({ node_count: (s.total_entities as number) ?? 0, edge_count: (s.total_relations as number) ?? 0 })
      } catch { /* ignore */ }
      await loadComponents()
    })()
  }, [loadComponents])

  // 分量列表加载后，默认加载第一个分量
  useEffect(() => {
    if (components.length > 0) {
      loadComponentGraph(selectedComponent)
    } else if (components.length === 0) {
      // 可能后端没有分量接口，降级加载全量
      loadComponentGraph('all')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [components])

  const handleSelectComponent = (id: number | 'all') => {
    setSelectedComponent(id)
    loadComponentGraph(id)
  }

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
      animationDelay: (idx: number) => idx * 30,
      force: {
        repulsion: nodes.length > 60 ? 250 : 400,
        edgeLength: nodes.length > 60 ? [50, 120] : [80, 200],
        gravity: nodes.length > 60 ? 0.15 : 0.1,
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
      label: { show: nodes.length <= 80, color: '#cbd5e1', fontSize: 10, position: 'right', distance: 5 },
      edgeLabel: {
        show: nodes.length <= 50, fontSize: 9, color: '#64748b',
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
          <p className="text-xs text-slate-500 mt-1.5">三库知识中心 · 实体关系网络 · 分区浏览</p>
        </div>
        <button onClick={() => { loadComponents(); loadComponentGraph(selectedComponent) }} className="btn-ghost text-sm">⟳ 刷新数据</button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索实体（如：嫦娥七号、CNSA、JWST）..."
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
        <div className="panel p-5 text-center">
          <div className="stat-num text-3xl text-emerald-400">{components.length || '-'}</div>
          <div className="text-xs text-slate-500 mt-1">连通分区</div>
        </div>
        <div className="panel p-5 text-center">
          <div className="stat-num text-3xl text-amber-400">{nodes.length}</div>
          <div className="text-xs text-slate-500 mt-1">当前显示</div>
        </div>
      </div>

      {/* 分区选择器 */}
      {components.length > 0 && (
        <div className="panel p-4">
          <h3 className="text-[11px] font-bold text-astro-300 mb-3">
            选择浏览分区
            <span className="ml-2 text-slate-500 font-normal">（共 {components.length} 个连通子图，点击切换）</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {/* 全量按钮 */}
            <button
              onClick={() => handleSelectComponent('all')}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-all ${
                selectedComponent === 'all'
                  ? 'bg-astro-300/20 border-astro-300 text-astro-300 shadow-[0_0_8px_rgba(56,212,248,0.3)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300'
              }`}
            >
              🌐 全部（{stats?.node_count ?? '...'}节点）
            </button>
            {/* 各分量 */}
            {components.map(comp => (
              <button
                key={comp.id}
                onClick={() => handleSelectComponent(comp.id)}
                className={`px-3 py-1.5 rounded-lg text-xs border transition-all ${
                  selectedComponent === comp.id
                    ? 'bg-astro-300/20 border-astro-300 text-astro-300 shadow-[0_0_8px_rgba(56,212,248,0.3)]'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300'
                }`}
              >
                <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: typeColors[comp.hub_type] || '#64748b' }} />
                {comp.label}
                <span className="ml-1 text-slate-500">{comp.node_count}节点</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 图谱可视化 */}
      {nodes.length > 0 ? (
        <div className="panel p-4">
          {selectedComponent === 'all' && nodes.length > 100 && (
            <div className="mb-3 px-3 py-2 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs">
              ⚠️ 当前显示全量图谱（{nodes.length} 个节点），渲染可能较慢。建议选择单个分区浏览。
            </div>
          )}
          <ReactECharts
            option={graphOption}
            style={{ height: 600 }}
            onChartReady={handleChartReady}
            opts={{ renderer: 'canvas' }}
            notMerge={true}
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
