/**
 * 云观星传 - 全局状态管理
 * 管理分析任务生命周期和结果数据
 */
import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react'
import {
  startAnalysis, getTaskStatus, getTaskResult, getHistory,
  listWorkflowProjects, getWorkflowProject, createWorkflowProject,
  runWorkflowStage, approveWorkflowStage, getWorkflowStages,
  type PipelineResult, type ResearchProject, type WorkflowStageMeta,
} from './api'

export type AnalysisPhase =
  | 'idle'        // 未开始
  | 'submitting'  // 提交中
  | 'running'     // Pipeline 运行中
  | 'completed'   // 完成
  | 'error'       // 出错

export interface StepProgress {
  name: string
  display_name: string
  status: 'running' | 'completed' | 'error' | 'pending'
  message: string
}

export interface RoundProgress {
  label: string
  steps: StepProgress[]
}

interface AnalysisState {
  phase: AnalysisPhase
  taskId: string | null
  topic: string
  errorMessage: string
  result: PipelineResult | null
  history: { task_id: string; topic: string; timestamp: string; status: string; iteration_count: number }[]
  progress: { rounds: RoundProgress[] }
}

interface StoreContextValue {
  state: AnalysisState
  /** 启动分析 */
  runAnalysis: (topic: string, maxIterations?: number) => Promise<void>
  /** 重置状态 */
  reset: () => void
  /** 加载历史记录结果 */
  loadHistoryResult: (taskId: string) => Promise<void>
  /** 后端是否在线 */
  backendOnline: boolean | null
  setBackendOnline: (v: boolean) => void
  // ===== 科研工作流（7 智能体科研工作台）=====
  /** 科研流程阶段元数据 */
  stageMeta: WorkflowStageMeta[]
  /** 科研项目列表 */
  projects: ResearchProject[]
  /** 当前查看的科研项目 */
  currentProject: ResearchProject | null
  /** 更新当前项目（一键全流程轮询用） */
  setCurrentProject: (p: ResearchProject | null) => void
  /** 更新项目列表 */
  setProjects: (fn: (prev: ResearchProject[]) => ResearchProject[]) => void
  /** 刷新项目列表 */
  refreshProjects: () => Promise<void>
  /** 加载单个项目详情 */
  loadProject: (id: string) => Promise<void>
  /** 创建科研项目 */
  createProject: (title: string, interest: string) => Promise<ResearchProject>
  /** 执行阶段智能体 */
  runStage: (id: string, stage: number, inputs?: Record<string, unknown>) => Promise<Record<string, unknown> | null>
  /** 确认阶段产出物，推进到下一阶段 */
  approveStage: (id: string, stage: number) => Promise<void>
}

const initialState: AnalysisState = {
  phase: 'idle',
  taskId: null,
  topic: '',
  errorMessage: '',
  result: null,
  history: [],
  progress: { rounds: [] },
}

const StoreContext = createContext<StoreContextValue | null>(null)

// localStorage key 用于持久化运行中的任务
const RUNNING_TASK_KEY = 'ygxc_running_task'

function saveRunningTask(taskId: string, topic: string) {
  localStorage.setItem(RUNNING_TASK_KEY, JSON.stringify({ taskId, topic }))
}

