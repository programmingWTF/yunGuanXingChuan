/**
 * 云观星传 - API 服务层
 * 所有后端接口调用
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // Pipeline 可能运行较久，5分钟超时
  withCredentials: true, // 会话 Cookie（httpOnly，same-origin）
})

// 论文上传直连入口：upload3.liguiyu.com:10443（灰云 DNS-only → 公网 IP:10443 → NPM → 云观星传后端），
// 不走 CF 代理（绕开 100MB/100s 限制）。跨域上传无法带 Cookie，改用 Authorization: Bearer <token>。
// 探测失败自动回退同域（tzb.liguiyu.com，CF 代理路径），保证功能始终可用（对齐团日资料 FAST_BASE 模式）。
const UPLOAD_BASE = 'https://upload3.liguiyu.com:10443'

// 直连入口探测缓存：'' = 回退同域，非空 = 直连
let uploadBaseCache: string | null = null
let uploadBaseProbe: Promise<string> | null = null
async function resolveUploadBase(): Promise<string> {
  if (uploadBaseCache !== null) return uploadBaseCache
  if (!uploadBaseProbe) {
    uploadBaseProbe = (async () => {
      try {
        await axios.get(`${UPLOAD_BASE}/api/library/health`, { timeout: 5000 })
        uploadBaseCache = UPLOAD_BASE
      } catch {
        uploadBaseCache = '' // upload3 未就绪 → 同域上传
      }
      return uploadBaseCache
    })()
  }
  return uploadBaseProbe
}

// 跨域上传用的会话 token（内存态；登录 / me 探测时由后端下发，刷新后由 getMe 重新获取）
let authToken: string | null = null
export function setAuthToken(t: string | null) {
  authToken = t
}
export function getAuthToken(): string | null {
  return authToken
}

// 统一错误处理：后端 FastAPI 的 4xx 会带 detail，转成可读 message
// （如「阶段 3 未解锁：当前进度在第 2 阶段」），避免只看到裸 400
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail
    if (detail) {
      err.message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
    return Promise.reject(err)
  },
)

// ============ 类型定义 ============

export interface EvaluationScores {
  factual_accuracy: number
  strategic_actionability: number
  audience_fit: number
  cultural_sensitivity: number
  narrative_fluency: number
}

export interface Evidence {
  source: string
  quote: string
  relevance: number
  evidence_type: string
}

export interface Hypothesis {
  hypothesis_id: string
  statement: string
  framework: string
  target_countries: string[]
  evidence_chain: Evidence[]
  verification_path: string
  confidence: number
  kg_entities_involved: string[]
  falsification_criteria: string
}

export interface Strategy {
  strategy_id: string
  target_audience: string
  narrative_persona: string
  narrative_angle: string
  key_messages: string[]
  channel_recommendation: string[]
  cultural_adaptations: string[]
  sample_text: string
  expected_effect: string
  risks: string[]
}

export interface VerificationResult {
  claim: string
  status: string
  rag_evidence: string | null
  kg_match: string | null
  cross_source_agreement: boolean | null
  confidence: number
  notes: string
}

export interface IterationFeedback {
  dimension: string
  current_score: number
  issue: string
  suggestion: string
  target_agent: string
}

export interface SearchSource {
  url: string
  title: string
  content: string
  /** 可选：工作流阶段产出物（search_sources）不携带 score，仅旧版 pipeline 的 SearchSource.to_dict() 有 */
  score?: number
  source: string  // "TavilySearch" | "QwenWebSearch"
}

export interface PipelineResult {
  topic: string
  timestamp: string
  science_facts: {
    topic?: string
    key_facts?: string[]
    entities?: { name: string; entity_type: string; attributes: Record<string, unknown>; description: string }[]
    relations?: { subject: string; predicate: string; object: string; confidence: number; source: string }[]
    timeline?: Record<string, unknown>[]
    data_sources?: string[]
  }
  context_analysis: {
    topic?: string
    country_analysis?: Record<string, unknown>[]
    framework_distribution?: Record<string, number>
    sentiment_summary?: Record<string, unknown>
    key_narratives?: string[]
    cross_cultural_differences?: string[]
  }
  hypotheses: Hypothesis[]
  verification_report: VerificationResult[]
  strategies: Strategy[]
  evaluation: EvaluationScores
  iteration_feedback: IterationFeedback[]
  iteration_count: number
  final_status: string
  search_sources: SearchSource[]
}

