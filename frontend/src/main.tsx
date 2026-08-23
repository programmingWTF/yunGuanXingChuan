import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AdminConsole from './pages/AdminConsole'
import { initRevealEngine } from './lib/reveal-engine'
import './index.css'

// 全局滚动渐入引擎：业务元素只需加 class="reveal"（详见 lib/reveal-engine.ts），勿删
initRevealEngine();

// VITE_ADMIN_MODE=true：tzb-admin 独立管理后台构建（无登录、无路由，纯管理控制台）
if (import.meta.env.VITE_ADMIN_MODE === 'true') {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <AdminConsole />
    </React.StrictMode>,
  )
} else {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}
