/**
 * 云观星传 V3.0 — AI Scientist 科研工作台（他山世界学术风）
 *
 * 布局：顶部固定导航（白底 48px + 衬线链接），内容区浅色学术风。
 * 前端按"科研流程"命名：智能体隐藏在页面背后，用户看到的是科研工作流。
 *
 * 路由结构：
 *   /              科研工作台（默认页：历史项目 / 新建 / 一键生成 / 进度 / 产出物 / 导出）
 *   /inspiration   ① 选题孵化     /literature   ② 文献综述
 *   /design        ③ 研究设计     /method       ④ 方法推荐
 *   /data-analysis ⑤ 数据分析     /writing      ⑥ 学术写作
 *   /review        ⑦ 同行评审
 */
import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { StoreProvider, useStore } from './store'
import { AuthProvider, useAuth } from './auth'
import StarfieldBackground from './components/StarfieldBackground'
import Workspace from './pages/Workspace'
import Inspiration from './pages/Inspiration'
import Literature from './pages/Literature'
import Design from './pages/Design'
import Method from './pages/Method'
import DataAnalysis from './pages/DataAnalysis'
import Writing from './pages/Writing'
import Review from './pages/Review'
import CrossCultural from './pages/CrossCultural'
import Login from './pages/Login'
import Register from './pages/Register'
import Admin from './pages/Admin'

/* ── 导航定义：科研工作台 + 科研流程 ── */
const PIPELINE_NAV = [
  { to: '/', icon: '🏠', label: '科研工作台', en: 'HOME', end: true },
  { to: '/inspiration', icon: '💡', label: '选题孵化', en: 'TOPIC' },
  { to: '/literature', icon: '📚', label: '文献综述', en: 'LITERATURE' },
  { to: '/design', icon: '🎯', label: '研究设计', en: 'DESIGN' },
  { to: '/method', icon: '🧪', label: '方法推荐', en: 'METHOD' },
  { to: '/data-analysis', icon: '📊', label: '数据分析', en: 'ANALYSIS' },
  { to: '/writing', icon: '✍️', label: '学术写作', en: 'WRITING' },
  { to: '/review', icon: '👨‍⚖️', label: '同行评审', en: 'REVIEW' },
]

/* ── 实时时钟 ── */
function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <span className="font-mono text-xs text-slate-400 tabular-nums tracking-wider hidden md:inline">
      {now.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}{' '}
      {now.toLocaleTimeString('zh-CN', { hour12: false })}
    </span>
  )
}

/* ── 后端状态点 ── */
function BackendDot() {
  const { backendOnline } = useStore()
  const online = backendOnline !== false
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
      <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-500' : 'bg-red-500'} ${online ? 'animate-pulse' : ''}`} />
      {online ? 'ONLINE' : 'OFFLINE'}
    </span>
  )
}

