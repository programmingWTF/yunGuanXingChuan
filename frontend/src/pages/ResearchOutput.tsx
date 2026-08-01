/**
 * 云观星传 V2.0 — 成果中心（Research Output Center）
 * 7 类研究成果的统一入口：真实生成器（研究计划/策略报告）+ 占位生成器
 */
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  getOutputTypes, generateOutput, getOutputStatus, getOutputResult, getOutputHistory,
  type OutputType, type OutputGenerateResult, type OutputHistoryItem,
} from '../api'
import { exportResult, FORMAT_META, type ExportFormat } from '../exportUtils'

/* ── 成果卡片元信息（图标 + 配色） ── */
const TYPE_META: Record<string, { icon: string; color: string }> = {
  research_plan: { icon: '◬', color: 'text-astro-400 border-astro-500/30 bg-astro-500/10' },
  strategy_report: { icon: '▤', color: 'text-nova-400 border-nova-400/30 bg-nova-400/10' },
  press_release: { icon: '▣', color: 'text-slate-300 border-slate-500/30 bg-slate-500/10' },
  paper_outline: { icon: '▧', color: 'text-purple-300 border-purple-400/30 bg-purple-500/10' },
  science_script: { icon: '▦', color: 'text-aurora-400 border-aurora-400/30 bg-aurora-400/10' },
  kg_report: { icon: '✦', color: 'text-flare-400 border-flare-400/30 bg-flare-500/10' },
  expression_adaptation: { icon: '≋', color: 'text-astro-300 border-astro-400/30 bg-astro-400/10' },
}

/* 真实生成器的专属字段标签 */
const REAL_FIELDS: Record<string, { label: string; placeholder: string }> = {
  research_plan: { label: '研究主题', placeholder: '如：嫦娥六号月球背面采样返回任务的国际传播效果研究' },
  strategy_report: { label: '议题', placeholder: '如：嫦娥六号' },
  press_release: { label: '议题', placeholder: '如：嫦娥六号' },
  paper_outline: { label: '研究主题', placeholder: '如：嫦娥六号月球样品研究' },
  kg_report: { label: '议题', placeholder: '如：嫦娥六号' },
  science_script: { label: '科普主题', placeholder: '如：嫦娥六号月球背面采样返回' },
}

/** 科普视频脚本的目标平台 */
const SCRIPT_PLATFORMS = ['短视频', '公众号', '微博', 'B站', '小红书']