export interface KGData {
  nodes: { name: string; type: string; attributes: Record<string, unknown> }[]
  edges: { source: string; target: string; predicate: string; confidence: number }[]
  stats?: { node_count: number; edge_count: number }
}

// ============ 分析接口 ============

/** 启动异步分析任务 */
export async function startAnalysis(topic: string, maxIterations: number = 3) {
  const res = await api.post('/analyze/run', { topic, max_iterations: maxIterations })
  return res.data as { task_id: string; status: string; message: string }
}

export interface StepProgress {
  name: string
  display_name: string
  status: 'running' | 'completed' | 'error' | 'pending'
  message: string
}

/** 查询任务状态 */
export async function getTaskStatus(taskId: string) {
  const res = await api.get(`/analyze/status/${taskId}`)
  return res.data as {
    task_id: string
    status: string
    has_result: boolean
    progress?: { rounds: { label: string; steps: StepProgress[] }[] }
  }
}

/** 获取任务结果 */
export async function getTaskResult(taskId: string) {
  const res = await api.get(`/analyze/result/${taskId}`)
  return res.data as PipelineResult
}

/** 同步运行分析（等待完成） */
export async function runAnalysisSync(topic: string, maxIterations: number = 3) {
  const res = await api.post('/analyze/run-sync', { topic, max_iterations: maxIterations })
  return res.data as PipelineResult
}

/** 列出所有历史结果 */
export async function listResults() {
  const res = await api.get('/analyze/results')
  return res.data as { count: number; tasks: { task_id: string; status: string }[] }
}

/** 获取历史分析记录（持久化） */
export async function getHistory() {
  const res = await api.get('/analyze/history')
  return res.data as { history: { task_id: string; topic: string; timestamp: string; final_status: string; iteration_count: number }[] }
}

// ============ 知识图谱接口 ============

/** 获取完整知识图谱 */
export async function getKnowledgeGraph() {
  const res = await api.get('/kg/')
  return res.data as KGData
}

/** 获取图谱统计 */
export async function getKGStats() {
  const res = await api.get('/kg/stats')
  return res.data
}

/** 搜索实体 */
export async function searchEntities(query: string, entityType?: string) {
  const params: Record<string, string> = { q: query }
  if (entityType) params.entity_type = entityType
  const res = await api.get('/kg/search', { params })
  return res.data
}

/** 获取议题子图 */
export async function getSubgraph(topic: string) {
  const res = await api.get(`/kg/subgraph/${encodeURIComponent(topic)}`)
  return res.data
}

/** 获取连通分量列表（分区浏览） */
export async function getKGComponents() {
  const res = await api.get('/kg/components')
  return res.data as { total_components: number; components: { id: number; label: string; hub_type: string; node_count: number; edge_count: number }[] }
}

/** 获取指定连通分量的图谱数据 */
export async function getKGComponentGraph(componentId: number) {
  const res = await api.get(`/kg/component/${componentId}`)
  return res.data as KGData
}

// ============ 校验接口 ============

/** 校验单条断言 */
export async function verifyClaim(claim: string, entities?: string[]) {
  const res = await api.post('/verify/claim', { claim, entities })
  return res.data as VerificationResult
}

/** 批量校验 */
export async function verifyBatch(claims: string[]) {
  const res = await api.post('/verify/batch', { claims })
  return res.data as { results: VerificationResult[]; summary: Record<string, unknown> }
}

/** 获取校验系统状态 */
export async function getVerifyStatus() {
  const res = await api.get('/verify/status')
  return res.data
}

// ============ AI Scientist 工作流接口 ============

export interface ParliamentMotion {
  motion_id: string
  motion_type: string
  proposer: string
  content: string
  supporting_evidence: string[]
  confidence: number
}

