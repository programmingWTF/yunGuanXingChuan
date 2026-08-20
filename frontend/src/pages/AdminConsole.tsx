/**
 * 云观星传 - 管理控制台（tzb-admin.liguiyu.com 专用，独立容器）
 *
 * 架构模仿 liguiyu-home 的 admin.liguiyu.com：应用层不校验身份，
 * 认证完全依赖 Cloudflare Access（管理员在 CF Zero Trust 侧配置）。
 *
 * 功能（轻量管理，不渲染项目详情）：
 * - 用户：列表 + 设为管理员/取消管理员 + 删除（级联删其项目）
 * - 项目：列表（标题 + 归属用户）+ 删除
 */
import { useEffect, useState } from 'react'
import { listAdminProjects, listAdminUsers, setAdminRole, deleteAdminUser, deleteAdminProject, type AdminProject, type AdminUser } from '../api'
import StarfieldBackground from '../components/StarfieldBackground'

export default function AdminConsole() {
  const [tab, setTab] = useState<'users' | 'projects'>('users')
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [projects, setProjects] = useState<AdminProject[] | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [confirmDelUser, setConfirmDelUser] = useState<string | null>(null)
  const [confirmDelProject, setConfirmDelProject] = useState<string | null>(null)

  const loadUsers = () => {
    listAdminUsers().then(({ users: u }) => setUsers(u)).catch(() => setError('加载用户失败'))
  }
  const loadProjects = () => {
    listAdminProjects().then(({ projects: p }) => setProjects(p)).catch(() => setError('加载项目失败'))
  }

  useEffect(() => { loadUsers(); loadProjects() }, [])

  const handleRole = async (u: AdminUser) => {
    setBusyId(u.id)
    setError('')
    try {
      await setAdminRole(u.id, u.role === 'admin' ? 'user' : 'admin')
      loadUsers()
    } catch { setError('操作失败') } finally { setBusyId(null) }
  }

  const handleDeleteUser = async (u: AdminUser) => {
    if (confirmDelUser !== u.id) { setConfirmDelUser(u.id); return }
    setConfirmDelUser(null)
    setBusyId(u.id)
    setError('')
    try {
      const r = await deleteAdminUser(u.id)
      setError(`已删除用户 ${r.deleted_user}（连带删除 ${r.deleted_projects} 个项目）`)
      loadUsers(); loadProjects()
    } catch { setError('删除失败') } finally { setBusyId(null) }
  }

  const handleDeleteProject = async (p: AdminProject) => {
    if (confirmDelProject !== p.id) { setConfirmDelProject(p.id); return }
    setConfirmDelProject(null)
    setBusyId(p.id)
    setError('')
    try {
      await deleteAdminProject(p.id)
      loadProjects()
    } catch { setError('删除失败') } finally { setBusyId(null) }
  }

  return (
    <div className="min-h-screen relative font-body">
      <StarfieldBackground />
      <div className="relative z-10 max-w-[1100px] mx-auto px-4 sm:px-8 py-10">
        {/* 页头 */}
        <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
          <div>
            <h1 className="font-display text-2xl font-bold text-slate-900 tracking-wide">
              云观 · 星传
              <span className="ml-2 font-sans text-[10px] font-semibold text-slate-400 tracking-[0.22em] uppercase">Admin Console</span>
            </h1>
            <p className="text-xs text-slate-500 mt-1">用户与项目管理（身份认证由 Cloudflare Access 负责）</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setTab('users')}
              className={`text-xs px-3.5 py-1.5 rounded-lg border transition-all ${tab === 'users' ? 'border-sky-300 bg-sky-50 text-sky-700 font-medium' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
              用户{users ? `（${users.length}）` : ''}
            </button>
            <button onClick={() => setTab('projects')}
              className={`text-xs px-3.5 py-1.5 rounded-lg border transition-all ${tab === 'projects' ? 'border-sky-300 bg-sky-50 text-sky-700 font-medium' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
              项目{projects ? `（${projects.length}）` : ''}
            </button>
          </div>
        </div>

        {error && <p className="text-[11px] text-red-600 mb-3">{error}</p>}

        {tab === 'users' ? (
          <div className="card p-4">
            <h3 className="sec-label !mb-3">账户用户</h3>
            {users === null && <p className="text-[11px] text-slate-400 py-4">加载中…</p>}
            {users && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-[10px] text-slate-400 font-sans tracking-wider uppercase border-b border-slate-100">
                      <th className="py-2 pr-4 font-medium">昵称</th>
                      <th className="py-2 pr-4 font-medium">邮箱</th>
                      <th className="py-2 pr-4 font-medium">角色</th>
                      <th className="py-2 pr-4 font-medium">注册时间</th>
                      <th className="py-2 pr-4 font-medium">项目数</th>
                      <th className="py-2 pr-4 font-medium">模型配置</th>
                      <th className="py-2 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id} className="border-b border-slate-50 hover:bg-slate-50/60">
                        <td className="py-2.5 pr-4 font-medium text-slate-700">{u.name}</td>
                        <td className="py-2.5 pr-4 text-slate-500">{u.email}</td>
                        <td className="py-2.5 pr-4">
                          <span className={`text-[9px] px-1.5 py-0.5 rounded border ${u.role === 'admin' ? 'text-amber-600 border-amber-200 bg-amber-50' : 'text-slate-500 border-slate-200'}`}>
                            {u.role === 'admin' ? '管理员' : '用户'}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 text-slate-400">{new Date(u.created_at * 1000).toLocaleString('zh-CN')}</td>
                        <td className="py-2.5 pr-4 text-slate-600">{u.project_count}</td>
                        <td className="py-2.5 pr-4">
                          <span className={`text-[9px] px-1.5 py-0.5 rounded border ${u.llm_configured ? 'text-emerald-600 border-emerald-200 bg-emerald-50' : 'text-slate-400 border-slate-200'}`}>
                            {u.llm_configured ? '已配置' : '未配置'}
                          </span>
                        </td>
                        <td className="py-2.5 text-right whitespace-nowrap">
                          <button onClick={() => void handleRole(u)} disabled={busyId === u.id}
                            className="text-[10px] px-2 py-1 rounded-md border border-slate-200 text-slate-500 hover:border-sky-300 hover:text-sky-700 disabled:opacity-40 mr-1.5 transition-all">
                            {u.role === 'admin' ? '取消管理员' : '设为管理员'}
                          </button>
                          <button onClick={() => void handleDeleteUser(u)} disabled={busyId === u.id}
                            className={`text-[10px] px-2 py-1 rounded-md border transition-all ${confirmDelUser === u.id ? 'bg-red-600 text-white border-red-600 font-medium' : 'border-slate-200 text-slate-500 hover:border-red-300 hover:text-red-600'}`}>
                            {confirmDelUser === u.id ? '确认删除？' : '删除'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="card p-4">
            <h3 className="sec-label !mb-3">全部项目</h3>
            {projects === null && <p className="text-[11px] text-slate-400 py-4">加载中…</p>}
            {projects?.length === 0 && <p className="text-[11px] text-slate-400 py-4 text-center">暂无项目</p>}
            {projects && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-[10px] text-slate-400 font-sans tracking-wider uppercase border-b border-slate-100">
                      <th className="py-2 pr-4 font-medium">标题</th>
                      <th className="py-2 pr-4 font-medium">归属用户</th>
                      <th className="py-2 pr-4 font-medium">状态</th>
                      <th className="py-2 pr-4 font-medium">创建时间</th>
                      <th className="py-2 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projects.map(p => (
                      <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50/60">
                        <td className="py-2.5 pr-4 font-medium text-slate-700 max-w-[260px] truncate" title={p.title}>{p.title}</td>
                        <td className="py-2.5 pr-4 text-slate-500">
                          {p.owner ? (
                            <span>{p.owner.name} <span className="text-slate-400">({p.owner.email})</span></span>
                          ) : (
                            <span className="text-amber-600">⚠️ 无主（legacy）</span>
                          )}
                        </td>
                        <td className="py-2.5 pr-4">
                          <span className={`text-[9px] px-1.5 py-0.5 rounded border ${p.status === 'completed' ? 'text-emerald-600 border-emerald-200' : 'text-sky-600 border-sky-200'}`}>
                            {p.status === 'completed' ? '已完成' : '进行中'}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 text-slate-400">{p.created_at?.slice(0, 19).replace('T', ' ')}</td>
                        <td className="py-2.5 text-right">
                          <button onClick={() => void handleDeleteProject(p)} disabled={busyId === p.id}
                            className={`text-[10px] px-2 py-1 rounded-md border transition-all ${confirmDelProject === p.id ? 'bg-red-600 text-white border-red-600 font-medium' : 'border-slate-200 text-slate-500 hover:border-red-300 hover:text-red-600'}`}>
                            {confirmDelProject === p.id ? '确认删除？' : '删除'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
