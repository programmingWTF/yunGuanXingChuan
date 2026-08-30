/**
 * 云观星传 - ⑤ 数据分析（产出物查看 + 素材上传分析）
 * - 无素材：一键模式下由 Agent 做框架性分析（基于检索上下文）
 * - 有素材：上传报道文本/访谈记录/数据表格 → 基于选定研究方法真实执行分析
 * 展示：词云（类目权重）/ 类目分布 / 研究发现 / 传播路径证据 / 初步解读
 */
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StageLayout, StageSources, StatusBadge, NoProjectHint, useStageExec, StageActions, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'
import { useStore } from '../store'
import { startAutoIterate } from '../api'
import type { IterationRecord, IterationProblem } from '../api'

const INFO: StageInfo = {
  stage: 5, icon: '📊', title: '数据分析', en: 'DATA ANALYSIS',
  description: '上传素材（文本/访谈/表格）执行内容/文本/框架分析，输出编码表与初步解读',
}

/** 稳定字符串哈希（djb2）→ 0..1 伪随机；保证词云每次渲染布局一致、不因 re-render 跳动 */
function hashUnit(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0
  return (h % 1000) / 1000  // 0..1
}

/** 词云排版：基于权重 + 稳定 hash 产出 { fontSize, rotate, offsetY, cls }，增强真实词云的错落/疏密/层次感 */
function wordStyle(category: string, count: number, maxCount: number) {
  const w = maxCount > 0 ? count / maxCount : 0
  const u = hashUnit(category)
  // 字号梯度加大：权重最高明显更大（12 → 38px 随权重拉陡）
  const fontSize = 12 + Math.round(w * 26)
  // 轻旋转（高权重略大角度朝向不同，低权重微顺/逆时针随机）
  const rotate = Math.round((u * 22 - 8) * (0.6 + w * 0.5))
  // 纵向错落：上下偏移 -10..10px，打破横向基线对齐形成疏密
  const offsetY = Math.round(u * 20 - 10)
  // 深浅色层级：>0.7 深蓝加粗前景 / >0.4 青绿 / 低 浅灰（远景弱化）
  const cls =
    w > 0.7 ? 'text-indigo-700 font-semibold'
      : w > 0.4 ? 'text-emerald-600 font-medium'
        : 'text-slate-400'
  const transform = `rotate(${rotate}deg) translateY(${offsetY}px)`
  return { fontSize, transform, cls }
}

interface Material {
  name: string
  content: string
}

interface SentimentShape {
  positive: number
  neutral: number
  negative: number
  summary: string
}

/** 情绪分析图（conic-gradient 圆环 + 图例 + 解读；ChatGPT 方案四图之一） */
function SentimentDonut({ sentiment }: { sentiment: SentimentShape }) {
  const total = sentiment.positive + sentiment.neutral + sentiment.negative
  if (total <= 0) {
    // LLM 漏填/全 0 时（schema 默认值落盘可到达），避免「全红圆环 + 积极」的矛盾展示
    return (
      <div className="card p-4">
        <h4 className="sec-label !mb-2">😊 情绪分析</h4>
        <p className="text-[10px] text-slate-400 py-3 text-center">暂无情绪数据（本次产出未包含情绪分布）</p>
      </div>
    )
  }
  const p = (sentiment.positive / total) * 360
  const n = (sentiment.neutral / total) * 360
  const conic = `conic-gradient(#34d399 0deg ${p}deg, #38d4f8 ${p}deg ${p + n}deg, #fb7185 ${p + n}deg 360deg)`
  const dominant =
    sentiment.positive >= sentiment.neutral && sentiment.positive >= sentiment.negative
      ? '积极'
      : sentiment.negative > sentiment.neutral
        ? '消极'
        : '中性'
  return (
    <div className="card p-4">
      <h4 className="sec-label !mb-2">😊 情绪分析</h4>
      <div className="flex items-center gap-5">
        <div className="relative w-24 h-24 rounded-full shrink-0" style={{ background: conic }}>
          <div className="absolute inset-2 rounded-full bg-white/75 backdrop-blur-sm flex items-center justify-center">
            <span className="text-[11px] font-medium text-slate-700">{dominant}</span>
          </div>
        </div>
        <div className="flex-1 space-y-1">
          <p className="text-[10px] text-slate-500">积极 <span className="font-mono text-emerald-600">{sentiment.positive}</span></p>
          <p className="text-[10px] text-slate-500">中性 <span className="font-mono text-indigo-600">{sentiment.neutral}</span></p>
          <p className="text-[10px] text-slate-500">消极 <span className="font-mono text-amber-600">{sentiment.negative}</span></p>
        </div>
      </div>
      {sentiment.summary && <p className="text-[10px] text-slate-500 mt-2 leading-snug">{sentiment.summary}</p>}
    </div>
  )
}

