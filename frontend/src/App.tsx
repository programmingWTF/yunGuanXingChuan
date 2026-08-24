/**
 * 云观星传 — AI Scientist 科研工作台（国风山水主题）
 *
 * 外观与《代码2》设计稿一致：
 * 透明导航 → 滚动后毛玻璃 + 渐变 Logo 方块 + pill 导航 + emerald 状态胶囊；
 * 全局动态背景（星空/云纹/水墨）+ slate-900 深色页脚 + 滚动渐入。
 * 业务结构不变：16 个页面、路由、API、用户系统、管理后台全部保留。
 */
import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { StoreProvider, useStore } from './store'
import { AuthProvider, useAuth } from './auth'
import { AnimatedBackground, DecorativeClouds, BigDipperConstellation, Polaris } from './components/AnimatedBackground'
import HomeHero from './components/HomeHero'
import Workspace from './pages/Workspace'
import Inspiration from './pages/Inspiration'
import Literature from './pages/Literature'
import Design from './pages/Design'
import Method from './pages/Method'
import DataAnalysis from './pages/DataAnalysis'
import Writing from './pages/Writing'
import Review from './pages/Review'
import PaperLibrary from './pages/PaperLibrary'
import CrossCultural from './pages/CrossCultural'
import Login from './pages/Login'
import Register from './pages/Register'
import UIShowcase from './pages/UIShowcase'
import Admin from './pages/Admin'
import Settings from './pages/Settings'
import { Sparkles, Search, Lightbulb, BookOpen, Target, FlaskConical, BarChart3, PenLine, Users, Library, Menu, X } from 'lucide-react'
import { cn } from './lib/utils'

/* ── 导航定义：科研工作台 + 科研流程 ── */
const PIPELINE_NAV = [
  { to: '/', icon: Search, label: '科研工作台', end: true },
  { to: '/inspiration', icon: Lightbulb, label: '选题孵化' },
  { to: '/literature', icon: BookOpen, label: '文献综述' },
  { to: '/design', icon: Target, label: '研究设计' },
  { to: '/method', icon: FlaskConical, label: '方法推荐' },
  { to: '/data-analysis', icon: BarChart3, label: '数据分析' },
  { to: '/writing', icon: PenLine, label: '学术写作' },
  { to: '/review', icon: Users, label: '同行评审' },
  { to: '/library', icon: Library, label: '论文库' },
]

/* ── 实时时钟 ── */
function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <span className="font-mono text-xs text-slate-400 tabular-nums tracking-wider">
      {now.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}{' '}
      {now.toLocaleTimeString('zh-CN', { hour12: false })}
    </span>
  )
}

/* ── 后端状态胶囊（emerald 运行中 / 红色离线）── */
function BackendDot() {
  const { backendOnline } = useStore()
  const online = backendOnline !== false
  return (
    <div className={cn(
      'hidden 2xl:flex items-center gap-2 px-3 py-1.5 rounded-full border',
      online
        ? 'bg-emerald-50 border-emerald-200'
        : 'bg-red-50 border-red-200',
    )}>
      <div className={cn(
        'w-2 h-2 rounded-full',
        online ? 'bg-emerald-500 animate-pulse' : 'bg-red-500',
      )} />
      <span className={cn(
        'text-xs font-medium',
        online ? 'text-emerald-700' : 'text-red-700',
      )}>
        {online ? '系统运行中' : '系统离线'}
      </span>
    </div>
  )
}