export interface ParliamentSpeech {
  speaker: string
  round_num: number
  content: string
  stance: string
  references: string[]
}

export interface ParliamentVote {
  motion_id: string
  votes: Record<string, string>
  weighted_yes: number
  weighted_no: number
  result: string
  minority_opinions: string[]
  speaker_ruling: string
}

export interface ParliamentMinorityOpinion {
  agent: string
  motion_id: string
  objection: string
  alternative_proposal: string
  why_overruled: string
}

export interface ParliamentRound {
  round_id: number
  topic: string
  speeches: ParliamentSpeech[]
  speaker_weights: Record<string, number>
  speaker_rationale: string
}

export interface FinalReport {
  one_line_takeaway: string
  core_conclusion: string
  top_strategies: { rank: number; title: string; audience: string; action: string }[]
  risk_warnings: string[]
  audience_recommendations: { audience: string; suggestion: string }[]
  generated_by?: string
}

export interface DeliberationTranscript {
  topic: string
  total_rounds: number
  rounds: ParliamentRound[]
  motions: ParliamentMotion[]
  votes: ParliamentVote[]
  minority_opinions: ParliamentMinorityOpinion[]
  final_strategies: {
    pipeline_evaluation?: Record<string, number>
    pipeline_strategies?: Record<string, unknown>
    pipeline_verification?: Record<string, unknown>[]
    debate_transcript_summary?: string
    search_sources?: { url: string; title: string; content: string; score: number; source: string }[]
  }
  final_report?: FinalReport
  started_at: string
  completed_at: string
  task_id?: string
  task_status?: string
}

/** 异步启动 AI Scientist 工作流 */
export async function conveneParliament(topic: string, maxRounds?: number, maxPipelineRounds?: number) {
  const res = await api.post('/parliament/convene', { topic, max_rounds: maxRounds, max_pipeline_rounds: maxPipelineRounds })
  return res.data as { task_id: string; status: string; message: string }
}

export async function stopParliament(taskId: string) {
  const res = await api.post(`/parliament/stop/${taskId}`)
  return res.data as { task_id: string; status: string; message: string }
}

/** 查询议会任务状态 */
export interface PhaseProgress {
  key: string; label: string; icon: string; group: string
  status: 'pending' | 'running' | 'completed' | 'error'
  message: string
  sub_steps?: { key: string; status: string; label: string; icon: string; detail: string; full_content?: string }[]
}

export async function getParliamentStatus(taskId: string) {
  const res = await api.get(`/parliament/status/${taskId}`)
  return res.data as {
    task_id: string
    status: string
    has_result: boolean
    progress?: {
      phases: PhaseProgress[]
      current_round: number
      total_rounds: number
      pipeline_round: number
    }
  }
}

/** 获取议会辩论记录 */
export async function getParliamentResult(taskId: string) {
  const res = await api.get(`/parliament/result/${taskId}`)
  return res.data as DeliberationTranscript
}

/** 获取议会历史记录 */
export async function getParliamentHistory() {
  const res = await api.get('/parliament/history')
  return res.data as {
    history: {
      task_id: string; topic: string; total_rounds: number; motion_count: number
      vote_count: number; passed_count: number; pass_rate: number
      minority_count: number; avg_score: number | null; completed_at: string
    }[]
    summary: {
      total_runs: number; avg_rounds: number; avg_motions: number
      avg_minority: number; avg_score: number | null; total_votes: number
    }
  }
}

// ============ 其他 ============

/** 获取框架类型列表 */
export async function getFrameworks() {
  const res = await api.get('/hypotheses/frameworks')
  return res.data
}

/** 获取叙事人设列表 */
export async function getPersonas() {
  const res = await api.get('/strategies/personas')
  return res.data
}

// ============ 成果中心接口 ============

export interface OutputType {
  generator_type: string
  name: string
  module: string
  description: string
  real: boolean
}

export interface OutputGenerateResult {
  task_id: string
  generator_type: string
  name: string
  topic: string
  source_task_id: string | null
  created_at: string
  status: string
  data: Record<string, unknown>
}

export interface OutputHistoryItem {
  task_id: string
  generator_type: string
  name: string
  topic: string
  created_at: string
  status: string
}

