/**
 * 云观星传 - 登录页（他山学术风：浅色卡片 + 衬线标题 + 青蓝交互）
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth, apiErrorText } from '../auth'
import StarfieldBackground from '../components/StarfieldBackground'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state as { email?: string; registered?: boolean } | null) ?? null
  const [email, setEmail] = useState(state?.email ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) return
    setSubmitting(true)
    setError('')
    try {
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(apiErrorText(err, '登录失败，请确认后端已启动'))
      setSubmitting(false)
    }
  }

  const inputCls =
    'w-full rounded-lg bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100 transition-all'

  return (
    <div className="min-h-screen relative font-body flex items-center justify-center px-4">
      <StarfieldBackground />
      <div className="relative z-10 w-full max-w-sm">
        {/* 品牌头 */}
        <div className="text-center mb-7">
          <h1 className="font-display text-2xl font-bold text-slate-900 tracking-wide">
            云观 · 星传
            <span className="ml-2 font-sans text-[10px] font-semibold text-slate-400 tracking-[0.22em] uppercase">AI Scientist</span>
          </h1>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            让科研流程可见，让每个产出可验证。
          </p>
        </div>

        <div className="card p-6">
          {/* 注册成功提示：登录后去模型设置填 API Key */}
          {state?.registered && (
            <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5">
              <p className="text-[11px] text-emerald-700 leading-relaxed">
                ✅ 注册成功！登录后请到<b>「模型设置」</b>填写你的 Qwen API Key
                （新用户可在 <a href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer" className="underline">阿里云百炼</a> 领取免费额度）
              </p>
            </div>
          )}
          <h2 className="sec-label !mb-4">登录</h2>
          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">邮箱</label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" className={inputCls} autoComplete="email" required
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">密码</label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="请输入密码" className={inputCls} autoComplete="current-password" required
              />
            </div>
            {error && <p className="text-[11px] text-red-600">{error}</p>}
            <button type="submit" disabled={submitting || !email.trim() || !password}
              className="btn-primary w-full text-xs disabled:opacity-40 disabled:cursor-not-allowed">
              {submitting ? '登录中…' : '登 录'}
            </button>
          </form>
          <p className="text-[11px] text-slate-500 mt-4 text-center">
            没有账号？<Link to="/register" className="text-sky-600 hover:text-sky-700 font-medium">去注册</Link>
          </p>
        </div>

        <p className="text-center text-[10px] text-slate-400 mt-5">
          登录即代表你同意仅将产出用于个人科研学习用途
        </p>
      </div>
    </div>
  )
}
