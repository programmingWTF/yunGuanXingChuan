/**
 * 云观星传 V2.0 — AI Scientist 科研工作台
 *
 * 前端按"科研流程"命名（非按智能体命名）：智能体隐藏在页面背后，
 * 用户看到的是科研工作流。核心交互：首页 Research Pipeline 时间轴，
 * 点击任意节点进入对应科研流程页面。
 *
 * 路由结构（9 页面）：
 *   /              科研首页（驾驶舱 + Pipeline）
 *   /inspiration   ① 选题孵化     /literature   ② 文献综述
 *   /design        ③ 研究设计     /method       ④ 方法推荐
 *   /data-analysis ⑤ 数据分析     /writing      ⑥ 学术写作
 *   /review        ⑦ 同行评审     /projects     我的项目
 * 旧功能页面保留在 Legacy 分组（路由不变，不破坏）。
 */
import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { StoreProvider, useStore } from './store'
import StarfieldBackground from './components/StarfieldBackground'
import Home from './pages/Home'
import Projects from './pages/Projects'
import StagePlaceholder from './pages/StagePlaceholder'
// Legacy 页面（保留，不破坏旧功能）
import TaskCenter from './pages/TaskCenter'
import Dashboard from './pages/Dashboard'
import Hypotheses from './pages/Hypotheses'
import Strategy from './pages/Strategy'
import KnowledgeGraph from './pages/KnowledgeGraph'
import VerifyReport from './pages/VerifyReport'
import Parliament from './pages/Parliament'
import ResearchOutput from './pages/ResearchOutput'
import CrossCultural from './pages/CrossCultural'

/* ── 导航定义：科研流程分组 ── */
const PIPELINE_NAV = [
  { to: '/', icon: '🏠', label: '科研首页', en: 'HOME', end: true },
  { to: '/inspiration', icon: '💡', label: '选题孵化', en: 'TOPIC' },
  { to: '/literature', icon: '📚', label: '文献综述', en: 'LITERATURE' },
  { to: '/design', icon: '🎯', label: '研究设计', en: 'DESIGN' },
  { to: '/method', icon: '🧪', label: '方法推荐', en: 'METHOD' },
  { to: '/data-analysis', icon: '📊', label: '数据分析', en: 'ANALYSIS' },
  { to: '/writing', icon: '✍️', label: '学术写作', en: 'WRITING' },
  { to: '/review', icon: '👨‍⚖️', label: '同行评审', en: 'REVIEW' },
  { to: '/projects', icon: '📁', label: '我的项目', en: 'PROJECTS' },
]

/* ── Legacy 导航（旧功能，保留可访问） ── */
const LEGACY_NAV = [
  { to: '/task-center', icon: '◈', label: '研究工作台', en: 'RESEARCH' },
  { to: '/parliament', icon: '⬡', label: 'AI 工作流', en: 'WORKFLOW' },
  { to: '/outputs', icon: '▤', label: '成果中心', en: 'OUTPUT' },
  { to: '/dashboard', icon: '◉', label: '传播分析', en: 'ANALYSIS' },
  { to: '/hypotheses', icon: '△', label: '研究假设', en: 'HYPOTHESES' },
  { to: '/strategy', icon: '▤', label: '传播策略', en: 'STRATEGY' },
  { to: '/kg', icon: '✦', label: '知识图谱', en: 'KNOWLEDGE' },
  { to: '/verify', icon: '◇', label: '证据校验', en: 'EVIDENCE' },
  { to: '/cross-cultural', icon: '⇌', label: '跨文化对照', en: 'CROSS-CULT' },
]

/* ── 实时时钟 ── */
function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <span className="font-mono text-xs text-slate-500 tabular-nums tracking-wider">
      {now.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}{' '}
      {now.toLocaleTimeString('zh-CN', { hour12: false })}
    </span>
  )
}