/** 列出所有成果类型 */
export async function getOutputTypes() {
  const res = await api.get('/outputs/types')
  return res.data as { count: number; types: OutputType[] }
}

/** 异步生成成果 */
export async function generateOutput(generatorType: string, topic: string, sourceTaskId?: string, platform?: string) {
  const res = await api.post('/outputs/generate', {
    generator_type: generatorType,
    topic,
    source_task_id: sourceTaskId || null,
    platform: platform || null,
  })
  return res.data as { task_id: string; status: string; message: string }
}

/** 查询成果生成状态 */
export async function getOutputStatus(taskId: string) {
  const res = await api.get(`/outputs/status/${taskId}`)
  return res.data as { task_id: string; status: string; has_result: boolean; progress: Record<string, unknown> | null }
}

/** 获取成果生成结果 */
export async function getOutputResult(taskId: string) {
  const res = await api.get(`/outputs/result/${taskId}`)
  return res.data as OutputGenerateResult
}

/** 获取成果历史记录 */
export async function getOutputHistory() {
  const res = await api.get('/outputs/history')
  return res.data as { count: number; history: OutputHistoryItem[] }
}

/** 健康检查 */
export async function healthCheck() {
  const res = await api.get('/health')
  return res.data
}

/** 导出成果（返回下载 URL） */
export function getExportUrl(taskId: string, format: string) {
  return `/api/outputs/export/${taskId}?format=${format}`
}

// ============ 科研工作流接口（7 智能体 · AI Scientist 科研工作台）============

export interface WorkflowStageMeta {
  stage: number
  key: string
  name: string
  icon: string
  description: string
  library: string[]
}

export type WorkflowStageStatus = 'pending' | 'running' | 'awaiting_review' | 'completed' | 'failed'

export interface WorkflowStageRecord {
  stage: number
  status: WorkflowStageStatus
  output: Record<string, unknown> | null
  error: string | null
  run_count: number
  updated_at: string
}

export interface ResearchProject {
  id: string
  title: string
  interest: string
  current_stage: number
  status: 'active' | 'completed'
  created_at: string
  updated_at: string
  stages: Record<string, WorkflowStageRecord>
  history: Record<string, unknown>[]
}

/** 获取科研流程阶段元数据（Research Pipeline 渲染） */
export async function getWorkflowStages() {
  const res = await api.get('/workflow/stages')
  return res.data as { stages: WorkflowStageMeta[] }
}

/** 创建科研项目 */
export async function createWorkflowProject(title: string, interest: string) {
  const res = await api.post('/workflow/projects', { title, interest })
  return res.data as { project: ResearchProject }
}

/** 项目列表 */
export async function listWorkflowProjects() {
  const res = await api.get('/workflow/projects')
  return res.data as { projects: ResearchProject[] }
}

/** 项目详情 */
export async function getWorkflowProject(id: string) {
  const res = await api.get(`/workflow/projects/${id}`)
  return res.data as { project: ResearchProject }
}

/** 删除项目（物理移除项目文件与产出物） */
export async function deleteWorkflowProject(id: string) {
  const res = await api.delete(`/workflow/projects/${id}`)
  return res.data as { status: string; project_id: string }
}

/** 执行阶段智能体（同步，产出物落盘为 awaiting_review） */
export async function runWorkflowStage(id: string, stage: number, inputs: Record<string, unknown> = {}) {
  const res = await api.post(`/workflow/projects/${id}/stages/${stage}/run`, { inputs })
  return res.data as {
    stage: number
    status: WorkflowStageStatus
    output: Record<string, unknown> | null
    error: string | null
  }
}

/** 获取阶段产出物 */
export async function getWorkflowStageResult(id: string, stage: number) {
  const res = await api.get(`/workflow/projects/${id}/stages/${stage}/result`)
  return res.data as { stage: number; output: Record<string, unknown> }
}

/** 研究者确认阶段产出物，推进到下一阶段 */
export async function approveWorkflowStage(id: string, stage: number) {
  const res = await api.post(`/workflow/projects/${id}/stages/${stage}/approve`)
  return res.data as { project: ResearchProject }
}

