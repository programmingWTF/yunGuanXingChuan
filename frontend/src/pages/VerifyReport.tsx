import { useState } from 'react'
import { useStore } from '../store'
import { verifyClaim, type VerificationResult } from '../api'

const statusConfig: Record<string, { color: string; text: string }> = {
  verified: { color: 'text-green-400 bg-green-500/20', text: '✓ 已验证' },
  partial: { color: 'text-yellow-400 bg-yellow-500/20', text: '◐ 部分验证' },
  conflicting: { color: 'text-red-400 bg-red-500/20', text: '✗ 冲突' },
  unverified: { color: 'text-gray-400 bg-gray-500/20', text: '? 未验证' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] || statusConfig.unverified
  return <span className={`px-2 py-1 rounded text-xs whitespace-nowrap ${cfg.color}`}>{cfg.text}</span>
}

function VerifyReport() {
  const { state } = useStore()
  const result = state.result
  const verifications: VerificationResult[] = result?.verification_report || []

  // 手动校验
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

  // 统计
  const counts = {
    total: verifications.length,
    verified: verifications.filter(v => v.status === 'verified').length,
    partial: verifications.filter(v => v.status === 'partial').length,
    conflicting: verifications.filter(v => v.status === 'conflicting').length,
  }

  if (!result) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-star-blue">✅ 校验报告</h2>

        {/* 即使没有分析结果，也允许手动校验 */}
        <ManualVerify
          claim={manualClaim} setClaim={setManualClaim}
          onVerify={handleVerify} verifying={verifying}
          result={manualResult} error={manualError}
        />

        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="text-6xl mb-4">✅</div>
          <h3 className="text-xl font-bold text-gray-300 mb-2">暂无 Pipeline 校验数据</h3>
          <p className="text-gray-500">运行分析后，校验层（RAG + KG 交叉验证）将自动校验所有事实和假设</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-star-blue">✅ 校验报告</h2>

      {/* 手动校验 */}
      <ManualVerify
        claim={manualClaim} setClaim={setManualClaim}
        onVerify={handleVerify} verifying={verifying}
        result={manualResult} error={manualError}
      />

      {/* 总览卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '总断言数', value: String(counts.total), color: 'text-star-blue' },
          { label: '已验证', value: String(counts.verified), color: 'text-green-400' },
          { label: '部分验证', value: String(counts.partial), color: 'text-yellow-400' },
          { label: '冲突', value: String(counts.conflicting), color: 'text-red-400' },
        ].map((item, i) => (
          <div key={i} className="card p-4 text-center">
            <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
            <div className="text-sm text-gray-400">{item.label}</div>
          </div>
        ))}
      </div>

      {/* 校验详情 */}
      <div className="card p-4">
        <h3 className="text-lg font-bold mb-4 text-star-gold">逐条校验详情（RAG + KG 交叉验证）</h3>
        {verifications.length === 0 ? (
          <p className="text-gray-500 text-sm">本次分析未产生校验结果</p>
        ) : (
          <div className="space-y-3">
            {verifications.map((item, i) => (
              <div key={i} className="p-3 bg-white/5 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm flex-1 mr-4">{item.claim}</span>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={item.status} />
                    <span className="text-sm text-gray-400 w-20 text-right" title="RAG向量检索置信度：基于本地知识库的语义匹配度，0%表示索引为空或无匹配">
                      置信度 {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                {/* 证据详情 */}
                {(item.rag_evidence || item.kg_match || item.notes) && (
                  <div className="mt-2 pt-2 border-t border-white/5 text-xs text-gray-500 space-y-1">
                    {item.rag_evidence && <p>📄 RAG: {item.rag_evidence}</p>}
                    {item.kg_match && <p>🔗 KG: {item.kg_match}</p>}
                    {item.notes && <p>📝 {item.notes}</p>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 迭代反馈 */}
      {result.iteration_feedback && result.iteration_feedback.length > 0 && (
        <div className="card p-4">
          <h3 className="text-lg font-bold mb-3 text-star-gold">评测迭代反馈</h3>
          <div className="space-y-2">
            {result.iteration_feedback.map((fb, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-white/5 rounded-lg text-sm">
                <span className="text-star-blue font-bold whitespace-nowrap">{fb.dimension}</span>
                <span className="text-gray-500 whitespace-nowrap">({fb.current_score}分)</span>
                <span className="text-gray-300">{fb.issue}</span>
                <span className="text-green-400/80 ml-auto whitespace-nowrap">→ {fb.target_agent}</span>
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
    <div className="card p-4">
      <h3 className="text-lg font-bold mb-3 text-star-gold">🔍 手动断言校验</h3>
      <div className="flex gap-3">
        <input
          type="text"
          value={claim}
          onChange={e => setClaim(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onVerify()}
          placeholder="输入需要校验的断言，如：嫦娥六号于2024年5月3日发射"
          className="flex-1 bg-white/5 border border-star-blue/30 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-star-blue"
        />
        <button onClick={onVerify} disabled={verifying || !claim.trim()} className="btn-primary text-sm disabled:opacity-50">
          {verifying ? '校验中...' : '校验'}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      {result && (
        <div className="mt-3 p-4 bg-white/5 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm">{result.claim}</span>
            <div className="flex items-center gap-3">
              <StatusBadge status={result.status} />
              <span className="text-sm text-gray-400">置信度 {(result.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div className="text-xs text-gray-500 space-y-1">
            {result.rag_evidence && <p>📄 RAG 证据: {result.rag_evidence}</p>}
            {result.kg_match && <p>🔗 KG 匹配: {result.kg_match}</p>}
            {result.notes && <p>📝 备注: {result.notes}</p>}
            {result.cross_source_agreement !== null && (
              <p>🤝 交叉一致性: {result.cross_source_agreement ? '一致' : '不一致'}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default VerifyReport
