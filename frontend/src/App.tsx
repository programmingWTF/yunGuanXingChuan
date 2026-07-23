import { useState, useEffect, useRef } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { StoreProvider, useStore } from './store'
import { healthCheck } from './api'
import StarfieldBackground from './components/StarfieldBackground'
import Dashboard from './pages/Dashboard'
import Hypotheses from './pages/Hypotheses'
import Strategy from './pages/Strategy'
import KnowledgeGraph from './pages/KnowledgeGraph'
import VerifyReport from './pages/VerifyReport'

/** 点击外部关闭 hook */
function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: () => void) {
  useEffect(() => {
    const listener = (e: MouseEvent) => {
      if (!ref.current || ref.current.contains(e.target as Node)) return
      handler()
    }
    document.addEventListener('mousedown', listener)
    return () => document.removeEventListener('mousedown', listener)
  }, [ref, handler])
}

/** 进度条：单行点 + 线，完成的变绿发光 */
function ProgressBar({ rounds }: { rounds: { label: string; steps: { name: string; display_name: string; status: string; message: string }[] }[] }) {
  if (rounds.length === 0) return null

  const allSteps: { name: string; display_name: string; status: string; message: string; roundLabel: string }[] = []
  for (const round of rounds) {
    for (const step of round.steps) {
      allSteps.push({ ...step, roundLabel: round.label })
    }
  }
  if (allSteps.length === 0) return null

  const dotColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-400 border-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]'
      case 'running':  return 'bg-star-blue border-star-blue shadow-[0_0_10px_rgba(0,212,255,0.7)] animate-pulse'
      case 'error':    return 'bg-red-400 border-red-400 shadow-[0_0_6px_rgba(248,113,113,0.5)]'
      default:         return 'bg-transparent border-gray-600'
    }
  }

  const labelColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400'
      case 'running':  return 'text-star-blue'
      case 'error':    return 'text-red-400'
      default:         return 'text-gray-600'
    }
  }

  return (
    <div className="flex items-center gap-3 animate-fade-in px-1 py-1">
      <div className="flex items-center flex-1 min-w-0 overflow-x-auto">
        {allSteps.map((step, i) => (
          <div key={step.name + i} className="flex items-center flex-shrink-0">
            <div className="flex flex-col items-center group relative" title={`${step.roundLabel}: ${step.message || step.display_name}`}>
              <div className={`w-3.5 h-3.5 rounded-full border-2 transition-all duration-700 ${dotColor(step.status)}`} />
              <span className={`text-[9px] mt-1 whitespace-nowrap transition-colors duration-300 ${labelColor(step.status)}`}>
                {step.display_name.replace(/^[^\s]+\s/, '')}
              </span>
            </div>
            {i < allSteps.length - 1 && (
              <div className={`h-0.5 w-6 sm:w-10 mx-0.5 rounded-full transition-all duration-700 ${
                allSteps[i].status === 'completed'
                  ? 'bg-green-400/70 shadow-[0_0_4px_rgba(74,222,128,0.3)]'
                  : 'bg-gray-700'
              }`} />
            )}
          </div>
        ))}
      </div>
      {allSteps.find(s => s.status === 'running')?.message && (
        <span className="text-[10px] text-star-blue/80 animate-pulse whitespace-nowrap flex-shrink-0 max-w-[220px] truncate">
          {allSteps.find(s => s.status === 'running')!.message}
        </span>
      )}
    </div>
  )
}

