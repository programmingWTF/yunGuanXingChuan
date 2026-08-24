/**
 * 云观星传 - 用户认证上下文
 *
 * 挂载时静默探测会话（GET /api/auth/me）；未登录 user=null。
 * login/logout 与后端 httpOnly Cookie 会话配合。
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import axios from 'axios'
import { getMe, loginUser, logoutUser, setAuthToken, type AuthUser } from './api'

interface AuthContextValue {
  /** 当前登录用户（null = 未登录） */
  user: AuthUser | null
  /** 会话探测中（首次挂载） */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then(({ user: u, token }) => {
        if (!cancelled) setUser(u)
        if (token) setAuthToken(token) // 刷新后重新拿跨域上传 token
      })
      .catch(() => { /* 401 = 未登录，保持 null */ })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { user: u, token } = await loginUser(email, password)
    setUser(u)
    if (token) setAuthToken(token)
  }, [])

  const logout = useCallback(async () => {
    try { await logoutUser() } catch { /* 忽略 */ }
    setUser(null)
    setAuthToken(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 <AuthProvider> 内使用')
  return ctx
}

/** 提取后端错误文案（FastAPI: {detail}；网络错误给兜底） */
export function apiErrorText(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
  }
  return fallback
}
