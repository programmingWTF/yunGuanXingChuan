/**
 * 云观星传 - ⑤ 数据分析（产出物查看 + 素材上传分析）
 * - 无素材：一键模式下由 Agent 做框架性分析（基于检索上下文）
 * - 有素材：上传报道文本/访谈记录/数据表格 → 基于选定研究方法真实执行分析
 * 展示：词云（类目权重）/ 类目分布 / 研究发现 / 传播路径证据 / 初步解读
 */
import { useState } from 'react'
import { StageLayout, StageSources, StatusBadge, NoProjectHint, useStageExec, StageActions, VerificationPanel, type VerificationReport, type StageInfo } from '../components/StageUI'

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
          <div className="absolute inset-2 rounded-full bg-white flex items-center justify-center">
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

export default function DataAnalysis() {
  const { projectId, status, rec, running, error, locked, exec, approve, confirmRerun, rerunConfirmEl } = useStageExec(5)
  const [materials, setMaterials] = useState<Material[]>([])
  const [pasteText, setPasteText] = useState('')
  const [reading, setReading] = useState(false)
  const [actionMsg, setActionMsg] = useState('')

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
        </div>
      )}
      {rerunConfirmEl}
    </StageLayout>
  )
}