/** 顶部分析控制栏 */
function AnalysisBar() {
  const { state, runAnalysis, reset, loadHistoryResult, backendOnline, setBackendOnline } = useStore()
  const [topic, setTopic] = useState('')
  const [maxIter, setMaxIter] = useState(3)
  const [showHistory, setShowHistory] = useState(false)
  const [showIterMenu, setShowIterMenu] = useState(false)
  const historyRef = useRef<HTMLDivElement>(null)
  const iterRef = useRef<HTMLDivElement>(null)

  useClickOutside(historyRef, () => setShowHistory(false))
  useClickOutside(iterRef, () => setShowIterMenu(false))

  // 检测后端连接
  useEffect(() => {
    healthCheck()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false))
  }, [setBackendOnline])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const t = topic.trim()
    if (!t) return
    runAnalysis(t, maxIter)
  }

  const isRunning = state.phase === 'submitting' || state.phase === 'running'

  return (
    <div className="relative z-30 border-b border-white/10 bg-space-dark/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <form onSubmit={handleSubmit} className="flex items-center gap-3">
          {/* 议题输入 */}
          <input
            type="text"
            value={topic}
            onChange={e => setTopic(e.target.value)}
            placeholder="输入科技议题，如：嫦娥六号、天宫空间站..."
            disabled={isRunning}
            className="flex-1 bg-white/5 border border-star-blue/30 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-star-blue disabled:opacity-50"
          />

          {/* 最大轮次 - 自定义下拉 */}
          <div className="relative" ref={iterRef}>
            <button
              type="button"
              onClick={() => setShowIterMenu(!showIterMenu)}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-white/5 border border-star-blue/30 text-white text-sm disabled:opacity-50 hover:bg-star-blue/10 transition-all cursor-pointer"
            >
              <span className="text-gray-400 text-xs">最大轮次</span>
              <span className="font-bold text-star-blue">{maxIter}</span>
              <span className="text-gray-500 text-[10px]">▼</span>
            </button>
            {showIterMenu && (
              <div className="absolute left-0 top-12 z-[9999] w-32 bg-[#0d1526] border border-star-blue/30 rounded-xl shadow-2xl shadow-black/50 p-1.5 animate-fade-in">
                {[1, 2, 3, 4, 5].map(n => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => { setMaxIter(n); setShowIterMenu(false) }}
                    className={`w-full text-center py-2 rounded-lg text-sm transition-colors ${
                      n === maxIter ? 'bg-star-blue/20 text-star-blue font-bold' : 'text-gray-300 hover:bg-white/10'
                    }`}
                  >
                    {n} 轮
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 提交按钮 */}
          <button
            type="submit"
            disabled={isRunning || !topic.trim()}
            className="btn-primary whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRunning ? '⏳ 分析中...' : '🚀 开始分析'}
          </button>

          {/* 重置 */}
          {state.phase === 'completed' || state.phase === 'error' ? (
            <button type="button" onClick={reset} className="px-4 py-2 rounded-lg text-gray-400 hover:text-white transition-colors text-sm">
              重置
            </button>
          ) : null}
        </form>

        {/* 状态提示 + 多行进度条 */}
        <div className="mt-2 space-y-1.5">
          {/* 第一行：后端状态 + 完成/错误信息 + 历史按钮 */}
          <div className="flex items-center gap-4 text-xs">
            <span className={`flex items-center gap-1 ${backendOnline ? 'text-green-400' : backendOnline === false ? 'text-red-400' : 'text-gray-500'}`}>
              <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-green-400' : backendOnline === false ? 'bg-red-400' : 'bg-gray-500'}`} />
              {backendOnline ? '后端已连接' : backendOnline === false ? '后端离线' : '检测中...'}
            </span>
            {state.phase === 'completed' && state.result && (
              <span className="text-green-400">
                ✓ 分析完成：{state.result.topic} | 迭代 {state.result.iteration_count} 轮
              </span>
            )}
            {state.phase === 'error' && (
              <span className="text-red-400">✗ {state.errorMessage}</span>
            )}
            {/* 历史记录按钮 */}
            {state.history.length > 0 && (
              <div className="relative ml-auto" ref={historyRef}>
                <button
                  type="button"
                  onClick={() => setShowHistory(!showHistory)}
                  className="px-3 py-1 rounded-lg bg-white/5 border border-star-blue/30 text-xs text-star-blue hover:bg-star-blue/10 transition-all"
                >
                  📜 历史记录 ({state.history.length})
                </button>
                {showHistory && (
                  <div className="absolute right-0 top-8 z-[9999] w-80 max-h-72 overflow-y-auto bg-[#0d1526] border border-star-blue/30 rounded-xl shadow-2xl shadow-black/50 p-2 animate-fade-in">
                    <div className="text-[10px] text-gray-500 px-2 pb-1 border-b border-white/5 mb-1">点击加载历史分析结果</div>
                    {state.history.map((h) => (
                      <button
                        key={h.task_id}
                        type="button"
                        onClick={() => { loadHistoryResult(h.task_id); setShowHistory(false) }}
                        className="w-full text-left p-2.5 rounded-lg hover:bg-white/10 transition-colors text-xs mb-0.5"
                      >
                        <div className="text-white truncate font-medium">{h.topic}</div>
                        <div className="text-gray-500 mt-0.5">
                          {h.timestamp?.slice(0, 16).replace('T', ' ')} | {h.iteration_count}轮 | {h.status}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 进度条：线条 + 节点 */}
          {state.phase === 'running' && (
            <ProgressBar rounds={state.progress.rounds} />
          )}
          {state.phase === 'running' && state.progress.rounds.length === 0 && (
            <span className="text-star-blue animate-pulse text-xs">🔄 Pipeline 启动中...</span>
          )}
        </div>
      </div>
    </div>
  )
}

function AppLayout() {
  const location = useLocation()
  return (
    <div className="min-h-screen relative">
      {/* 3D 星空粒子背景 */}
      <StarfieldBackground />

      <div className="relative z-10">
        {/* 顶部导航 */}
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

        {/* 分析控制栏 */}
        <AnalysisBar />

        {/* 页面内容（带切换动画） */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          <div key={location.pathname} className="page-transition">
            <Routes location={location}>
              <Route path="/" element={<Dashboard />} />
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