/** 将成果结果渲染为结构化区块列表（供页面展示） */
function resultToSections(data: Record<string, unknown>) {
  const labelMap: Record<string, string> = {
    topic: '研究主题',
    research_background: '研究背景',
    research_gap: '研究空白',
    scientific_hypotheses: 'AI 科学假设',
    suggested_methods: '建议研究方法',
    suggested_data_sources: '建议数据来源',
    experiment_steps: '建议实验步骤',
    feasibility_analysis: '可行性分析',
    note: '助研说明',
    target_countries: '目标国家',
    target_audiences: '目标受众',
    communication_goals: '传播目标',
    narrative_frameworks: '叙事框架',
    recommended_titles: '推荐标题',
    keywords: '关键词',
    risk_warnings: '风险提醒',
    china_media_differences: '中外媒体差异',
    message: '提示',
    // #6 新闻传播建议稿
    lead_suggestions: '导语建议',
    body_framework: '正文框架',
    interview_subjects: '推荐采访对象',
    image_suggestions: '配图建议',
    platform_suggestions: '传播平台建议',
    // #7 论文大纲
    paper_title: '论文标题',
    abstract_framework: '摘要框架',
    introduction_framework: '引言框架',
    literature_review_framework: '文献综述框架',
    method_framework: '研究方法框架',
    result_framework: '结果框架',
    discussion_framework: '讨论框架',
    future_work_framework: '未来工作',
    research_questions: '研究问题',
    // #8 知识图谱报告
    kg_summary: '知识图谱总览',
    hot_nodes: '热点节点',
    key_persons: '关键人物',
    organizations: '机构',
    relations: '关系三元组',
    // science_script（科普视频脚本）字段
    platform: '目标平台',
    title: '脚本标题',
    opening_hook: '开场钩子',
    shots: '分镜脚本',
    bgm_suggestion: 'BGM 建议',
    hashtags: '话题标签',
    author_notes: '发布/运营提示',
    scene_no: '镜头序号',
    scene_description: '画面/镜头描述',
    duration_seconds: '建议时长',
    caption: '字幕',
    narration: '旁白',
    visual_suggestion: '配图建议',
  }
  const listOnly: Record<string, string> = {
    existing_research: '已有研究',
    scientific_hypotheses: 'AI 科学假设',
    suggested_methods: '建议研究方法',
    suggested_data_sources: '建议数据来源',
    experiment_steps: '建议实验步骤',
    target_countries: '目标国家',
    target_audiences: '目标受众',
    communication_goals: '传播目标',
    narrative_frameworks: '叙事框架',
    recommended_titles: '推荐标题',
    keywords: '关键词',
    risk_warnings: '风险提醒',
    china_media_differences: '中外媒体差异',
    lead_suggestions: '导语建议',
    body_framework: '正文框架',
    interview_subjects: '推荐采访对象',
    image_suggestions: '配图建议',
    platform_suggestions: '传播平台建议',
    research_questions: '研究问题',
    hot_nodes: '热点节点',
    key_persons: '关键人物',
    organizations: '机构',
    relations: '关系三元组',
  }
  return Object.entries(data)
    .filter(([k, v]) => v !== undefined && v !== null && v !== '' && !['evidence_sources', 'status'].includes(k))
    .map(([k, v]) => {
      const label = labelMap[k] || k
      // 分镜数组（对象数组）专用渲染
      if (k === 'shots' && Array.isArray(v)) {
        return { key: k, label, kind: 'shots' as const, shots: v as Record<string, unknown>[] }
      }
      // 对象数组（如 KG 报告的 hot_nodes / relations）——需对象渲染
      if (Array.isArray(v) && v.length > 0 && typeof v[0] === 'object' && v[0] !== null) {
        return { key: k, label, kind: 'objectList' as const, items: v as Record<string, unknown>[] }
      }
      if (Array.isArray(v)) {
        return {
          key: k, label, kind: 'list' as const, items: v as string[],
          note: listOnly[k] ? '' : `${v.length} 项`,
        }
      }
      if (typeof v === 'object' && v !== null) {
        return { key: k, label, kind: 'object' as const, value: v as Record<string, unknown> }
      }
      return { key: k, label, kind: 'text' as const, value: String(v) }
    })
}