/* ── 顶部导航：白底 48px + 1px 底边框 + 衬线链接（他山 8.1）── */
function TopNav() {
  const { user, logout } = useAuth()
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-slate-200/80">
      <div className="mx-auto h-12 flex items-center justify-between gap-4 px-4 sm:px-8 lg:px-10">
        <div className="flex items-center gap-6 min-w-0">
          {/* Logo：衬线 + 字间留白（他山 Logo 写法） */}
          <NavLink to="/" className="font-display font-bold text-[15px] text-slate-900 tracking-wide shrink-0 whitespace-nowrap">
            云观 · 星传
            <span className="ml-1.5 font-sans text-[10px] font-semibold text-slate-400 tracking-[0.22em] uppercase">AI Scientist</span>
          </NavLink>
          {/* 科研流程导航（窄屏横向滚动，滚动条隐藏） */}
          <nav className="flex items-center gap-0.5 overflow-x-auto no-scrollbar min-w-0">
            {PIPELINE_NAV.map(item => (
              <NavLink key={item.to} to={item.to} end={item.end ?? false}
                className={({ isActive }) => `nav-link whitespace-nowrap ${isActive ? 'active' : ''}`}>
                <span className="text-[13px]">{item.icon}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <span className="hidden lg:inline text-[10px] font-sans text-slate-400 tracking-[0.22em] uppercase">
            Research Workspace
          </span>
          <BackendDot />
          <LiveClock />
          {user && (
            <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
              {user.role === 'admin' && (
                <NavLink to="/admin"
                  className={({ isActive }) => `text-[11px] font-medium px-2 py-1 rounded-md border transition-all ${isActive ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-slate-200 text-slate-500 hover:border-amber-300 hover:text-amber-700'}`}>
                  🛡 管理后台
                </NavLink>
              )}
              <span className="text-xs font-medium text-slate-600 max-w-[80px] truncate" title={user.email}>{user.name}</span>
              <button onClick={() => void logout()}
                className="text-[11px] text-slate-400 hover:text-red-600 transition-colors shrink-0">
                退出
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

/* ── 当前页面标题条（顶栏下方，白底分隔区）── */
function PageHeading() {
  const location = useLocation()
  const current = PIPELINE_NAV.find(n => n.to === location.pathname)
  if (!current) return null
  return (
    <div className="bg-white border-b border-slate-200/80">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-4 flex items-baseline gap-3">
        <span className="text-lg">{current.icon}</span>
        <h1 className="font-display text-xl font-semibold text-slate-900 tracking-tight">{current.label}</h1>
        <span className="font-sans text-[10px] font-semibold text-slate-400 tracking-[0.28em] uppercase">
          {current.en}
        </span>
      </div>
    </div>
  )
}

/* ── 页脚：深海军蓝 #0E2E4F（他山 8.7：全站唯一大面积深色）── */
function Footer() {
  return (
    <footer className="relative z-10 mt-20 bg-footer text-white/70">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-12 grid gap-10 md:grid-cols-3">
        <div>
          <p className="font-display text-lg font-semibold text-white tracking-wide">云观 · 星传</p>
          <p className="text-sm mt-2.5 leading-relaxed">对齐需求，寻找协作 —— 在讨论中推进科学发现。</p>
        </div>
        <div>
          <p className="font-sans text-[11px] font-semibold text-white/50 tracking-[0.22em] uppercase mb-3">Research Pipeline</p>
          <p className="text-sm leading-relaxed">选题孵化 · 文献综述 · 研究设计 · 方法推荐 · 数据分析 · 学术写作 · 同行评审</p>
        </div>
        <div>
          <p className="font-sans text-[11px] font-semibold text-white/50 tracking-[0.22em] uppercase mb-3">Powered By</p>
          <p className="text-sm leading-relaxed">通义大模型 · RAG + 知识图谱双校验 · AI Scientist 多智能体协作</p>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-8 py-4 flex flex-wrap items-center justify-between gap-2 text-xs text-white/50">
          <span>© 2026 云观星传 · AI Scientist 科研工作台</span>
          <span>挑战杯「揭榜挂帅」· 科技议题传播分析与表达系统</span>
        </div>
      </div>
    </footer>
  )
}

function AppLayout() {
  const location = useLocation()
  const { user, loading } = useAuth()
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register'

  // 会话探测中：避免闪烁，显示轻量占位
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-xs text-slate-400">加载中…</div>
  }
  // 路由守卫：未登录只能访问登录/注册页；已登录访问登录/注册页则回工作台
  if (!user && !isAuthPage) return <Navigate to="/login" replace />
  if (user && isAuthPage) return <Navigate to="/" replace />

  // 登录/注册页：独立布局（无顶栏/页脚）
  if (isAuthPage) {
    return (
      <Routes location={location}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    )
  }

  return (
    <div className="min-h-screen relative font-body">
      <StarfieldBackground />
      <TopNav />
      <PageHeading />
      <div className="relative z-10 pt-12">
        <main className="px-4 sm:px-8 py-8 max-w-[1400px] mx-auto">
          <div key={location.pathname} className="page-transition">
            <Routes location={location}>
              {/* 科研工作台（默认页）+ 7 个科研流程页 */}
              <Route path="/" element={<Workspace />} />
              {/* “我的项目”入口（StageUI 引导链接指向此路由）：复用科研工作台 */}
              <Route path="/projects" element={<Workspace />} />
              <Route path="/inspiration" element={<Inspiration />} />
              <Route path="/literature" element={<Literature />} />
              <Route path="/design" element={<Design />} />
              <Route path="/method" element={<Method />} />
              <Route path="/data-analysis" element={<DataAnalysis />} />
              <Route path="/writing" element={<Writing />} />
              <Route path="/review" element={<Review />} />
              <Route path="/cross-cultural" element={<CrossCultural />} />

              {/* 管理后台（admin 角色；后端二次校验） */}
              <Route path="/admin" element={<Admin />} />

              {/* 兜底：未知路径回科研工作台 */}
              <Route path="*" element={<Workspace />} />
            </Routes>
          </div>
        </main>
        <Footer />
      </div>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <StoreProvider>
        <Router>
          <AppLayout />
        </Router>
      </StoreProvider>
    </AuthProvider>
  )
}

export default App
