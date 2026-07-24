/**
 * 云观星传 - API 服务层
 * 所有后端接口调用
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // Pipeline 可能运行较久，5分钟超时
})

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
  score: number
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

// ============ 认知议会接口 ============

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

/** 异步召集认知议会 */
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

/** 健康检查 */
export async function healthCheck() {
  const res = await api.get('/health')
  return res.data
}

export default api
