/**
 * 云观星传 V2.0 — 证据校验
 * Verifier Agent · RAG + KG 交叉验证 · 手动断言校验
 */
import { useState } from 'react'
import { useStore } from '../store'
import { verifyClaim, type VerificationResult } from '../api'

const statusConfig: Record<string, { color: string; text: string }> = {
  verified: { color: 'text-aurora-400 bg-aurora-400/10 border-aurora-400/30', text: '✓ 已验证' },
  partial: { color: 'text-nova-400 bg-nova-400/10 border-nova-400/30', text: '◐ 部分验证' },
  conflicting: { color: 'text-flare-400 bg-flare-500/10 border-flare-400/30', text: '✗ 冲突' },
  unverified: { color: 'text-slate-400 bg-slate-500/10 border-slate-500/30', text: '? 未验证' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] || statusConfig.unverified
  return <span className={`px-2.5 py-1 rounded-md text-[11px] font-medium border whitespace-nowrap ${cfg.color}`}>{cfg.text}</span>
}

function loadParliamentVerification() {
  try {
    const r = localStorage.getItem('ygxc_latest_parliament')
    if (!r) return null
    const d = JSON.parse(r)
    const v = d?.final_strategies?.pipeline_verification
    if (!v || !Array.isArray(v) || v.length === 0) return null
    return v.map((item: Record<string, unknown>) => ({
      claim: (item.claim as string) || '',
      status: (item.status as string) || (item.verification_status as string) || 'unverified',
      rag_evidence: (item.rag_evidence as string) || null,
      kg_match: (item.kg_match as string) || null,
      cross_source_agreement: (item.cross_source_agreement as boolean) ?? null,
      confidence: (item.confidence as number) || 0,
      notes: (item.notes as string) || '',
    })) as VerificationResult[]
  } catch { return null }
}

