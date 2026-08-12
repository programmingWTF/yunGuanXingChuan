import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AdminConsole from './pages/AdminConsole'
import './index.css'

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
