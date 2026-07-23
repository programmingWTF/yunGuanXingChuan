import { useState, useEffect, useCallback, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import type { ECharts } from 'echarts'
import { useStore } from '../store'
import { getKnowledgeGraph, getKGStats, searchEntities } from '../api'

const typeColors: Record<string, string> = {
  mission: '#00D4FF',
  body: '#FFD700',
  technology: '#4CAF50',
  organization: '#FF6B35',
  person: '#E91E63',
  event: '#9C27B0',
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

  // 加载知识图谱数据
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
      // 如果 API 不可用，尝试从 pipeline 结果获取
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

  // 搜索实体
  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults([]); return }
    try {
      const res = await searchEntities(searchQuery.trim())
      setSearchResults(res.results || [])
    } catch {
      // 本地搜索 fallback
      const q = searchQuery.toLowerCase()
      setSearchResults(nodes.filter(n => n.name.toLowerCase().includes(q)).map(n => ({ name: n.name, type: n.type })))
    }
  }

  const chartRef = useRef<ECharts | null>(null)

  const handleChartReady = useCallback((instance: ECharts) => {
    chartRef.current = instance
  }, [])

  const graphOption = {
    // 状态切换渐变动画：控制 emphasis/blur 过渡（缓慢亮起/熄灭）
    stateAnimation: {
      duration: 800,
      easing: 'cubicInOut',
    },
    title: { text: `知识图谱${state.result ? ` - ${state.result.topic}` : ''}`, left: 'center', textStyle: { color: '#E0E0E0' } },
    tooltip: {
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
      // 初始动画
      animationDuration: 1200,
      animationEasing: 'cubicInOut',
      // 节点逐个缓入：产生星空逐一亮起的平滑效果
      animationDelay: (idx: number) => idx * 60,
      // series 级状态动画：确保 hover 高亮/恢复有平滑渐变
      stateAnimation: {
        duration: 800,
        easing: 'cubicInOut',
      },
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
        itemStyle: { color: typeColors[n.type] || '#888', borderColor: '#fff', borderWidth: 1 },
        category: n.type,
      })),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
        value: e.predicate || e.relation || '',
        lineStyle: { width: 2, opacity: 0.5 },
      })),
      // 节点标签
      label: {
        show: true,
        color: '#E0E0E0',
        fontSize: 10,
        position: 'right',
        distance: 5,
      },
      // 边标签（关系文字显示在线上）
      edgeLabel: {
        show: true,
        fontSize: 9,
        color: '#999',
        formatter: (params: { data: { value?: string } }) => params.data.value || '',
      },
      lineStyle: { color: 'source', curveness: 0.2, opacity: 0.5, width: 2 },
      // hover 时高亮相邻节点和边（内置状态系统，不触发 setOption，不会抖动）
      emphasis: {
        focus: 'adjacency',
        // 节点高亮样式
        itemStyle: {
          borderWidth: 2,
          shadowBlur: 12,
          shadowColor: 'rgba(255,255,255,0.3)',
        },
        // 边高亮样式
        lineStyle: {
          width: 3.5,
          opacity: 1,
        },
        label: {
          show: true,
        },
      },
      // 非高亮元素柔和渐隐
      blur: {
        itemStyle: {
          opacity: 0.15,
        },
        lineStyle: {
          opacity: 0.08,
        },
        label: {
          opacity: 0.15,
        },
      },
      scaleLimit: { min: 0.3, max: 3 },
    }],
    backgroundColor: 'transparent',
  }

  // 统计卡片数据
  const typeCounts: Record<string, number> = {}
  nodes.forEach(n => { typeCounts[n.type] = (typeCounts[n.type] || 0) + 1 })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-star-blue">🔗 知识图谱</h2>
        <button onClick={loadKG} className="px-4 py-2 rounded-lg bg-white/5 border border-star-blue/30 text-sm text-star-blue hover:bg-star-blue/10 transition-colors">
          🔄 刷新数据
        </button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="搜索实体（如：嫦娥六号、CNSA）..."
          className="flex-1 bg-white/5 border border-star-blue/30 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-star-blue"
        />
        <button onClick={handleSearch} className="btn-primary text-sm">搜索</button>
      </div>

      {/* 搜索结果 */}
      {searchResults.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-bold text-star-gold mb-2">搜索结果 ({searchResults.length})</h3>
          <div className="flex flex-wrap gap-2">
            {searchResults.map((r, i) => (
              <span key={i} className="px-3 py-1 rounded-full text-sm" style={{ backgroundColor: `${typeColors[r.type] || '#888'}33`, color: typeColors[r.type] || '#888' }}>
                {r.name} ({typeNames[r.type] || r.type})
              </span>
            ))}
          </div>
        </div>
      )}

      {error && <div className="card p-4 text-red-400 text-sm">{error}</div>}
      {loading && <div className="card p-4 text-star-blue text-sm animate-pulse">加载知识图谱数据中...</div>}

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-star-blue">{stats?.node_count ?? nodes.length}</div>
          <div className="text-sm text-gray-400">实体总数</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold text-star-gold">{stats?.edge_count ?? edges.length}</div>
          <div className="text-sm text-gray-400">关系总数</div>
        </div>
        {Object.entries(typeCounts).slice(0, 2).map(([type, count]) => (
          <div key={type} className="card p-4 text-center">
            <div className="text-2xl font-bold" style={{ color: typeColors[type] || '#888' }}>{count}</div>
            <div className="text-sm text-gray-400">{typeNames[type] || type}</div>
          </div>
        ))}
      </div>

      {/* 图谱可视化 */}
      {nodes.length > 0 ? (
        <div className="card p-4">
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
          <div className="card p-8 text-center text-gray-500">
            暂无图谱数据。请确认后端已启动，或先运行分析任务。
          </div>
        )
      )}

      {/* 图例 */}
      <div className="card p-4">
        <h3 className="text-lg font-bold mb-3 text-star-gold">图例说明</h3>
        <div className="flex gap-6 text-sm flex-wrap">
          {Object.entries(typeNames).map(([type, name]) => (
            <span key={type} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: typeColors[type] }} />
              {name} ({type})
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export default KnowledgeGraph