function loadRunningTask(): { taskId: string; topic: string } | null {
  try {
    const raw = localStorage.getItem(RUNNING_TASK_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return null
}

function clearRunningTask() {
  localStorage.removeItem(RUNNING_TASK_KEY)
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AnalysisState>(initialState)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ===== 科研工作流状态 =====
  const [stageMeta, setStageMeta] = useState<WorkflowStageMeta[]>([])
  const [projects, setProjects] = useState<ResearchProject[]>([])
  const [currentProject, setCurrentProject] = useState<ResearchProject | null>(null)

  // 启动时加载历史记录 + 恢复运行中的任务
  useEffect(() => {
    getHistory().then(({ history }) => {
      setState(prev => ({
        ...prev,
        history: history.map(h => ({
          task_id: h.task_id,
          topic: h.topic,
          timestamp: h.timestamp,
          status: h.final_status,
          iteration_count: h.iteration_count,
        })),
      }))
    }).catch(() => { /* 后端未启动时忽略 */ })

    // 恢复刷新前正在运行的任务
    const running = loadRunningTask()
    if (running) {
      resumePolling(running.taskId, running.topic)
    }
  }, [])

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  /** 恢复对某个任务的轮询（页面刷新后调用） */
  const resumePolling = useCallback((taskId: string, topic: string) => {
    stopPolling()
    setState(prev => ({ ...prev, phase: 'running', taskId, topic, result: null, errorMessage: '' }))

    pollingRef.current = setInterval(async () => {
      try {
        const status = await getTaskStatus(taskId)
        if (status.progress) {
          setState(prev => ({ ...prev, progress: status.progress! as { rounds: RoundProgress[] } }))
        }
        if (status.status === 'completed' && status.has_result) {
          stopPolling()
          clearRunningTask()
          const result = await getTaskResult(taskId)
          setState(prev => ({
            ...prev,
            phase: 'completed',
            result,
            history: [
              { task_id: taskId, topic, timestamp: result.timestamp, status: result.final_status, iteration_count: result.iteration_count },
              ...prev.history.filter(h => h.task_id !== taskId),
            ].slice(0, 20),
          }))
        } else if (status.status.startsWith('error')) {
          stopPolling()
          clearRunningTask()
          setState(prev => ({ ...prev, phase: 'error', errorMessage: status.status }))
        }
      } catch {
        // 后端可能已重启，任务不存在了
        stopPolling()
        clearRunningTask()
        setState(prev => ({ ...prev, phase: 'idle' }))
      }
    }, 3000)
  }, [stopPolling])

  const runAnalysis = useCallback(async (topic: string, maxIterations: number = 3) => {
    stopPolling()

    setState(prev => ({
      ...prev,
      phase: 'submitting',
      topic,
      errorMessage: '',
      result: null,
    }))

    try {
      // 1. 提交任务
      const { task_id } = await startAnalysis(topic, maxIterations)

      setState(prev => ({ ...prev, phase: 'running', taskId: task_id }))
      saveRunningTask(task_id, topic)

      // 2. 轮询状态（每 3 秒）
      pollingRef.current = setInterval(async () => {
        try {
          const status = await getTaskStatus(task_id)

          // 更新进度
          if (status.progress) {
            setState(prev => ({ ...prev, progress: status.progress! as { rounds: RoundProgress[] } }))
          }

          if (status.status === 'completed' && status.has_result) {
            stopPolling()
            clearRunningTask()
            const result = await getTaskResult(task_id)
            setState(prev => ({
              ...prev,
              phase: 'completed',
              result,
              history: [
                { task_id, topic, timestamp: result.timestamp, status: result.final_status, iteration_count: result.iteration_count },
                ...prev.history.filter(h => h.task_id !== task_id),
              ].slice(0, 20),
            }))
          } else if (status.status.startsWith('error')) {
            stopPolling()
            clearRunningTask()
            setState(prev => ({
              ...prev,
              phase: 'error',
              errorMessage: status.status,
            }))
          }
          // 'running' 状态继续轮询
        } catch {
          // 轮询网络错误时不中断，继续尝试
        }
      }, 3000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '无法连接后端服务，请确认 API 已启动 (uvicorn api.main:app)'
      setState(prev => ({ ...prev, phase: 'error', errorMessage: msg }))
    }
  }, [stopPolling])

  const reset = useCallback(() => {
    stopPolling()
    clearRunningTask()
    setState(prev => ({ ...initialState, history: prev.history }))
  }, [stopPolling])

  const loadHistoryResult = useCallback(async (taskId: string) => {
    stopPolling()
    setState(prev => ({ ...prev, phase: 'submitting', result: null }))
    try {
      const result = await getTaskResult(taskId)
      setState(prev => ({
        ...prev,
        phase: 'completed',
        topic: result.topic,
        result,
      }))
    } catch {
      setState(prev => ({ ...prev, phase: 'error', errorMessage: '加载历史记录失败' }))
    }
  }, [stopPolling])

  // ===== 科研工作流方法 =====

  /** 加载阶段元数据（首页 Pipeline 渲染） */
  const refreshStageMeta = useCallback(async () => {
    try {
      const { stages } = await getWorkflowStages()
      setStageMeta(stages)
    } catch {
      /* 后端未启动时忽略 */
    }
  }, [])

  const refreshProjects = useCallback(async () => {
    try {
      const { projects: list } = await listWorkflowProjects()
      setProjects(list)
    } catch {
      /* 后端未启动时忽略 */
    }
  }, [])

  const loadProject = useCallback(async (id: string) => {
    const { project } = await getWorkflowProject(id)
    setCurrentProject(project)
    setProjects(prev => prev.map(p => (p.id === id ? project : p)))
  }, [])

  const createProject = useCallback(async (title: string, interest: string) => {
    const { project } = await createWorkflowProject(title, interest)
    setProjects(prev => [project, ...prev])
    setCurrentProject(project)
    return project
  }, [])

  const runStage = useCallback(async (id: string, stage: number, inputs: Record<string, unknown> = {}) => {
    const { output } = await runWorkflowStage(id, stage, inputs)
    const { project } = await getWorkflowProject(id)
    setCurrentProject(project)
    setProjects(prev => prev.map(p => (p.id === id ? project : p)))
    return output
  }, [])

  const approveStage = useCallback(async (id: string, stage: number) => {
    const { project } = await approveWorkflowStage(id, stage)
    setCurrentProject(project)
    setProjects(prev => prev.map(p => (p.id === id ? project : p)))
  }, [])

  // 初始化：加载阶段元数据与项目列表
  useEffect(() => {
    refreshStageMeta()
    refreshProjects()
  }, [refreshStageMeta, refreshProjects])

  return (
    <StoreContext.Provider value={{
      state, runAnalysis, reset, loadHistoryResult, backendOnline, setBackendOnline,
      stageMeta, projects, currentProject,
      setCurrentProject, setProjects,
      refreshProjects, loadProject, createProject, runStage, approveStage,
    }}>
      {children}
    </StoreContext.Provider>
  )
}

export function useStore() {
  const ctx = useContext(StoreContext)
  if (!ctx) throw new Error('useStore must be used within StoreProvider')
  return ctx
}