function HBar({ label, value, color = 'bg-indigo-500' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-500 w-20 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="text-[10px] font-mono text-slate-500 w-6 text-right">{value}</span>
    </div>
  )
}

/* ═══════════ 闭环迭代（issue #129）：迭代计数器 + AI 诊断与迭代建议 ═══════════ */

/** ISO 时间 → MM-DD HH:mm（前端展示用） */
function fmtTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(5, 16).replace('T', ' ')
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 迭代指标小徽章（率/置信度 → 百分比，其余原值） */
function MetricChip({ label, value }: { label: string; value: number }) {
  const isRatio = label.includes('率') || label.includes('置信度')
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-white border border-slate-200 px-2 py-0.5">
      <span className="text-[9px] text-slate-400">{label}</span>
      <span className="text-[10px] font-mono text-slate-700">{isRatio ? `${Math.round(value * 100)}%` : value}</span>
    </span>
  )
}

/** 顶部迭代计数器：已完成 N 轮迭代，可展开查看每轮修改内容与指标变化（issue #129） */
function IterationCounter({ iterations, designVersion }: { iterations: IterationRecord[]; designVersion: number }) {
  const [open, setOpen] = useState(false)
  if (iterations.length === 0) return null
  return (
    <div className="card p-4 !border-amber-200/70">
      <button onClick={() => setOpen(v => !v)} className="w-full flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-base">🔄</span>
          <p className="text-xs text-slate-700">
            已完成 <span className="font-bold font-mono text-amber-600">{iterations.length}</span> 轮迭代
            <span className="ml-2 text-[10px] text-slate-400">当前设计版本 <span className="font-mono text-indigo-600">V{designVersion}</span></span>
          </p>
        </div>
        <span className="text-[10px] text-slate-400 shrink-0">{open ? '收起 ▲' : '展开每轮记录 ▼'}</span>
      </button>
      {open && (
        <div className="mt-3 pt-3 border-t border-slate-100 space-y-2.5">
          {iterations.map((it, i) => {
            const prev = i > 0 ? iterations[i - 1] : null
            return (
              <div key={it.iteration} className="rounded-xl bg-slate-50/70 border border-slate-100 px-3.5 py-2.5">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <p className="text-[11px] font-medium text-slate-700">
                    第 {it.iteration} 轮 <span className="text-slate-400 font-normal">· 设计 V{it.design_version}</span>
                  </p>
                  <span className="text-[9px] font-mono text-slate-400">{fmtTime(it.timestamp)}</span>
                </div>
                {Object.keys(it.metrics).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {Object.entries(it.metrics).map(([k, v]) => (
                      <MetricChip key={k} label={k} value={v} />
                    ))}
                  </div>
                )}
                {prev && Object.keys(prev.metrics).length > 0 && Object.keys(it.metrics).length > 0 && (
                  <p className="text-[9px] text-slate-400 mt-1">
                    较上轮：
                    {Object.entries(it.metrics).map(([k, v]) => {
                      if (prev.metrics[k] === undefined) return null
                      const diff = v - prev.metrics[k]
                      const isRatio = k.includes('率') || k.includes('置信度')
                      if (Math.abs(diff) < 0.001) return null
                      const arrow = diff > 0 ? '↑' : '↓'
                      const color = diff > 0 ? 'text-emerald-600' : 'text-red-500'
                      const delta = isRatio ? `${Math.round(Math.abs(diff) * 100)}%` : Math.abs(diff)
                      return <span key={k} className={`mr-2 ${color}`}>{k} {arrow}{delta}</span>
                    })}
                  </p>
                )}
                {it.suggestion && <p className="text-[10px] text-slate-500 mt-1 leading-snug">💡 {it.suggestion}</p>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}


export default function DataAnalysis() {
  const { projectId, status, rec, running, error, locked, exec, approve, confirmRerun, rerunConfirmEl } = useStageExec(5)
  const { currentProject, setIterationSuggestion, setRevisionHint } = useStore()
  const navigate = useNavigate()
  const [autoRunning, setAutoRunning] = useState(false)
  const [autoMsg, setAutoMsg] = useState('')
  const [materials, setMaterials] = useState<Material[]>([])
  const [pasteText, setPasteText] = useState('')
  const [reading, setReading] = useState(false)
  const [actionMsg, setActionMsg] = useState('')

  // issue #129 闭环迭代：迭代记录 + 设计版本号（后端持久化，随项目加载）
  const iterations = currentProject?.iterations ?? []
  const designVersion = currentProject?.design_version ?? 1
  const latestIteration = iterations.length > 0 ? iterations[iterations.length - 1] : null

  const output = (rec?.output ?? null) as {
    coding_table?: { category: string; count: number }[]
    findings?: { finding: string; evidence: string; confidence: number }[]
    sentiment?: SentimentShape
    interpretation?: string
    verification?: unknown
  } | null
  const codingTable = output?.coding_table ?? []
  const findings = output?.findings ?? []
  const maxCount = Math.max(1, ...codingTable.map(c => c.count))

  /** 粘贴素材 → 加入列表 */
  const addPasted = () => {
    const t = pasteText.trim()
    if (!t) return
    setMaterials(prev => [...prev, { name: `粘贴素材 ${prev.length + 1}`, content: t.slice(0, 20000) }])
    setPasteText('')
  }

  /** 文件上传（txt/md/csv/json）→ 读取文本加入列表 */
  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    setReading(true)
    try {
      const added = await Promise.all(
        files.map(async f => ({ name: f.name, content: (await f.text()).slice(0, 20000) })),
      )
      setMaterials(prev => [...prev, ...added])
    } finally {
      setReading(false)
      e.target.value = ''
    }
  }

  const removeMaterial = (i: number) => setMaterials(prev => prev.filter((_, idx) => idx !== i))

  /** 基于素材执行分析（产出物落盘为 awaiting_review，可确认后进入下一阶段） */
  const runWithMaterials = async () => {
    if (materials.length === 0) return
    setActionMsg('')
    try {
      await exec({ materials })
      setActionMsg('✅ 分析完成：下方展示基于素材的分析结果，确认后可进入下一阶段')
    } catch {
      setActionMsg('❌ 分析失败，请稍后重试（可在产出物区域查看具体错误）')
    }
  }

  /** 闭环迭代：携带 AI 诊断建议跳转研究设计页（issue #129） */
  const goFixDesign = () => {
    if (latestIteration) {
      setIterationSuggestion({ text: latestIteration.suggestion, iteration: latestIteration.iteration })
    }
    navigate('/design')
  }

  /** issue #130：携带 AI 诊断建议跳转文献综述页，发起补充检索 */
  const goSupplementLiterature = () => {
    if (latestIteration) {
      setRevisionHint({ text: latestIteration.suggestion, source: 'analysis' })
    }
    navigate('/literature')
  }

  /** 确认版第二层：单条问题 → 按路由跳转（3=研究设计 2=文献综述） */
  const goFixProblem = (pb: IterationProblem) => {
    if (pb.target_stage === 2) {
      setRevisionHint({ text: pb.text, source: 'analysis' })
      navigate('/literature')
    } else {
      setIterationSuggestion({ text: pb.text, iteration: latestIteration?.iteration ?? 0 })
      navigate('/design')
    }
  }

  /** 确认版核心：自动迭代（分析→诊断→自动改设计→自动重跑，后台执行，轮询进度） */
  const runAutoIterate = async () => {
    if (!projectId || autoRunning) return
    setAutoRunning(true)
    const before = currentProject?.iterations?.length ?? 0
    setAutoMsg('🤖 自动迭代已启动：AI 正在分析 → 诊断 → 修订设计 → 重跑…')
    try {
      await startAutoIterate(projectId, { max_rounds: 3, target_confidence: 0.85 })
      let done = false
      const t0 = Date.now()
      const timer = setInterval(async () => {
        if (done) return
        if (Date.now() - t0 > 8 * 60 * 1000) {
          done = true; clearInterval(timer); setAutoRunning(false)
          setAutoMsg('⏱ 自动迭代仍在后台进行，稍后刷新查看结果')
          return
        }
        try {
          const { getWorkflowProject } = await import('../api')
          const detail = (await getWorkflowProject(projectId)).project
          const its = detail?.iterations ?? []
          const n = its.length
          const last = its[n - 1]
          if (n > before && last && (last.problems?.length ?? 1) === 0) {
            done = true; clearInterval(timer); setAutoRunning(false)
            setAutoMsg(`✅ 自动迭代完成：本轮综合可信度 ${((last.confidence ?? 0) * 100).toFixed(0)}%，${last.conclusion ?? '结论可靠'}`)
            return
          }
          setAutoMsg(`🤖 自动迭代进行中…（迭代记录 ${n} 条，最新可信度 ${(((last?.confidence) ?? 0) * 100).toFixed(0)}%）`)
        } catch { /* 轮询失败忽略 */ }
      }, 8000)
    } catch (err: unknown) {
      setAutoRunning(false)
      setAutoMsg('❌ 自动迭代启动失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={status} />
            <StageActions
            stage={5}
            status={status}
            onRun={() => void exec({})}
            onApprove={approve}
            running={running}
            error={error}
            runLabel="开始分析"
          />
          </div>

          {/* issue #129 闭环迭代：顶部迭代计数器（已完成 N 轮，可展开看每轮记录与指标对比） */}
          <IterationCounter iterations={iterations} designVersion={designVersion} />

          {/* RAG + KG 双校验报告（产出物后置校验） */}
          <VerificationPanel verification={(rec?.output as { verification?: VerificationReport } | null)?.verification ?? null} />
          <StageSources output={rec?.output ?? null} />

          {/* ── 素材上传区 ── */}
          <div className="card p-4 border-indigo-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="sec-label !mb-0">📎 分析素材</h3>
              <span className="text-[10px] text-slate-500">已添加 {materials.length} 份 · 上传后基于素材真实执行分析</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <textarea
                value={pasteText}
                onChange={e => setPasteText(e.target.value)}
                placeholder="粘贴报道文本 / 访谈记录 / 数据表格内容…"
                rows={2}
                className="input-field flex-1 !bg-slate-50 !rounded-lg !text-xs resize-none"
              />
              <div className="flex gap-2 shrink-0">
                <button onClick={addPasted} disabled={!pasteText.trim()}
                  className="text-xs px-3 py-2 rounded-lg border border-slate-200 text-slate-600 hover:border-indigo-400 hover:text-indigo-700 disabled:opacity-40 transition-all">
                  添加文本
                </button>
                <label className={`text-xs px-3 py-2 rounded-lg border border-slate-200 text-slate-600 hover:border-indigo-400 hover:text-indigo-700 cursor-pointer transition-all ${reading ? 'opacity-40 pointer-events-none' : ''}`}>
                  {reading ? '读取中…' : '📄 上传文件'}
                  <input type="file" accept=".txt,.md,.csv,.json" multiple className="hidden" onChange={onFileChange} />
                </label>
              </div>
            </div>
            {materials.length > 0 && (
              <div className="mt-2.5 space-y-1.5">
                {materials.map((m, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-1.5">
                    <span className="text-[11px] font-medium text-slate-600 shrink-0">📄 {m.name}</span>
                    <span className="text-[10px] text-slate-400 truncate flex-1">{m.content.slice(0, 80)}…</span>
                    <button onClick={() => removeMaterial(i)} className="text-[11px] text-slate-500 hover:text-red-600 transition-colors shrink-0">✕</button>
                  </div>
                ))}
                <button onClick={runWithMaterials} disabled={running}
                  className="btn-primary w-full mt-2 text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                  {running ? '⏳ AI 分析中…（约 1-3 分钟，请勿刷新）' : '🚀 基于以上素材开始分析'}
                </button>
                {actionMsg && <p className="text-[10px] text-slate-500">{actionMsg}</p>}
              </div>
            )}
            {materials.length === 0 && (
              <p className="text-[10px] text-slate-400 mt-2">未添加素材时，分析基于检索上下文做框架性分析；上传素材后分析将基于素材真实内容执行。</p>
            )}
          </div>

          {codingTable.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 情绪分析（四图之一：词云/情绪/框架分布/传播路径） */}
              {output?.sentiment && (
                <SentimentDonut sentiment={output.sentiment} />
              )}
              <div className="card p-4">
                <h4 className="sec-label !mb-2">词云（类目权重）</h4>
                {/* 伪词云：纵向错落 + 轻微旋转 + 深浅色层级 + 加大字号梯度（纯前端渲染，沿用 coding_table 数据） */}
                <div className="flex flex-wrap items-center justify-center px-3 pt-3 pb-4 min-h-28 gap-x-4 gap-y-3">
                  {codingTable.map((c, i) => {
                    const s = wordStyle(c.category, c.count, maxCount)
                    return (
                      <span key={`${c.category}-${i}`} style={{ fontSize: s.fontSize, transform: s.transform }}
                        className={`inline-block leading-tight whitespace-nowrap ${s.cls}`}>
                        {c.category}
                      </span>
                    )
                  })}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">类目 / 框架分布</h4>
                <div className="space-y-2">
                  {codingTable.map((c, i) => (
                    <HBar key={i} label={c.category} value={Math.round((c.count / maxCount) * 100)} color={i % 2 ? 'bg-emerald-500' : 'bg-indigo-500'} />
                  ))}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">研究发现（传播路径线索）</h4>
                <div className="space-y-2">
                  {findings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${f.confidence >= 0.7 ? 'bg-emerald-500' : f.confidence >= 0.4 ? 'bg-indigo-500' : 'bg-slate-500'}`} />
                      <p className="text-[11px] text-slate-600 leading-snug">{f.finding}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card p-4">
                <h4 className="sec-label !mb-2">传播路径 / 证据</h4>
                <div className="space-y-2">
                  {findings.map((f, i) => (
                    f.evidence && <p key={i} className="text-[10px] text-slate-500 leading-snug">"{f.evidence}"</p>
                  ))}
                </div>
              </div>
            </div>
          )}
          {output?.interpretation && (
            <div className="card p-5 border-indigo-200">
              <h4 className="sec-label !mb-2">初步解读</h4>
              <p className="text-[13px] text-slate-600 leading-relaxed">{output.interpretation}</p>
            </div>
          )}

          {/* issue #129 闭环迭代：底部 AI 诊断与迭代建议（分析完成后出现，一键去修改设计） */}
          {latestIteration && latestIteration.suggestion && (
            <div className="card p-5 !border-indigo-300/70 bg-gradient-to-br from-indigo-50/70 via-white to-white">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                <h3 className="sec-label !mb-0">🩺 AI 方法学评估</h3>
                <span className="text-[9px] text-slate-400">基于第 {latestIteration.iteration} 轮分析 · 设计 V{latestIteration.design_version}</span>
              </div>
              {/* 确认版第一层：结论 + 综合可信度进度条 */}
              {(latestIteration.conclusion || typeof latestIteration.confidence === 'number') && (
                <div className="mb-3">
                  <p className="text-[13px] text-slate-700 font-medium leading-relaxed">
                    {latestIteration.conclusion || 'AI 已完成本轮诊断'}
                  </p>
                  {typeof latestIteration.confidence === 'number' && latestIteration.confidence > 0 && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                        <span>综合可信度</span>
                        <span className="font-mono font-bold text-indigo-600">{(latestIteration.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${latestIteration.confidence >= 0.85 ? 'bg-emerald-500' : latestIteration.confidence >= 0.7 ? 'bg-amber-500' : 'bg-red-400'}`}
                          style={{ width: `${Math.round(latestIteration.confidence * 100)}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* LLM 方法学评判：做得好的点 */}
              {(latestIteration.strengths?.length ?? 0) > 0 && (
                <div className="mt-2.5">
                  <ul className="space-y-1">
                    {latestIteration.strengths!.map((st, i) => (
                      <li key={i} className="text-[11px] text-emerald-600 leading-relaxed">✓ {st}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 确认版第二层：结构化问题清单（每条独立跳转按钮） */}
              {(latestIteration.problems?.length ?? 0) > 0 && (
                <div className="mb-3">
                  <p className="text-[11px] font-medium text-slate-600 mb-1.5">📋 发现 {latestIteration.problems!.length} 个问题：</p>
                  <ul className="space-y-1.5">
                    {latestIteration.problems!.map((pb, i) => (
                      <li key={i} className="flex items-start gap-2 text-[11px] text-slate-600 leading-relaxed">
                        <span className="flex-1 min-w-0">· {pb.text}</span>
                        <button onClick={() => goFixProblem(pb)}
                          className={`shrink-0 text-[9px] px-2 py-0.5 rounded border transition-all ${pb.target_stage === 2 ? 'border-sky-200 text-sky-600 hover:bg-sky-50' : 'border-indigo-200 text-indigo-600 hover:bg-indigo-50'}`}>
                          {pb.target_stage === 2 ? '📚 去修改' : '✏️ 去修改'}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 确认版核心：自动迭代一键启动 */}
              <div className="flex items-center gap-3 mt-3 flex-wrap">
                <button onClick={() => void runAutoIterate()} disabled={autoRunning}
                  className="text-xs px-3.5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all">
                  {autoRunning ? '⏳ 自动迭代中…' : '🤖 自动迭代（≤3 轮，可信度 ≥85% 自动停）'}
                </button>
                <button onClick={goFixDesign} className="btn-primary text-xs">✏️ 手动去修改设计 →</button>
                <button onClick={goSupplementLiterature}
                  className="text-xs px-3 py-2 rounded-lg border border-sky-200 text-sky-600 hover:bg-sky-50 transition-all">
                  📚 去补充文献 →
                </button>
              </div>
              {autoMsg && <p className="text-[11px] text-indigo-600 mt-2 leading-snug">{autoMsg}</p>}
            </div>
          )}
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}