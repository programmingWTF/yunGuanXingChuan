/**
 * 云观星传 - 科研流程页面占位组件
 *
 * 科研流程页面组（选题孵化/文献综述/研究设计/方法推荐/数据分析/学术写作/同行评审）
 * 由配套 Issue（前端科研流程页面组）开发实现。本组件先承载路由与后端 API 契约，
 * 保证 9 页面科研工作台框架完整可达，并展示当前项目在该阶段的状态。
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'
import ResearchPipeline, { PIPELINE_NODES } from '../components/ResearchPipeline'
import type { PipelineNode } from '../components/ResearchPipeline'

interface StagePlaceholderProps {
  stage: number        // 对应后端阶段 1-7
}

export default function StagePlaceholder({ stage }: StagePlaceholderProps) {
  const { currentProject, loadProject, projects } = useStore()
  const meta = PIPELINE_NODES.find(n => n.stage === stage)

  // 侧边栏直达流程页且未选中项目时，自动加载最新项目作为上下文
  useEffect(() => {
    if (!currentProject && projects.length > 0) {
      loadProject(projects[0].id).catch(() => { /* ignore */ })
    }
  }, [currentProject, projects, loadProject])

  return (
    <div className="space-y-6">
      {/* 页面头 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">
            {meta?.icon} {meta?.label}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {meta?.en} · 对应科研流程第 {stage} 阶段
          </p>
        </div>
        <span className="text-[9px] font-mono text-slate-600 tracking-widest">STAGE {stage}</span>
      </div>

      {/* 当前进度条 */}
      <div className="card p-4">
        <ResearchPipeline
          stages={currentProject?.stages ?? null}
          currentStage={currentProject?.current_stage ?? 1}
          compact
        />
      </div>

      <div className="card p-8 text-center space-y-4">
        <div className="text-5xl">{meta?.icon ?? '🔧'}</div>
        <h3 className="font-display text-xl font-bold text-white">{meta?.label}页面建设中</h3>
        <p className="text-sm text-slate-500 max-w-xl mx-auto">
          该科研流程页面由「前端科研流程页面组」Issue 开发（选题孵化 → 文献综述 → 研究设计
          → 方法推荐 → 数据分析 → 学术写作 → 同行评审），将复用本工作台的
          <code className="text-astro-300"> /api/workflow/* </code>
          接口：执行阶段（POST run）、产出物（GET result）、确认推进（POST approve）。
        </p>

        {/* API 契约预览 */}
        <div className="max-w-2xl mx-auto text-left">
          <p className="sec-label !mb-2">后端 API 契约（已就绪）</p>
          <pre className="text-[11px] text-slate-400 bg-black/25 rounded-xl p-4 overflow-x-auto">
{`POST /api/workflow/projects                         创建项目
POST /api/workflow/projects/{id}/stages/${stage}/run   执行阶段 ${stage}（同步）
GET  /api/workflow/projects/{id}/stages/${stage}/result 阶段产出物
POST /api/workflow/projects/{id}/stages/${stage}/approve 确认并推进
GET  /api/workflow/projects/{id}/export?fmt=md|json    汇总导出`}
          </pre>
        </div>

        {currentProject && (
          <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
            <span>当前项目：{currentProject.title}</span>
            <span className="text-slate-600">·</span>
            <span>阶段 {currentProject.current_stage}/7</span>
            <button
              onClick={() => loadProject(currentProject.id)}
              className="text-astro-400 hover:text-astro-300 ml-2"
            >
              刷新状态
            </button>
          </div>
        )}
        {!currentProject && (
          <div className="flex items-center justify-center gap-2 text-xs text-slate-500">
            <span>暂无项目上下文 —— 请先到 <Link to="/projects" className="text-astro-400 hover:text-astro-300">我的项目</Link> 创建研究项目</span>
          </div>
        )}
      </div>
    </div>
  )
}

export type { PipelineNode }
