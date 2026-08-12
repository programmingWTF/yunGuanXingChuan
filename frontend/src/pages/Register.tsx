/**
 * 云观星传 - 注册页（流程对齐 liguiyu-home）
 *
 * 昵称 + 邮箱 + 密码 → 点「发送验证码」（6 位数字，10 分钟有效，60s 重发冷却）
 * → 填验证码 → 完成注册。注册成功跳转登录页（邮箱预填）。
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { sendAuthCode, registerUser } from '../api'
import { apiErrorText } from '../auth'
import StarfieldBackground from '../components/StarfieldBackground'

const RESEND_COOLDOWN = 60

export default function Register() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [sending, setSending] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current) }, [])

  const startCountdown = () => {
    setCountdown(RESEND_COOLDOWN)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1 && timerRef.current) clearInterval(timerRef.current)
        return prev <= 1 ? 0 : prev - 1
      })
    }, 1000)
  }

  const handleSendCode = async () => {
    if (!email.trim()) { setError('请先填写邮箱'); return }
    setSending(true)
    setError('')
    setInfo('')
    try {
      const res = await sendAuthCode(email.trim())
      setInfo(res.message)
      startCountdown()
    } catch (err) {
      setError(apiErrorText(err, '验证码发送失败，请确认后端已启动'))
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !email.trim() || !password || !code.trim()) return
    setSubmitting(true)
    setError('')
    setInfo('')
    try {
      await registerUser(name.trim(), email.trim(), password, code.trim())
      // 注册成功 → 登录页（邮箱预填）
      navigate('/login', { replace: true, state: { email: email.trim(), registered: true } })
    } catch (err) {
      setError(apiErrorText(err, '注册失败，请稍后重试'))
      setSubmitting(false)
    }
  }

  const inputCls =
    'w-full rounded-lg bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100 transition-all'

  return (
    <div className="min-h-screen relative font-body flex items-center justify-center px-4 py-10">
      <StarfieldBackground />
      <div className="relative z-10 w-full max-w-sm">
        {/* 品牌头 */}
        <div className="text-center mb-7">
          <h1 className="font-display text-2xl font-bold text-slate-900 tracking-wide">
            云观 · 星传
            <span className="ml-2 font-sans text-[10px] font-semibold text-slate-400 tracking-[0.22em] uppercase">AI Scientist</span>
          </h1>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            注册账号，开启你的 AI 科研工作台
          </p>
        </div>

        <div className="card p-6">
          <h2 className="sec-label !mb-4">注册</h2>
          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">昵称</label>
              <input
                type="text" value={name} onChange={e => setName(e.target.value)}
                placeholder="怎么称呼你" className={inputCls} maxLength={50} required
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">邮箱</label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" className={inputCls} autoComplete="email" required
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">密码（至少 6 位）</label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="设置登录密码" className={inputCls} autoComplete="new-password" minLength={6} required
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">邮箱验证码</label>
              <div className="flex gap-2">
                <input
                  type="text" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="6 位验证码" className={`${inputCls} font-mono tracking-widest`} inputMode="numeric" required
                />
                <button
                  type="button" onClick={handleSendCode} disabled={sending || countdown > 0}
                  className="shrink-0 text-xs px-3.5 rounded-lg border border-sky-300 bg-sky-50 text-sky-600 hover:bg-sky-100 disabled:opacity-40 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                >
                  {sending ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '发送验证码'}
                </button>
              </div>
              {info && <p className="text-[10px] text-emerald-600 mt-1.5">{info}</p>}
            </div>
            {error && <p className="text-[11px] text-red-600">{error}</p>}
            <button type="submit" disabled={submitting || !name.trim() || !email.trim() || !password || !code.trim()}
              className="btn-primary w-full text-xs disabled:opacity-40 disabled:cursor-not-allowed">
              {submitting ? '注册中…' : '完成注册'}
            </button>
          </form>
          <p className="text-[11px] text-slate-500 mt-4 text-center">
            已有账号？<Link to="/login" className="text-sky-600 hover:text-sky-700 font-medium">去登录</Link>
          </p>
        </div>

        <p className="text-center text-[10px] text-slate-400 mt-5">
          注册即表示同意将验证码用于验证你的邮箱地址
        </p>
      </div>
    </div>
  )
}
