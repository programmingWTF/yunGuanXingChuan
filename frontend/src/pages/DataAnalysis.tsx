/**
 * 云观星传 - ⑤ 数据分析
 * 上传分析素材（报道/访谈/表格文本）→ AI 分析 → 四类可视化（词云/情绪/框架分布/传播路径）
 */
import { useState } from 'react'
import { StageLayout, StageActions, StatusBadge, NoProjectHint, OutputView, useStageExec, type StageInfo } from '../components/StageUI'

const INFO: StageInfo = {
  stage: 5, icon: '📊', title: '数据分析', en: 'DATA ANALYSIS',
  description: '上传分析素材，执行内容/文本/框架分析并给出初步解读',
}

/** 词云：关键词 tag 云 */
function WordCloud({ items }: { items: { word: string; weight: number }[] }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 p-4 min-h-24">
      {items.map((w, i) => {
        const size = 12 + Math.min(14, Math.round(w.weight * 14))
        return (
          <span key={i} style={{ fontSize: size }} className={`text-slate-200 ${w.weight > 0.7 ? 'text-astro-300' : w.weight > 0.4 ? 'text-aurora-300' : 'text-slate-400'}`}>
            {w.word}
          </span>
        )
      })}
    </div>
  )
}

/** 横向条形图 */
function HBar({ label, value, color = 'bg-astro-400' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-400 w-20 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
      <span className="text-[10px] font-mono text-slate-400 w-6 text-right">{value}</span>
    </div>
  )
}

export default function DataAnalysis() {
  const { projectId, status, rec, running, error, exec, approve } = useStageExec(5)
  const [materialsText, setMaterialsText] = useState('')
  const [materialName, setMaterialName] = useState('')

  const output = (rec?.output ?? null) as {
    analysis_type?: string
    coding_table?: { category: string; count: number }[]
    findings?: { finding: string; evidence: string; confidence: number }[]
    interpretation?: string
  } | null
  const codingTable = output?.coding_table ?? []
  const findings = output?.findings ?? []
  const maxCount = Math.max(1, ...codingTable.map(c => c.count))

  const handleRun = async () => {
    const materials = materialsText.trim()
      ? [{ name: materialName.trim() || '分析素材', content: materialsText.trim() }]
      : []
    await exec({ materials })
  }

  return (
    <StageLayout info={INFO}>
      {!projectId ? <NoProjectHint /> : (
        <div className="space-y-5">
          {/* 输入区：上传素材 */}
          <div className="card p-5">
            <h3 className="sec-label !mb-3">上传分析素材</h3>
            <div className="flex flex-col md:flex-row gap-2 mb-2">
              <input
                value={materialName}
                onChange={e => setMaterialName(e.target.value)}
                placeholder="素材名称（如：美国媒体报道）"
                className="md:w-56 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60"
              />
              <span className="text-[10px] text-slate-600 self-center">支持粘贴新闻报道/访谈记录/数据表格文本</span>
            </div>
            <textarea
              value={materialsText}
              onChange={e => setMaterialsText(e.target.value)}
              placeholder={'粘贴素材内容…\n\n例如：\n【报道1】SpaceX rival Zhuque-2 rocket completed its first flight...\n【报道2】朱雀二号遥二运载火箭飞行试验任务取得圆满成功...'}
              rows={6}
              className="w-full rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-astro-400/60 resize-none font-mono"
            />
            <div className="mt-3 flex items-center gap-3 flex-wrap">
              <button onClick={handleRun} disabled={running || !materialsText.trim()}
                className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
                {running ? '分析中…' : '开始 AI 分析 →'}
              </button>
              <StatusBadge status={status} />
              <StageActions status={status} onRun={handleRun} onApprove={approve} running={running} error={error} runLabel="重新上传分析" />
            </div>
          </div>

          {/* 分析结果：四类可视化 */}
          {codingTable.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 词云（由关键词频率合成） */}
              <div className="card p-4">
                <h4 className="sec-label !mb-2">词云</h4>
                <WordCloud items={codingTable.map(c => ({ word: c.category, weight: c.count / maxCount }))} />
              </div>
              {/* 情绪分析（由 findings 置信度合成展示位） */}
              <div className="card p-4">
                <h4 className="sec-label !mb-2">情绪 / 类目分布</h4>
                <div className="space-y-2">
                  {codingTable.map((c, i) => (
                    <HBar key={i} label={c.category} value={Math.round((c.count / maxCount) * 100)} color={i % 2 ? 'bg-aurora-400' : 'bg-astro-400'} />
                  ))}
                </div>
              </div>
              {/* 框架分布 */}
              <div className="card p-4">
                <h4 className="sec-label !mb-2">框架分布</h4>
                <div className="space-y-2">
                  {codingTable.slice(0, 6).map((c, i) => (
                    <HBar key={i} label={c.category} value={Math.round((c.count / maxCount) * 100)} color="bg-flare-400" />
                  ))}
                </div>
              </div>
              {/* 传播路径 / 发现列表 */}
              <div className="card p-4">
                <h4 className="sec-label !mb-2">研究发现（传播路径线索）</h4>
                <div className="space-y-2">
                  {findings.map((f, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${f.confidence >= 0.7 ? 'bg-aurora-400' : f.confidence >= 0.4 ? 'bg-astro-400' : 'bg-slate-500'}`} />
                      <p className="text-[11px] text-slate-300 leading-snug">{f.finding}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {output?.interpretation && (
            <div className="card p-5 border-astro-400/25">
              <h4 className="sec-label !mb-2">初步解读</h4>
              <p className="text-[13px] text-slate-300 leading-relaxed">{output.interpretation}</p>
            </div>
          )}

          {rec?.status === 'awaiting_review' && <OutputView output={rec.output} />}
        </div>
      )}
    </StageLayout>
  )
}
