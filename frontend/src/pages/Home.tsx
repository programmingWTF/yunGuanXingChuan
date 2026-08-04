/**
 * 云观星传 - 科研首页（科研驾驶舱）
 *
 * 评委第一眼看到的页面：
 * - 今日科技热点
 * - 我的科研项目统计
 * - AI 科研流程（Research Pipeline 时间轴，点击进入对应页面）
 * - 最近任务 / 快速开始研究
 */
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useStore } from '../store'
import ResearchPipeline from '../components/ResearchPipeline'

/** 今日热点（示例数据，后续可接统一搜索后端实时热点） */
const HOT_TOPICS = [
  { tag: '航天', title: '朱雀2号火箭成功首飞', source: '科技日报' },
  { tag: '深空', title: '嫦娥七号探测器任务规划公布', source: 'CNSA' },
  { tag: '天文', title: 'FAST 发现快速射电暴新样本', source: '中科院' },
  { tag: '国际', title: '多国联合月球科研站进展', source: '新华社' },
]

export default function Home() {
  const { projects, stageMeta, refreshProjects, createProject, currentProject } = useStore()
  const navigate = useNavigate()
  const [interest, setInterest] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  const activeCount = projects.filter(p => p.status === 'active').length
  const doneCount = projects.filter(p => p.status === 'completed').length
  const literatureCount = projects.reduce((acc, p) => {
    const lit = p.stages['2']
    return acc + (lit && lit.output && Array.isArray(lit.output.references) ? (lit.output.references as unknown[]).length : 0)
  }, 0)

  const handleQuickStart = async (e: FormEvent) => {
    e.preventDefault()
    if (!interest.trim()) return
    setCreating(true)
    setError('')
    try {
      const project = await createProject('', interest.trim())
      navigate(`/projects?focus=${project.id}`)
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : null
      setError(status === 404
        ? '后端尚未包含 /api/workflow 路由（需先合并后端 PR #52），或服务未启动'
        : '创建项目失败，请确认后端服务已启动（uvicorn api.main:app）')
    } finally {
      setCreating(false)
    }
  }

  const latestStages = currentProject?.stages ?? null
  const latestCurrentStage = currentProject?.current_stage ?? 1

  return (
    <div className="space-y-6">
      {/* 顶部欢迎条 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">科研驾驶舱</h2>
          <p className="text-xs text-slate-500 mt-1">以研究者为中心，与 7 位科研智能体协作，共同完成论文产出</p>
        </div>
        <Link to="/projects" className="btn-primary text-xs">＋ 新建研究项目</Link>
      </div>

      {/* 上排：热点 + 项目统计 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* 今日科技热点 */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="sec-label !mb-0">今日科技热点</h3>
            <span className="text-[9px] font-mono text-astro-400/70">TRENDING</span>
          </div>
          <div className="space-y-3">
            {HOT_TOPICS.map((t, i) => (
              <div key={i} className="flex items-center gap-3 group">
                <span className="w-1.5 h-1.5 rounded-full bg-flare-400/80 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 truncate group-hover:text-astro-300 transition-colors">{t.title}</p>
                  <p className="text-[10px] text-slate-600">{t.source}</p>
                </div>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400">{t.tag}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 我的科研项目统计 */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="sec-label !mb-0">我的科研项目</h3>
            <span className="text-[9px] font-mono text-astro-400/70">PROJECTS</span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-white/[0.03] border border-white/10 py-4">
              <p className="font-display text-3xl font-bold text-astro-300">{activeCount}</p>
              <p className="text-[10px] text-slate-500 mt-1">进行中</p>
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-white/10 py-4">
              <p className="font-display text-3xl font-bold text-aurora-300">{doneCount}</p>
              <p className="text-[10px] text-slate-500 mt-1">已完成</p>
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-white/10 py-4">
              <p className="font-display text-3xl font-bold text-slate-300">{literatureCount}</p>
              <p className="text-[10px] text-slate-500 mt-1">文献梳理</p>
            </div>
          </div>
          <div className="mt-4 text-center">
            <Link to="/projects" className="text-xs text-astro-400 hover:text-astro-300 transition-colors">查看全部项目 →</Link>
          </div>
        </div>

        {/* 快速开始 */}
        <div className="card p-5">
          <h3 className="sec-label !mb-3">快速开始研究</h3>
          <form onSubmit={handleQuickStart} className="space-y-3">
            <textarea
              value={interest}
              onChange={e => setInterest(e.target.value)}
              placeholder="输入你的研究兴趣，如：朱雀2号火箭的国际报道"
              rows={3}
              className="w-full rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60 resize-none"
            />
            {error && <p className="text-[11px] text-flare-400">{error}</p>}
            <button
              type="submit"
              disabled={creating || !interest.trim()}
              className="btn-primary w-full text-xs disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? '创建中…' : '开始科研流程 →'}
            </button>
          </form>
        </div>
      </div>

      {/* AI 科研流程（Research Pipeline） */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="sec-label !mb-1">AI 科研流程</h3>
            <p className="text-[11px] text-slate-500">选题 → 文献 → Gap → RQ → 方法 → 分析 → 写作 → 评审，点击节点进入对应科研页面</p>
          </div>
          {stageMeta.length > 0 && (
            <span className="text-[9px] font-mono text-slate-600 tracking-widest">{stageMeta.length} STAGES</span>
          )}
        </div>
        <ResearchPipeline stages={latestStages} currentStage={latestCurrentStage} />
      </div>
    </div>
  )
}
