import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { StoreProvider } from './store'
import StarfieldBackground from './components/StarfieldBackground'
import TaskCenter from './pages/TaskCenter'
import Dashboard from './pages/Dashboard'
import Hypotheses from './pages/Hypotheses'
import Strategy from './pages/Strategy'
import KnowledgeGraph from './pages/KnowledgeGraph'
import VerifyReport from './pages/VerifyReport'
import Parliament from './pages/Parliament'

function AppLayout() {
  const location = useLocation()
  return (
    <div className="min-h-screen relative">
      <StarfieldBackground />
      <div className="relative z-10">
        <header className="border-b border-white/10 backdrop-blur-md bg-space-dark/50">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🌟</span>
                <div>
                  <h1 className="text-xl font-bold text-star-blue">云观星传</h1>
                  <p className="text-xs text-gray-400">科技议题传播分析与表达系统</p>
                </div>
              </div>
              <nav className="flex gap-2">
                <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
                  🚀 任务中心
                </NavLink>
                <NavLink to="/parliament" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  🏛️ 认知议会
                </NavLink>
                <NavLink to="/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  📊 数据驾驶舱
                </NavLink>
                <NavLink to="/hypotheses" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  💡 假设浏览
                </NavLink>
                <NavLink to="/strategy" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  📋 策略推演
                </NavLink>
                <NavLink to="/kg" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  🔗 知识图谱
                </NavLink>
                <NavLink to="/verify" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  ✅ 校验报告
                </NavLink>
              </nav>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6">
          <div key={location.pathname} className="page-transition">
            <Routes location={location}>
              <Route path="/" element={<TaskCenter />} />
              <Route path="/parliament" element={<Parliament />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/hypotheses" element={<Hypotheses />} />
              <Route path="/strategy" element={<Strategy />} />
              <Route path="/kg" element={<KnowledgeGraph />} />
              <Route path="/verify" element={<VerifyReport />} />
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