/** 一键全流程：后台串行执行全部 7 阶段（进度通过 getWorkflowProject 轮询各阶段状态） */
export async function runAllWorkflow(
  id: string,
  opts: { materials?: { name: string; content: string }[]; style_sample?: string; topic?: string } = {},
) {
  const res = await api.post(`/workflow/projects/${id}/run-all`, opts)
  return res.data as { status: string; message: string }
}

/** 导出项目（md/json 文本；word/pdf 为二进制文件下载） */
export async function exportWorkflowProject(id: string, fmt: 'md' | 'json' | 'word' | 'pdf' = 'md') {
  if (fmt === 'word' || fmt === 'pdf') {
    // 二进制走下载（后端返回 Content-Disposition 附件）
    const res = await api.get(`/workflow/projects/${id}/export`, { params: { fmt }, responseType: 'blob' })
    return { format: fmt as 'word' | 'pdf', blob: res.data as Blob }
  }
  const res = await api.get(`/workflow/projects/${id}/export`, { params: { fmt } })
  return res.data as { content: string; format: string }
}

/** AI 润色论文章节（独立接口，不修改已确认产出物） */
export async function polishWorkflowSection(
  id: string,
  section: string,
  content: string,
  instruction: string = '',
) {
  const res = await api.post(`/workflow/projects/${id}/stages/6/polish`, { section, content, instruction })
  return res.data as { section: string; content: string }
}

/** 今日科技热点（统一搜索召回；后端不可用时返回空列表） */
export async function getHotTopics(limit: number = 6) {
  const res = await api.get('/workflow/hot-topics', { params: { limit } })
  return res.data as { topics: { title: string; url: string; source: string; content: string }[] }
}

// ============ 用户认证（用户系统对齐 liguiyu-home）============

export interface AuthUser {
  id: string
  email: string
  name: string
  role: 'user' | 'admin'
  /** 是否已配置自己的 LLM API（多租户自带钥匙模式） */
  llm_configured?: boolean
}

/** 注册前发送邮箱验证码（6 位，10 分钟有效） */
export async function sendAuthCode(email: string) {
  const res = await api.post('/auth/send-code', { email })
  return res.data as { success: boolean; message: string }
}

/** 注册：昵称 + 邮箱 + 密码 + 验证码 */
export async function registerUser(name: string, email: string, password: string, code: string) {
  const res = await api.post('/auth/register', { name, email, password, code })
  return res.data as { success: boolean; message: string; user?: AuthUser }
}

/** 登录：邮箱 + 密码（会话 httpOnly Cookie；同时返回 token 供跨域直传鉴权） */
export async function loginUser(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password })
  return res.data as { success: boolean; user: AuthUser; token?: string }
}

export async function logoutUser() {
  const res = await api.post('/auth/logout')
  return res.data as { success: boolean }
}

/** 当前登录用户（未登录 401）；me 会附带重新下发的 token（跨域上传用） */
export async function getMe() {
  const res = await api.get('/auth/me')
  return res.data as { user: AuthUser & { created_at: number; llm_configured: boolean }; token?: string }
}

// ============ 用户模型配置（多租户自带钥匙）============

export interface LlmConfigView {
  api_key_masked: string
  configured: boolean
  base_url: string
  model: string
}

export interface LlmConfigResponse {
  llm: LlmConfigView
  embedding: LlmConfigView
}

/** 查看当前用户模型配置（key 掩码） */
export async function getLlmConfig() {
  const res = await api.get('/user/llm-config')
  return res.data as LlmConfigResponse
}

/** 保存模型配置（自动验证连通；embedding 留空 = 清除/降级） */
export async function saveLlmConfig(cfg: {
  llm: { api_key: string; base_url: string; model: string }
  embedding?: { api_key: string; base_url: string; model: string } | null
}) {
  const res = await api.put('/user/llm-config', cfg)
  return res.data as { success: boolean; message: string }
}

// ============ 管理后台（admin）============

export interface AdminUser {
  id: string
  email: string
  name: string
  role: string
  created_at: number
  project_count: number
  llm_configured?: boolean
}