function VerifyReport() {
  const { state } = useStore()
  const result = state.result
  const verifications: VerificationResult[] = result?.verification_report || loadParliamentVerification() || []

  const [manualClaim, setManualClaim] = useState('')
  const [manualResult, setManualResult] = useState<VerificationResult | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [manualError, setManualError] = useState('')

  const handleVerify = async () => {
    if (!manualClaim.trim()) return
    setVerifying(true)
    setManualError('')
    setManualResult(null)
    try {
      const res = await verifyClaim(manualClaim.trim())
      setManualResult(res)
    } catch {
      setManualError('校验请求失败，请确认后端已启动')
    } finally {
      setVerifying(false)
    }
  }

  const counts = {
    total: verifications.length,
    verified: verifications.filter(v => v.status === 'verified').length,
    partial: verifications.filter(v => v.status === 'partial').length,
    conflicting: verifications.filter(v => v.status === 'conflicting').length,
  }

  if (!result && verifications.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <p className="sec-label mb-1">Evidence Verification</p>
          <h2 className="font-display text-2xl font-bold text-white">证据校验</h2>
        </div>

        <ManualVerify
          claim={manualClaim} setClaim={setManualClaim}
          onVerify={handleVerify} verifying={verifying}
          result={manualResult} error={manualError}
        />

        <div className="panel p-16 text-center">
          <div className="text-5xl mb-5 opacity-50">◇</div>
          <h3 className="text-lg font-bold text-white mb-2">暂无证据校验数据</h3>
          <p className="text-sm text-slate-500">运行分析后，Verifier Agent（RAG + KG 交叉验证）将自动校验所有事实与假设</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="sec-label mb-1">Evidence Verification</p>
        <h2 className="font-display text-2xl font-bold text-white">证据校验</h2>
        <p className="text-xs text-slate-500 mt-1.5">RAG 向量检索 + 知识图谱交叉验证 · 可证伪性检验</p>
      </div>

      {/* 手动校验 */}
      <ManualVerify
        claim={manualClaim} setClaim={setManualClaim}
        onVerify={handleVerify} verifying={verifying}
        result={manualResult} error={manualError}
      />

      {/* 总览卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总断言数', value: counts.total, color: 'text-astro-300' },
          { label: '已验证', value: counts.verified, color: 'text-aurora-400' },
          { label: '部分验证', value: counts.partial, color: 'text-nova-400' },
          { label: '冲突', value: counts.conflicting, color: 'text-flare-400' },
        ].map((item, i) => (
          <div key={i} className="panel p-5 text-center">
            <div className={`stat-num text-3xl ${item.color}`}>{item.value}</div>
            <div className="text-xs text-slate-500 mt-1">{item.label}</div>
          </div>
        ))}
      </div>

      {/* 校验详情 */}
      <div className="panel p-5">
        <p className="sec-label mb-1">Cross Verification</p>
        <h3 className="font-display text-base font-bold text-white mb-4">逐条校验详情</h3>
        {verifications.length === 0 ? (
          <p className="text-slate-600 text-sm">本次分析未产生校验结果</p>
        ) : (
          <div className="space-y-3">
            {verifications.map((item, i) => (
              <div key={i} className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] animate-rise" style={{ animationDelay: `${i * 0.04}s` }}>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm text-slate-200 flex-1 leading-relaxed">{item.claim}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <StatusBadge status={item.status} />
                    <span className="text-xs text-slate-500 w-20 text-right font-mono" title="RAG向量检索置信度">
                      {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                {(item.rag_evidence || item.kg_match || item.notes) && (
                  <div className="mt-3 pt-3 border-t border-white/[0.05] text-xs text-slate-500 space-y-1.5">
                    {item.rag_evidence && <p><span className="text-astro-300">📄 RAG</span> · {item.rag_evidence}</p>}
                    {item.kg_match && <p><span className="text-nova-400">🔗 KG</span> · {item.kg_match}</p>}
                    {item.notes && <p><span className="text-slate-400">📝</span> {item.notes}</p>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 迭代反馈 */}
      {result?.iteration_feedback && result.iteration_feedback.length > 0 && (
        <div className="panel p-5">
          <p className="sec-label mb-1">Iteration Feedback</p>
          <h3 className="font-display text-base font-bold text-white mb-3">评测迭代反馈</h3>
          <div className="space-y-2">
            {result.iteration_feedback.map((fb, i) => (
              <div key={i} className="flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-sm">
                <span className="text-astro-300 font-bold whitespace-nowrap">{fb.dimension}</span>
                <span className="text-slate-600 whitespace-nowrap font-mono text-xs">({fb.current_score})</span>
                <span className="text-slate-300">{fb.issue}</span>
                <span className="text-aurora-400/80 ml-auto whitespace-nowrap text-xs">→ {fb.target_agent}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/** 手动断言校验组件 */
function ManualVerify({ claim, setClaim, onVerify, verifying, result, error }: {
  claim: string
  setClaim: (v: string) => void
  onVerify: () => void
  verifying: boolean
  result: VerificationResult | null
  error: string
}) {
  return (
    <div className="panel p-5">
      <p className="sec-label mb-1">Manual Check</p>
      <h3 className="font-display text-base font-bold text-white mb-3">手动断言校验</h3>
      <div className="flex gap-3">
        <input
          type="text"
          value={claim}
          onChange={e => setClaim(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onVerify()}
          placeholder="输入需要校验的断言，如：嫦娥六号于2024年5月3日发射"
          className="input-field flex-1"
        />
        <button onClick={onVerify} disabled={verifying || !claim.trim()} className="btn-primary text-sm disabled:opacity-50">
          {verifying ? '校验中...' : '校验'}
        </button>
      </div>

      {error && <p className="mt-2.5 text-sm text-flare-400">{error}</p>}

      {result && (
        <div className="mt-4 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] animate-fade-in">
          <div className="flex items-center justify-between mb-3 gap-4">
            <span className="text-sm text-slate-200">{result.claim}</span>
            <div className="flex items-center gap-3 shrink-0">
              <StatusBadge status={result.status} />
              <span className="text-xs text-slate-500 font-mono">置信度 {(result.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div className="text-xs text-slate-500 space-y-1.5">
            {result.rag_evidence && <p><span className="text-astro-300">📄 RAG 证据</span> · {result.rag_evidence}</p>}
            {result.kg_match && <p><span className="text-nova-400">🔗 KG 匹配</span> · {result.kg_match}</p>}
            {result.notes && <p><span className="text-slate-400">📝 备注</span> · {result.notes}</p>}
            {result.cross_source_agreement !== null && (
              <p><span className="text-aurora-400">🤝 交叉一致性</span> · {result.cross_source_agreement ? '一致' : '不一致'}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default VerifyReport
