/**
 * 云观星传 - 模型设置页（多租户"自带钥匙"模式）
 *
 * 每次推理使用你自己的 LLM API（平台不提供推理 API）：
 * - LLM（必填）：API Key + BaseURL + 模型ID —— 阿里云百炼 / 任意 OpenAI 兼容端点
 * - Embedding（可选）：填了用向量匹配（更精准），不填自动降级为文本匹配
 * - 保存时自动验证连通性；key 加密存储，管理后台看不到明文
 */
import { useEffect, useState, type FormEvent } from 'react'
import { getLlmConfig, saveLlmConfig } from '../api'
import { useAuth, apiErrorText } from '../auth'

const inputCls =
  'w-full rounded-lg bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all'

export default function Settings() {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  // LLM（必填）
  const [llmKey, setLlmKey] = useState('')
  const [llmBase, setLlmBase] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [llmMasked, setLlmMasked] = useState('')
  // Embedding（可选）
  const [embKey, setEmbKey] = useState('')
  const [embBase, setEmbBase] = useState('')
  const [embModel, setEmbModel] = useState('')
  const [embMasked, setEmbMasked] = useState('')

  useEffect(() => {
    getLlmConfig().then(({ llm, embedding }) => {
      setLlmBase(llm.base_url)
      setLlmModel(llm.model)
      setLlmMasked(llm.api_key_masked)
      setEmbBase(embedding.base_url)
      setEmbModel(embedding.model)
      setEmbMasked(embedding.api_key_masked)
    }).catch(() => setMsg({ type: 'err', text: '加载配置失败' }))
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!llmKey.trim() && llmMasked) {
      // 已有配置且未改 key：留空 = 沿用旧 key
      setMsg({ type: 'err', text: '密钥已存在且未修改：如需保留请留空即可（会沿用），如需更换请输入新 Key' })
      return
    }
    if (!llmKey.trim()) { setMsg({ type: 'err', text: '请填写 LLM API Key（首次配置必填）' }); return }
    setSaving(true)
    setMsg(null)
    try {
      const embedding = (embKey.trim() || embBase.trim() || embModel.trim())
        ? { api_key: embKey.trim() || '', base_url: embBase.trim(), model: embModel.trim() }
        : null
      const r = await saveLlmConfig({
        llm: { api_key: llmKey.trim(), base_url: llmBase.trim(), model: llmModel.trim() },
        embedding,
      })
      setMsg({ type: 'ok', text: r.message })
      setLlmKey(''); setEmbKey('')
      const fresh = await getLlmConfig()
      setLlmMasked(fresh.llm.api_key_masked)
      setEmbMasked(fresh.embedding.api_key_masked)
    } catch (err) {
      setMsg({ type: 'err', text: apiErrorText(err, '保存失败，请检查配置') })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-xs text-slate-400 py-8 text-center">加载中…</p>

  return (
    <div className="space-y-5">
      <div className="py-2">
        <h2 className="font-display text-2xl font-semibold text-slate-900 tracking-tight">模型设置</h2>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed max-w-2xl">
          平台不提供推理 API——每次生成使用<strong className="text-slate-700">你自己的</strong> Qwen 模型 Key（加密存储，管理后台不可见）。
          在阿里云百炼平台（按量付费或 Token Plan 订阅）获取 Key 后填入即可，<strong className="text-slate-700">联网搜索自动启用</strong>。
        </p>
        {/* 获取 API Key 指引 */}
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 space-y-1.5 max-w-2xl">
          <p className="text-[11px] font-medium text-slate-600">🔑 获取 API Key：</p>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            <span className="font-medium text-slate-600">方式一 · 阿里云百炼（推荐，新用户免费额度）：</span>
            <a href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">bailian.console.aliyun.com</a>
            <span className="text-slate-400"> → API-KEY 管理 → 创建 API Key（新用户 90 天内各模型 100 万 Token 免费额度）</span>
          </p>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            <span className="font-medium text-slate-600">方式二 · Token Plan 订阅：</span>
            <a href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">bailian.console.aliyun.com</a>
            <span className="text-slate-400"> → Token Plan → 我的订阅（专属 sk-tp-/sk-sp- Key，Base URL 以页面展示为准）</span>
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
        {/* LLM（必填） */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="sec-label !mb-0">LLM 模型（必填）</h3>
            {llmMasked && <span className="text-[10px] text-emerald-600">已配置 {llmMasked}</span>}
          </div>
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">API Key</label>
              <input type="password" value={llmKey} onChange={e => setLlmKey(e.target.value)}
                placeholder={llmMasked ? `${llmMasked}（留空沿用）` : 'sk-...'} className={inputCls} autoComplete="off" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">BaseURL</label>
              <input type="text" value={llmBase} onChange={e => setLlmBase(e.target.value)}
                placeholder="百炼：https://dashscope.aliyuncs.com/compatible-mode/v1 ｜ TokenPlan：https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
                className={inputCls} required />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">模型 ID</label>
              <input type="text" value={llmModel} onChange={e => setLlmModel(e.target.value)}
                placeholder="如 qwen3.8-max / qwen-plus / qwen3.8-max-preview" className={inputCls} required />
            </div>
          </div>
        </div>

        {/* Embedding（可选） */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="sec-label !mb-0">向量模型 Embedding（可选）</h3>
            {embMasked ? <span className="text-[10px] text-emerald-600">已配置 {embMasked}</span> : <span className="text-[10px] text-slate-400">未配置 · 自动降级为文本匹配</span>}
          </div>
          <p className="text-[11px] text-slate-400 mb-3">建议填写（历史经验匹配更精准）；不填也可以正常使用，只是匹配精度降低。</p>
          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">API Key</label>
              <input type="password" value={embKey} onChange={e => setEmbKey(e.target.value)}
                placeholder={embMasked ? `${embMasked}（留空沿用）` : 'sk-...'} className={inputCls} autoComplete="off" />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">BaseURL</label>
              <input type="text" value={embBase} onChange={e => setEmbBase(e.target.value)}
                placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" className={inputCls} />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">模型 ID</label>
              <input type="text" value={embModel} onChange={e => setEmbModel(e.target.value)}
                placeholder="如 qwen3.7-text-embedding" className={inputCls} />
            </div>
            {embKey || embBase || embModel ? (
              <p className="text-[10px] text-amber-600">Embedding 已填写：三项需一起填，保存时会验证连通性；想清除请全部清空后保存</p>
            ) : null}
          </div>
        </div>

        {msg && <p className={`text-[11px] ${msg.type === 'ok' ? 'text-emerald-600' : 'text-red-600'}`}>{msg.text}</p>}
        <button type="submit" disabled={saving}
          className="btn-primary text-xs disabled:opacity-40 disabled:cursor-not-allowed">
          {saving ? '保存并验证中…' : '保存配置（自动验证连通）'}
        </button>
        <p className="text-[10px] text-slate-400">当前账号：{user?.email}</p>
      </form>
    </div>
  )
}