export default function ResearchOutput() {
  const [types, setTypes] = useState<OutputType[]>([])
  const [selected, setSelected] = useState<OutputType | null>(null)
  const [topic, setTopic] = useState('')
  const [platform, setPlatform] = useState('短视频')
  const [running, setRunning] = useState<{ taskId: string; name: string } | null>(null)
  const [result, setResult] = useState<OutputGenerateResult | null>(null)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<OutputHistoryItem[]>([])
  const pollingRef = useRef<number | null>(null)

  const loadTypes = async () => {
    try { const r = await getOutputTypes(); setTypes(r.types) } catch { /* backend offline */ }
  }
  const loadHistory = async () => {
    try { const r = await getOutputHistory(); setHistory(r.history) } catch { /* ignore */ }
  }

  useEffect(() => {
    loadTypes()
    loadHistory()
  }, [])

  useEffect(() => () => { if (pollingRef.current) window.clearInterval(pollingRef.current) }, [])

  const stopPolling = () => { if (pollingRef.current) { window.clearInterval(pollingRef.current); pollingRef.current = null } }

  const handleGenerate = async () => {
    if (!selected || !topic.trim()) return
    setError(''); setResult(null); setRunning({ taskId: '', name: selected.name })
    try {
      const { task_id } = await generateOutput(selected.generator_type, topic.trim(), undefined, selected.generator_type === 'science_script' ? platform : undefined)
      setRunning({ taskId: task_id, name: selected.name })

      // 轮询：真实生成器异步完成，占位生成器立即完成
      pollingRef.current = window.setInterval(async () => {
        try {
          const status = await getOutputStatus(task_id)
          if (status.has_result) {
            const r = await getOutputResult(task_id)
            setResult(r); setRunning(null); stopPolling(); loadHistory()
          } else if (status.status.startsWith('error')) {
            setError(`生成失败：${status.status}`); setRunning(null); stopPolling()
          }
        } catch { /* 网络抖动，下次轮询重试 */ }
      }, 2000)
    } catch (e) {
      setRunning(null)
      setError(`提交失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const resetForm = () => { setSelected(null); setTopic(''); setResult(null); setError('') }

  return (
    <div className="space-y-7">
      {/* 页头 */}
      <div className="flex justify-between items-end">
        <div>
          <p className="sec-label mb-1">Research Output Center</p>
          <h2 className="font-display text-2xl font-bold text-white">成果中心</h2>
          <p className="text-xs text-slate-500 mt-1.5">7 类研究成果统一生成 —— 助研助传，不做代写</p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="chip">真实生成器 ×{types.filter(t => t.real).length}</span>
          <span className="chip">占位待实现 ×{types.length - types.filter(t => t.real).length}</span>
        </div>
      </div>

      {/* 7 类成果卡片网格 */}
      <section>
        <p className="sec-label mb-3">Output Modules</p>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {types.map((t, i) => {
            const meta = TYPE_META[t.generator_type] || TYPE_META.research_plan
            const isActive = selected?.generator_type === t.generator_type
            return (
              <button key={t.generator_type}
                onClick={() => { setSelected(t); setResult(null); setError(''); setTopic('') }}
                style={{ animationDelay: `${i * 40}ms` }}
                className={`animate-rise text-left p-5 rounded-2xl border transition-all duration-200 cursor-pointer ${isActive
                  ? 'border-astro-400/50 bg-astro-500/10 shadow-glow-cyan'
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-astro-500/30 hover:bg-white/[0.04]'}`}>
                <div className="flex items-center gap-3 mb-3">
                  <span className={`w-9 h-9 flex items-center justify-center rounded-xl border text-lg ${meta.color}`}>{meta.icon}</span>
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-white truncate">{t.name}</div>
                    <div className="text-[10px] font-mono text-slate-600">{t.module}</div>
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 leading-relaxed line-clamp-2">{t.description}</p>
                <div className="mt-3 flex items-center justify-between">
                  <span className={`text-[10px] px-2 py-0.5 rounded-md ${t.real ? 'bg-aurora-400/10 text-aurora-400 border border-aurora-400/20' : 'bg-white/[0.04] text-slate-500 border border-white/[0.06]'}`}>
                    {t.real ? '✓ 可生成' : '🔒 即将上线'}
                  </span>
                  {isActive && <span className="text-astro-400 text-sm">▶</span>}
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* 生成面板（选中生成器时显示） */}
      {selected && (
        <section className="panel panel-beam p-6 animate-fade-in">
          {selected.real ? (
            <>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="sec-label mb-1">Generate {selected.generator_type}</p>
                  <h3 className="text-lg font-bold text-white">{selected.name}</h3>
                </div>
                <button onClick={resetForm} className="text-[11px] text-slate-500 hover:text-white transition-colors">✕ 取消</button>
              </div>

              <div className="flex flex-col sm:flex-row gap-3 mb-4">
                {selected.generator_type === 'science_script' && (
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] text-slate-500">平台</span>
                    <select
                      value={platform}
                      onChange={e => setPlatform(e.target.value)}
                      className="input-field py-3 px-3 text-sm bg-[#0b1230]"
                      style={{ width: 110 }}
                    >
                      {SCRIPT_PLATFORMS.map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                )}
                <input
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                  placeholder={REAL_FIELDS[selected.generator_type]?.placeholder || '输入议题'}
                  className="input-field flex-1 py-3 px-4"
                />
                <button onClick={handleGenerate} disabled={!topic.trim() || !!running} className="btn-primary px-7 py-3 whitespace-nowrap disabled:opacity-50">
                  {running ? '⏳ 生成中...' : '◇ 开始生成'}
                </button>
              </div>

              {error && <p className="text-xs text-flare-400 mb-3">{error}</p>}

              {running && (
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="w-3 h-3 rounded-full bg-astro-400 animate-pulse" />
                    <span className="text-sm text-slate-300">正在生成「{running.name}」...</span>
                    <span className="text-[10px] font-mono text-slate-600 ml-auto">{running.taskId.slice(0, 16)}</span>
                  </div>
                  <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
                    <div className="h-full w-1/2 rounded-full bg-gradient-to-r from-astro-500 to-nova-400 animate-[scan_1.6s_ease-in-out_infinite]" />
                  </div>
                </div>
              )}

              {result && (
                <div className="mt-5 space-y-4 animate-fade-in">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white">生成结果</h4>
                    <ExportMenu result={result} />
                  </div>
                  <ResultSections data={result.data} />
                  {(() => {
                    const src = result.data.evidence_sources
                    const sources = Array.isArray(src) ? src.filter((s): s is string => typeof s === 'string') : []
                    if (sources.length === 0) return null
                    return (
                      <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4">
                        <p className="sec-label mb-2">Evidence Sources</p>
                        <ul className="space-y-1">
                          {sources.map((s, i) => (
                            <li key={i} className="text-xs text-slate-400 font-mono">▸ {s}</li>
                          ))}
                        </ul>
                      </div>
                    )
                  })()}
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-10">
              <div className="text-4xl mb-4 opacity-40">🔒</div>
              <h3 className="text-base font-bold text-white mb-2">「{selected.name}」即将上线</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                成果中心架构已就绪（统一接口 + 生成器注册表），该成果生成器正在按议题逐个填充。
                本次已实现：科学假设与研究计划、国际传播策略报告、新闻传播建议稿、论文大纲、知识图谱报告。
              </p>
            </div>
          )}
        </section>
      )}

      {/* 历史记录 */}
      {history.length > 0 && (
        <section className="panel panel-beam p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="sec-label mb-1">Output Archive</p>
              <h3 className="text-lg font-bold text-white">历史成果（{history.length}）</h3>
            </div>
            <button onClick={loadHistory} className="text-[11px] text-slate-500 hover:text-white transition-colors">↻ 刷新</button>
          </div>
          <div className="space-y-2">
            {history.map(h => (
              <div key={h.task_id} className="flex items-center gap-4 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-white/10 transition-colors">
                <span className="text-sm text-astro-400">▤</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">{h.name} · {h.topic}</div>
                  <div className="text-[10px] font-mono text-slate-600">{h.task_id}</div>
                </div>
                <span className="text-[10px] text-slate-500">{h.created_at?.slice(0, 16)?.replace('T', ' ')}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-md ${h.status === 'completed' ? 'bg-aurora-400/10 text-aurora-400 border border-aurora-400/20' : 'bg-white/[0.04] text-slate-500 border border-white/[0.06]'}`}>
                  {h.status}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 空状态（无成果类型时） */}
      {types.length === 0 && (
        <div className="panel p-16 text-center">
          <div className="text-5xl mb-5 opacity-50">▤</div>
          <h3 className="text-lg font-bold text-white mb-2">成果中心</h3>
          <p className="text-sm text-slate-500 mb-7">后端未连接 —— 请先启动后端服务（uvicorn api.main:app）</p>
          <Link to="/" className="btn-primary inline-flex px-7 py-3">◈ 前往研究工作台</Link>
        </div>
      )}
    </div>
  )
}

/* ═══════════ 结果区块渲染 ═══════════ */
function ResultSections({ data }: { data: Record<string, unknown> }) {
  const sections = resultToSections(data)
  return (
    <div className="space-y-3">
      {sections.map(s => (
        <div key={s.key} className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-bold text-astro-300">{s.label}</p>
            {s.kind === 'list' && s.note && <span className="text-[10px] text-slate-600">{s.note}</span>}
            {s.kind === 'shots' && <span className="text-[10px] text-slate-600">{s.shots.length} 个镜头</span>}
          </div>
          {s.kind === 'list' ? (
            <ul className="space-y-1.5">
              {s.items.map((item, i) => (
                <li key={i} className="text-sm text-slate-300 leading-relaxed">
                  {s.label.includes('步骤') ? `${i + 1}. ` : '· '}{item}
                </li>
              ))}
            </ul>
          ) : s.kind === 'objectList' ? (
            <div className="space-y-2">
              {s.items.map((obj, i) => (
                <div key={i} className="rounded-lg bg-white/[0.02] border border-white/[0.05] px-3 py-2">
                  <div className="text-sm font-medium text-white mb-0.5">
                    {String(obj.name || obj.subject || obj.media || `#${i + 1}`)}
                    {typeof obj.degree === 'number' && <span className="ml-2 text-[10px] text-nova-400">热度 {obj.degree}</span>}
                    {typeof obj.type === 'string' && obj.type && <span className="ml-2 text-[10px] font-mono text-slate-500">{obj.type}</span>}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                    {Object.entries(obj).filter(([kk, vv]) => !['name', 'subject', 'media', 'degree', 'type'].includes(kk) && vv !== undefined && vv !== null && vv !== '').map(([kk, vv]) => (
                      <span key={kk} className="text-[11px] text-slate-400">
                        <span className="text-slate-600">{kk}:</span> {String(vv)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : s.kind === 'shots' ? (
            <div className="space-y-3">
              {s.shots.map((shot, i) => (
                <div key={i} className="rounded-lg bg-white/[0.02] border border-white/[0.05] p-3">
                  <p className="text-xs font-bold text-aurora-400 mb-2">第 {String(shot.scene_no || i + 1)} 镜头</p>
                  <ShotRow label="画面" value={String(shot.scene_description || '')} />
                  <ShotRow label="时长" value={shot.duration_seconds ? `${String(shot.duration_seconds)}s` : ''} />
                  <ShotRow label="字幕" value={String(shot.caption || '')} />
                  <ShotRow label="旁白" value={String(shot.narration || '')} />
                  <ShotRow label="配图" value={String(shot.visual_suggestion || '')} />
                </div>
              ))}
            </div>
          ) : s.kind === 'object' ? (
            <div className="flex flex-wrap gap-x-4 gap-y-0.5">
              {Object.entries(s.value).filter(([, vv]) => vv !== undefined && vv !== null && vv !== '').map(([kk, vv]) => (
                <span key={kk} className="text-[11px] text-slate-400">
                  <span className="text-slate-600">{kk}:</span> {String(vv)}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{s.value}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function ShotRow({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="mb-1.5">
      <span className="text-[10px] text-slate-500 mr-2">{label}</span>
      <span className="text-sm text-slate-300 leading-relaxed">{value}</span>
    </div>
  )
}

/* ═══════════ 多格式导出下拉菜单 ═══════════ */
function ExportMenu({ result }: { result: OutputGenerateResult }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const formats: ExportFormat[] = ['pdf', 'word', 'markdown', 'html', 'json', 'png']

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium border border-astro-500/30 bg-astro-500/10 text-astro-300 hover:bg-astro-500/20 transition-colors"
      >
        ⬇ 导出
        <span className="text-[9px] opacity-60">▾</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-50 min-w-[180px] py-1.5 rounded-xl border border-white/[0.08] bg-[#0a1630]/95 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.6)]">
          <p className="px-4 py-1.5 text-[9px] font-mono tracking-widest text-slate-600 uppercase">Export Format</p>
          {formats.map(fmt => {
            const meta = FORMAT_META[fmt]
            return (
              <button
                key={fmt}
                onClick={() => { exportResult(result, fmt); setOpen(false) }}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.06] hover:text-white transition-colors text-left"
              >
                <span className="w-5 text-center text-xs opacity-70">{meta.icon}</span>
                <span className="flex-1">{meta.label}</span>
                <span className="text-[9px] font-mono text-slate-600">.{meta.ext}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}