/**
 * 云观星传 - 注册页（流程对齐 liguiyu-home）
 *
 * 昵称 + 邮箱 + 密码（确认密码 + 明文切换 + 一致性对号）→ 点「发送验证码」（6 位数字，10 分钟有效，60s 重发冷却）
 * → 填验证码 → 完成注册。注册成功跳转登录页（提示登录后填写 API Key）。
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { sendAuthCode, registerUser } from '../api'
import { apiErrorText } from '../auth'
import { AnimatedBackground, DecorativeClouds } from '../components/AnimatedBackground'

const RESEND_COOLDOWN = 60

const inputCls =
  'w-full rounded-xl bg-white/70 backdrop-blur-sm border border-slate-200/60 px-3.5 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all'

/** 密码输入框：右侧明文切换按钮 */
function PasswordField({
  value, onChange, placeholder, show, onToggleShow, autoComplete,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  show: boolean
  onToggleShow: () => void
  autoComplete: string
}) {
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} className={`${inputCls} pr-10`} autoComplete={autoComplete} required
      />
      <button
        type="button" onClick={onToggleShow} tabIndex={-1}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-indigo-600 transition-colors select-none"
        aria-label={show ? '隐藏密码' : '显示密码'}
        title={show ? '隐藏密码' : '显示密码'}
      >
        {show ? '🙈' : '👁'}
      </button>
    </div>
  )
}

export default function Register() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [showConfirmPwd, setShowConfirmPwd] = useState(false)
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

  // 两次密码一致性校验
  const pwdMatch = confirmPwd.length > 0 ? password === confirmPwd : null

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !email.trim() || !password || !code.trim()) return
    if (pwdMatch === false) { setError('两次输入的密码不一致'); return }
    setSubmitting(true)
    setError('')
    setInfo('')
    try {
      await registerUser(name.trim(), email.trim(), password, code.trim())
      // 注册成功 → 登录页（邮箱预填 + 提示填写 API Key）
      navigate('/login', { replace: true, state: { email: email.trim(), registered: true } })
    } catch (err) {
      setError(apiErrorText(err, '注册失败，请稍后重试'))
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center px-4 py-10">
      {/* 国风山水动态背景（设计稿全站背景层） */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <AnimatedBackground />
        <DecorativeClouds />
      </div>
      <div className="relative z-10 w-full max-w-sm">
        {/* 品牌头（设计稿 Logo 方块 + 双行标题） */}
        <div className="flex flex-col items-center text-center mb-7">
          <img
            src="/logo-64.png"
            alt="云观星传"
            className="h-14 w-auto object-contain mb-3"
            draggable={false}
          />
          <h1 className="text-2xl font-bold text-[#17294F] tracking-tight">
            云观星传
            <span className="ml-2 text-[10px] font-semibold text-slate-400 tracking-widest uppercase align-middle">
              Cloud Star Legacy
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            注册账号，开启你的 AI 科研工作台
          </p>
        </div>

        {/* 毛玻璃卡片（设计稿 bg-white/70 backdrop-blur 范式） */}
        <div className="p-6 rounded-2xl bg-white/70 backdrop-blur-sm border border-slate-200/50 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">注册</h2>
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
              <PasswordField
                value={password} onChange={setPassword}
                placeholder="设置登录密码" show={showPwd}
                onToggleShow={() => setShowPwd(v => !v)} autoComplete="new-password"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1.5">确认密码</label>
              <div className="relative">
                <PasswordField
                  value={confirmPwd} onChange={setConfirmPwd}
                  placeholder="再次输入密码" show={showConfirmPwd}
                  onToggleShow={() => setShowConfirmPwd(v => !v)} autoComplete="new-password"
                />
                {/* 一致性对号/叉号：两次密码一致 → 绿色 ✓；不一致 → 红色 ✗ */}
                {confirmPwd.length > 0 && (
                  <span className={`absolute right-10 top-1/2 -translate-y-1/2 text-sm select-none ${pwdMatch ? 'text-emerald-500' : 'text-red-500'}`}>
                    {pwdMatch ? '✓' : '✗'}
                  </span>
                )}
              </div>
              {confirmPwd.length > 0 && !pwdMatch && (
                <p className="text-[10px] text-red-500 mt-1">两次输入的密码不一致</p>
              )}
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
                  className="shrink-0 text-xs px-3.5 rounded-lg border border-indigo-300 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                >
                  {sending ? '发送中…' : countdown > 0 ? `${countdown}s 后重发` : '发送验证码'}
                </button>
              </div>
              {info && <p className="text-[10px] text-emerald-600 mt-1.5">{info}</p>}
            </div>
            {error && <p className="text-[11px] text-red-600">{error}</p>}
            <button type="submit"
              disabled={submitting || !name.trim() || !email.trim() || !password || !code.trim() || pwdMatch === false}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-700 text-white font-medium text-sm shadow-lg shadow-indigo-200/50 hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed">
              {submitting ? '注册中…' : '完成注册'}
            </button>
          </form>
          <p className="text-[11px] text-slate-500 mt-4 text-center">
            已有账号？<Link to="/login" className="text-indigo-600 hover:text-indigo-700 font-medium">去登录</Link>
          </p>
        </div>

        <p className="text-center text-[10px] text-slate-400 mt-5">
          注册即表示同意将验证码用于验证你的邮箱地址
        </p>
      </div>
    </div>
  )
}
