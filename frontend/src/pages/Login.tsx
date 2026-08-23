/**
 * 云观星传 - 登录页（国风山水：毛玻璃卡片 + 渐变 Logo + 动态背景）
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth, apiErrorText } from '../auth'
import { AnimatedBackground, DecorativeClouds } from '../components/AnimatedBackground'
import { Sparkles } from 'lucide-react'

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
    'w-full rounded-xl bg-white/70 backdrop-blur-sm border border-slate-200/60 px-3.5 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all'

  return (
    <div className="min-h-screen relative flex items-center justify-center px-4">
      {/* 国风山水动态背景（设计稿全站背景层） */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <AnimatedBackground />
        <DecorativeClouds />
      </div>

      <div className="relative z-10 w-full max-w-sm">
        {/* 品牌头（设计稿 Logo 方块 + 双行标题） */}
        <div className="flex flex-col items-center text-center mb-7">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-600 to-blue-700 flex items-center justify-center shadow-lg shadow-indigo-200 mb-3">
            <Sparkles className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-[#17294F] tracking-tight">
            云观星传
            <span className="ml-2 text-[10px] font-semibold text-slate-400 tracking-widest uppercase align-middle">
              Cloud Star Legacy
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            让科研流程可见，让每个产出可验证。
          </p>
        </div>

        {/* 毛玻璃卡片（设计稿 bg-white/70 backdrop-blur 范式） */}
        <div className="p-6 rounded-2xl bg-white/70 backdrop-blur-sm border border-slate-200/50 shadow-sm">
          {state?.registered && (
            <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5">
              <p className="text-[11px] text-emerald-700 leading-relaxed">
                ✅ 注册成功！登录后请到<b>「模型设置」</b>填写你的 Qwen API Key
                （新用户可在 <a href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer" className="underline">阿里云百炼</a> 领取免费额度）
              </p>
            </div>
          )}
          <h2 className="text-sm font-semibold text-slate-700 mb-4">登录</h2>
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
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-700 text-white font-medium text-sm shadow-lg shadow-indigo-200/50 hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed">
              {submitting ? '登录中…' : '登 录'}
            </button>
          </form>
          <p className="text-[11px] text-slate-500 mt-4 text-center">
            没有账号？<Link to="/register" className="text-indigo-600 hover:text-indigo-700 font-medium">去注册</Link>
          </p>
        </div>

        <p className="text-center text-[10px] text-slate-400 mt-5">
          登录即代表你同意仅将产出用于个人科研学习用途
        </p>
      </div>
    </div>
  )
}