/* ── 侧边栏 ── */
function Sidebar() {
  const { stageMeta } = useStore()
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[228px] z-40 flex flex-col border-r border-white/[0.06] bg-[#060d1c]/80 backdrop-blur-xl">
      {/* LOGO */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 shrink-0">
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-astro-400 to-astro-600 opacity-90 shadow-[0_0_18px_rgba(12,184,232,0.5)]" />
            <div className="absolute inset-0 flex items-center justify-center text-lg text-white font-bold">✶</div>
            <div className="absolute -inset-1 rounded-xl border border-astro-400/30 animate-breathe" />
          </div>
          <div>
            <h1 className="font-display text-lg font-bold text-white leading-tight tracking-wide">云观星传</h1>
            <p className="text-[9px] font-mono text-astro-400/70 tracking-[0.18em] uppercase">AI Scientist</p>
          </div>
        </div>
      </div>

      <div className="mx-5 divider-glow" />

      {/* 科研流程导航 */}
      <nav className="flex-1 px-3.5 py-4 space-y-0.5 overflow-y-auto">
        <p className="sec-label px-3 mb-2">Research Pipeline</p>
        {PIPELINE_NAV.map(item => (
          <NavLink key={item.to} to={item.to} end={item.end ?? false}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <span className="w-6 text-center text-base opacity-80">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            <span className="text-[8px] font-mono tracking-widest text-slate-600">{item.en}</span>
          </NavLink>
        ))}

        {/* Legacy 分组 */}
        <details className="group mt-4">
          <summary className="sec-label px-3 mb-1 cursor-pointer select-none hover:text-slate-400 transition-colors">
            Legacy Modules <span className="text-[9px]">({stageMeta.length || 7})</span>
          </summary>
          <div className="space-y-0.5 mt-1">
            {LEGACY_NAV.map(item => (
              <NavLink key={item.to} to={item.to}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <span className="w-6 text-center text-base opacity-60">{item.icon}</span>
                <span className="flex-1 text-[12px]">{item.label}</span>
                <span className="text-[8px] font-mono tracking-widest text-slate-600">{item.en}</span>
              </NavLink>
            ))}
          </div>
        </details>
      </nav>

      {/* 底部系统状态 */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <SystemStatus />
      </div>
    </aside>
  )
}

/* ── 系统状态指示 ── */
function SystemStatus() {
  const { backendOnline } = useStore()
  const online = backendOnline !== false
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500">后端服务</span>
        <span className="flex items-center gap-1.5 text-[10px] font-medium">
          <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-aurora-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]' : 'bg-flare-400'} ${online ? 'animate-pulse' : ''}`} />
          <span className={online ? 'text-aurora-400' : 'text-flare-400'}>{online ? 'ONLINE' : 'OFFLINE'}</span>
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500">科研流程</span>
        <span className="text-[10px] font-mono text-astro-300">7 Agent</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500">搜索引擎</span>
        <span className="text-[10px] font-mono text-slate-400">Tavily + Qwen + 他山</span>
      </div>
    </div>
  )
}

/* ── 顶部状态栏 ── */
function TopBar() {
  const location = useLocation()
  const all = [...PIPELINE_NAV, ...LEGACY_NAV]
  const current = all.find(n => n.to === location.pathname)
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-8 h-14 border-b border-white/[0.06] bg-[#040810]/70 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        {current && (
          <>
            <span className="text-astro-400 text-sm">{current.icon}</span>
            <span className="text-sm font-medium text-slate-200">{current.label}</span>
            <span className="text-[9px] font-mono tracking-[0.25em] text-slate-600 uppercase">/ {current.en}</span>
          </>
        )}
        {!current && <span className="text-sm font-medium text-slate-200">云观星传 AI Scientist</span>}
      </div>
      <div className="flex items-center gap-5">
        <span className="hidden md:inline text-[10px] font-mono text-slate-600 tracking-wider">
          AI SCIENTIST RESEARCH WORKSPACE
        </span>
        <LiveClock />
      </div>
    </header>
  )
}

function AppLayout() {
  const location = useLocation()
  return (
    <div className="min-h-screen relative font-body">
      <StarfieldBackground />
      <Sidebar />
      <div className="relative z-10 ml-[228px]">
        <TopBar />
        <main className="px-8 py-7 max-w-[1600px]">
          <div key={location.pathname} className="page-transition">
            <Routes location={location}>
              {/* 科研工作台 9 页面 */}
              <Route path="/" element={<Home />} />
              <Route path="/inspiration" element={<StagePlaceholder stage={1} />} />
              <Route path="/literature" element={<StagePlaceholder stage={2} />} />
              <Route path="/design" element={<StagePlaceholder stage={3} />} />
              <Route path="/method" element={<StagePlaceholder stage={4} />} />
              <Route path="/data-analysis" element={<StagePlaceholder stage={5} />} />
              <Route path="/writing" element={<StagePlaceholder stage={6} />} />
              <Route path="/review" element={<StagePlaceholder stage={7} />} />
              <Route path="/projects" element={<Projects />} />

              {/* Legacy 路由（保留旧功能入口） */}
              <Route path="/task-center" element={<TaskCenter />} />
              <Route path="/parliament" element={<Parliament />} />
              <Route path="/outputs" element={<ResearchOutput />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/hypotheses" element={<Hypotheses />} />
              <Route path="/strategy" element={<Strategy />} />
              <Route path="/kg" element={<KnowledgeGraph />} />
              <Route path="/verify" element={<VerifyReport />} />
              <Route path="/cross-cultural" element={<CrossCultural />} />

              {/* 兜底：未知路径回科研首页 */}
              <Route path="*" element={<Home />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}

function App() {
  return (
    <StoreProvider>
      <Router>
        <AppLayout />
      </Router>
    </StoreProvider>
  )
}

export default App