export interface AdminProject extends ResearchProject {
  owner: { id: string; email: string; name: string } | null
}

/** 用户列表（含各自项目数） */
export async function listAdminUsers() {
  const res = await api.get('/admin/users')
  return res.data as { users: AdminUser[]; total_projects: number }
}

/** 全部项目 + 归属人（含无主 legacy 项目） */
export async function listAdminProjects() {
  const res = await api.get('/admin/projects')
  return res.data as { projects: AdminProject[]; count: number }
}

/** 项目详情（admin 视角，与前台同构） */
export async function getAdminProject(id: string) {
  const res = await api.get(`/admin/projects/${id}`)
  return res.data as { project: AdminProject }
}

/** 设置/取消管理员角色 */
export async function setAdminRole(userId: string, role: 'admin' | 'user') {
  const res = await api.post(`/admin/users/${userId}/role`, { role })
  return res.data as { success: boolean; user_id: string; role: string }
}

/** 删除用户（级联删除其全部项目） */
export async function deleteAdminUser(userId: string) {
  const res = await api.delete(`/admin/users/${userId}`)
  return res.data as { success: boolean; deleted_user: string; deleted_projects: number }
}

/** 删除项目（物理移除） */
export async function deleteAdminProject(projectId: string) {
  const res = await api.delete(`/admin/projects/${projectId}`)
  return res.data as { status: string; project_id: string }
}

// ============ 个人论文库（library）============

export interface LibraryPaper {
  id: number
  title: string
  file_name: string
  file_ext: string
  status: 'uploaded' | 'processing' | 'ready' | 'error'
  chunk_count: number
  error_msg: string
  created_at: string
}

export interface LibraryStyle {
  terms: string[]
  structure: {
    sections_detected?: string[]
    abstract_style?: string[]
    conclusion_style?: string[]
    avg_sentence_len?: number
  }
  few_shot: string[]
}

export interface LibrarySearchResult {
  text: string
  score: number
  metadata: Record<string, unknown>
}

export interface LibraryHealth {
  storage: 'local'
  supported_extensions: string[]
}

/** 获取存储模式状态 */
export async function getLibraryHealth() {
  const res = await api.get('/library/health')
  return res.data as LibraryHealth
}

/** 上传论文：multipart 直传（upload3 直连入口，探测失败回退同域）→ 后端落盘解析（单步完成，含进度回调） */
export async function uploadLibraryPaper(file: File, onProgress?: (pct: number) => void) {
  const form = new FormData()
  form.append('file', file)
  const base = await resolveUploadBase()
  const cross = base !== ''
  // ⚠️ 统一用裸 axios + 绝对 URL：同域不能用 api 实例（baseURL='/api' 会叠加成 /api/api/...）
  const url = cross ? `${base}/api/library/upload` : `${window.location.origin}/api/library/upload`
  const res = await axios.post(url, form, {
    headers: {
      'Content-Type': 'multipart/form-data',
      ...(cross && getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
    },
    withCredentials: !cross,
    onUploadProgress: (e) => {
      if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100))
    },
    timeout: 600000, // 大文件 + 后端解析，10 分钟
  })
  return res.data as { paper_id: number; status: string; chunk_count: number; style: LibraryStyle }
}

/** 论文列表 */
export async function listLibraryPapers() {
  const res = await api.get('/library')
  return res.data as LibraryPaper[]
}

/** 论文详情 */
export async function getLibraryPaper(id: number) {
  const res = await api.get(`/library/${id}`)
  return res.data as LibraryPaper
}

/** 删除论文 */
export async function deleteLibraryPaper(id: number) {
  const res = await api.delete(`/library/${id}`)
  return res.data as { ok: boolean }
}

/** 检索用户论文库 */
export async function searchLibrary(query: string, topK = 5) {
  const res = await api.post('/library/search', { query, top_k: topK })
  return res.data as { query: string; results: LibrarySearchResult[] }
}

/** 全局风格三件套 */
export async function getLibraryStyle() {
  const res = await api.get('/library/style')
  return res.data as LibraryStyle
}

export default api