/* ── 顶部导航（《代码2》设计稿样式）：透明 → 滚动后毛玻璃 ── */
function TopNav() {
  const { user, logout } = useAuth()
  const [isScrolled, setIsScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <nav
      className={cn(
        'fixed top-0 left-0 right-0 z-50 transition-all duration-500',
        isScrolled
          ? 'bg-white/90 backdrop-blur-xl shadow-sm border-b border-slate-200/50'
          : 'bg-transparent',
      )}
    >
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          {/* Logo：渐变方块 + 双行标题（设计稿原样） */}
          <NavLink to="/" className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-blue-700 flex items-center justify-center shadow-lg shadow-indigo-200">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-800 tracking-tight">
                云观星传
              </span>
              <span className="text-[10px] text-slate-500 tracking-wider">
                Cloud Star Legacy
              </span>
            </div>
          </NavLink>

          {/* 桌面导航（设计稿样式：rounded-lg pill，激活态 indigo） */}
          <div className="hidden xl:flex items-center gap-1 min-w-0">
            {PIPELINE_NAV.map(item => (
              <NavLink key={item.to} to={item.to} end={item.end ?? false}
                className={({ isActive }) => cn(
                  'px-2.5 py-2 rounded-lg text-xs font-medium transition-all duration-200 flex items-center gap-1 whitespace-nowrap',
                  isActive
                    ? 'bg-[#eef2f7] text-[#1c315b] shadow-[inset_0_-2px_0_#17294f]'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/50',
                )}>
                <item.icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            ))}
          </div>

          {/* 右侧操作区：状态胶囊 + 时钟 + 用户区 */}
          <div className="flex items-center gap-3 shrink-0">
            <BackendDot />
            {user ? (
              <div className="flex items-center gap-2.5">
                {user.role === 'admin' && (
                  <NavLink to="/admin"
                    className={({ isActive }) => cn(
                      'hidden 2xl:inline-flex text-[11px] font-medium px-2.5 py-1.5 rounded-lg border transition-all whitespace-nowrap',
                      isActive
                        ? 'bg-amber-50 border-amber-300 text-amber-700'
                        : 'border-slate-200 text-slate-500 hover:border-amber-300 hover:text-amber-700',
                    )}>
                    🛡 管理后台
                  </NavLink>
                )}
                <NavLink to="/settings"
                  className={({ isActive }) => cn(
                    'text-[11px] font-medium px-2.5 py-1.5 rounded-lg border transition-all whitespace-nowrap',
                    isActive
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                      : 'border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-700',
                  )}>
                  ⚙ 模型设置
                </NavLink>
                <button className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors" title={user.email}>
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-slate-400 to-slate-600" />
                </button>
                <button onClick={() => void logout()}
                  className="text-[11px] text-slate-400 hover:text-red-600 transition-colors shrink-0">
                  退出
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {/* 未登录：主界面可用（浏览），但运行操作需登录 */}
                <NavLink to="/register"
                  className="text-[11px] font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-700 transition-all">
                  注册
                </NavLink>
                <NavLink to="/login"
                  className="text-[11px] font-medium px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-all shadow-sm">
                  登录
                </NavLink>
              </div>
            )}
            {/* 移动端菜单按钮 */}
            <button
              className="xl:hidden p-2 rounded-lg hover:bg-slate-100 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="菜单"
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 移动端菜单（设计稿样式） */}
      {mobileMenuOpen && (
        <div className="xl:hidden bg-white/85 backdrop-blur-xl border-t border-slate-200 shadow-lg">
          <div className="w-full px-4 py-4 grid grid-cols-2 gap-1">
            {PIPELINE_NAV.map(item => (
              <NavLink key={item.to} to={item.to} end={item.end ?? false}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) => cn(
                  'px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2',
                  isActive
                    ? 'bg-[#eef2f7] text-[#1c315b] shadow-[inset_0_-2px_0_#17294f]'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/50',
                )}>
                <item.icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  )
}

/* ── 当前页面标题条（设计稿内页头部风格：白底毛玻璃分隔区）── */
function PageHeading() {
  const location = useLocation()
  const current = PIPELINE_NAV.find(n => n.to === location.pathname)
  if (!current || location.pathname === '/') return null
  const Icon = current.icon
  return (
    <div className="pt-16">
      <div className="bg-white/70 backdrop-blur-sm border-b border-slate-200/50">
        <div className="w-full px-4 sm:px-6 lg:px-8 py-3.5 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-100 to-blue-100 flex items-center justify-center">
            <Icon className="w-4 h-4 text-indigo-600" />
          </div>
          <h1 className="text-lg font-bold text-slate-800 tracking-tight">{current.label}</h1>
        </div>
      </div>
    </div>
  )
}

/* ── 页脚（设计稿样式：slate-900 深色 + 四栏 + 底部状态条）── */
function Footer() {
  return (
    <footer id="footer" className="relative z-20 mt-auto py-16 px-4 bg-slate-900 text-white">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-4 gap-8 mb-12">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="text-lg font-bold">云观星传</span>
                <span className="text-xs text-slate-400 ml-2">Cloud Star Legacy</span>
              </div>
            </div>
            <p className="text-slate-400 text-sm max-w-md leading-relaxed">
              面向科技议题研究与国际传播的智能辅助平台，
              基于 AI Scientist 范式，提供从信息搜集到成果产出的完整闭环。
            </p>
          </div>
          <div>
            <h4 className="font-semibold mb-4">系统模块</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>科研工作台</li>
              <li>选题孵化 · 文献综述</li>
              <li>研究设计 · 方法推荐</li>
              <li>数据分析 · 学术写作 · 同行评审</li>
              <li>论文库</li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-4">技术支持</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>通义大模型</li>
              <li>RAG + 知识图谱双校验</li>
              <li>FAISS 向量库</li>
              <li>多智能体协作</li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-sm text-slate-500">
            © 2026 云观星传 · 挑战杯「揭榜挂帅」科技议题传播分析与表达系统
          </p>
          <div className="flex items-center gap-4">
            <LiveClock />
            <BackendDot />
          </div>
        </div>
      </div>
    </footer>
  )
}

function AppLayout() {
  const location = useLocation()
  const { user, loading } = useAuth()
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register'
  const isShowcase = location.pathname === '/ui-showcase'

  // 组件展示页：独立布局，不依赖认证/后端，便于验收 shadcn/ui 组件与设计令牌
  if (isShowcase) {
    return (
      <div className="min-h-screen bg-background">
        <UIShowcase />
      </div>
    )
  }

  // 会话探测中：避免闪烁，显示轻量占位
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-xs text-slate-400">加载中…</div>
  }
  // 未登录：不再强制跳登录页——主界面可浏览（运行/生成操作替换为登录按钮）
  // 已登录访问登录/注册页则回工作台
  if (user && isAuthPage) return <Navigate to="/" replace />

  // 登录/注册页：独立布局（无顶栏/页脚，保留动态背景）
  if (isAuthPage) {
    return (
      <Routes location={location}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* 全局动态背景 - 所有页面共享（设计稿 __root 布局） */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <AnimatedBackground />
        <DecorativeClouds />
      </div>
      <TopNav />
      <PageHeading />
      <div className="relative z-10 flex-1 flex flex-col text-slate-800 overflow-x-hidden">
        {/* 星座装饰（设计稿内页装饰：北斗七星 + 北极星） */}
        <div className="absolute inset-x-0 top-48 bottom-0 z-0 overflow-hidden pointer-events-none">
          <BigDipperConstellation />
          <Polaris />
        </div>
        <main className="relative z-10 px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
          <div key={location.pathname} className="page-transition">
            <Routes location={location}>
              {/* 首页：效果图 Hero Landing + 科研工作台（点击「开始分析」锚点滚动到此） */}
              <Route path="/" element={<><HomeHero /><div id="workspace"><Workspace /></div></>} />
              {/* "我的项目"入口（StageUI 引导链接指向此路由）：复用科研工作台 */}
              <Route path="/projects" element={<Workspace />} />
              <Route path="/inspiration" element={<Inspiration />} />
              <Route path="/literature" element={<Literature />} />
              <Route path="/design" element={<Design />} />
              <Route path="/method" element={<Method />} />
              <Route path="/data-analysis" element={<DataAnalysis />} />
              <Route path="/writing" element={<Writing />} />
              <Route path="/review" element={<Review />} />
              <Route path="/library" element={<PaperLibrary />} />
              <Route path="/cross-cultural" element={<CrossCultural />} />

              {/* 管理后台（admin 角色；后端二次校验） */}
              <Route path="/admin" element={<Admin />} />

              {/* 模型设置（多租户自带钥匙：用户自己的 LLM API） */}
              <Route path="/settings" element={<Settings />} />

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
