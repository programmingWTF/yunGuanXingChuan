/**
 * 云观星传 - 管理后台（admin）
 *
 * 模仿 liguiyu-home 管理后台的定位：查看所有人的使用历史记录 + 每条记录的归属。
 * 历史记录查看方式与前台科研工作台完全一致（同一套 ResearchPipeline + 阶段卡片渲染）。
 *
 * - 项目视图：全部项目（含归属人邮箱/昵称），点击查看详情（渲染与前台一致）
 * - 用户视图：注册用户列表 + 各自项目数
 */
import { useEffect, useState } from 'react'
import { listAdminProjects, listAdminUsers, type AdminProject, type AdminUser } from '../api'
import { useAuth } from '../auth'
import ResearchPipeline from '../components/ResearchPipeline'

const STAGE_NAMES: Record<string, string> = {
  '1': '选题孵化', '2': '文献综述', '3': '研究设计',
  '4': '方法推荐', '5': '数据分析', '6': '学术写作', '7': '同行评审',
}
const STAGE_ICONS: Record<string, string> = {
  '1': '💡', '2': '📚', '3': '🎯', '4': '🧪', '5': '📊', '6': '✍️', '7': '👨⚖️',
}
const STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: '待开始', cls: 'text-slate-500 border-slate-200' },
  running: { label: '运行中', cls: 'text-amber-600 border-red-200 animate-pulse' },
  awaiting_review: { label: '待确认', cls: 'text-sky-600 border-sky-300' },
  completed: { label: '已完成', cls: 'text-emerald-600 border-emerald-300' },
  failed: { label: '失败', cls: 'text-red-600 border-red-300' },
}

function fmtTime(ts?: string) {
  return ts ? ts.slice(0, 19).replace('T', ' ') : '—'
}

export default function Admin() {
  const { user } = useAuth()
  const [tab, setTab] = useState<'projects' | 'users'>('projects')
  const [projects, setProjects] = useState<AdminProject[] | null>(null)
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [selected, setSelected] = useState<AdminProject | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    listAdminProjects()
      .then(({ projects: p }) => { setProjects(p); setSelected(prev => prev ? p.find(x => x.id === prev.id) ?? null : null) })
      .catch(() => setError('加载项目列表失败（需要管理员权限）'))
  }, [])

  useEffect(() => {
    if (tab === 'users' && users === null) {
      listAdminUsers().then(({ users: u }) => setUsers(u)).catch(() => setError('加载用户列表失败'))
    }
  }, [tab, users])

  if (user?.role !== 'admin') {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-slate-500">无权限访问管理后台（仅 admin 角色可用）</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* 页头 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-2xl font-semibold text-slate-900 tracking-tight">管理后台</h2>
          <p className="text-xs text-slate-500 mt-1">
            全部用户的使用历史记录与归属（查看方式与前台科研工作台一致）
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab('projects')}
            className={`text-xs px-3.5 py-1.5 rounded-lg border transition-all ${tab === 'projects' ? 'border-sky-300 bg-sky-50 text-sky-700 font-medium' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
            项目记录{projects ? `（${projects.length}）` : ''}
          </button>
          <button onClick={() => setTab('users')}
            className={`text-xs px-3.5 py-1.5 rounded-lg border transition-all ${tab === 'users' ? 'border-sky-300 bg-sky-50 text-sky-700 font-medium' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}>
            用户{users ? `（${users.length}）` : ''}
          </button>
        </div>
      </div>

      {error && <p className="text-[11px] text-red-600">{error}</p>}

      {tab === 'projects' ? (
        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5 items-start">
          {/* 左：全部项目列表（含归属） */}
          <div className="card p-4">
            <h3 className="sec-label !mb-2">全部项目（{projects?.length ?? '…'}）</h3>
            <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
              {projects === null && <p className="text-[11px] text-slate-400 py-4 text-center">加载中…</p>}
              {projects?.length === 0 && <p className="text-[11px] text-slate-400 py-4 text-center">暂无项目</p>}
              {projects?.map(p => (
                <button key={p.id} onClick={() => setSelected(p)}
                  className={`group w-full text-left rounded-xl border px-3 py-2.5 transition-all ${selected?.id === p.id ? 'border-sky-300 bg-sky-50' : 'border-slate-200 bg-slate-50 hover:border-slate-300'}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[13px] font-medium text-slate-700 truncate">{p.title}</p>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border shrink-0 ${p.status === 'completed' ? 'text-emerald-600 border-emerald-200' : 'text-sky-600 border-sky-200'}`}>
                      {p.status === 'completed' ? '已完成' : '进行中'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-0.5 truncate">{p.interest}</p>
                  {/* 归属人：无主 legacy 项目高亮提示 */}
                  <p className="text-[10px] mt-0.5 truncate">
                    {p.owner ? (
                      <span className="text-slate-500">
                        👤 {p.owner.name} <span className="text-slate-400">({p.owner.email})</span>
                      </span>
                    ) : (
                      <span className="text-amber-600">⚠️ 无主（legacy）</span>
                    )}
                    <span className="text-slate-400 ml-2">{fmtTime(p.created_at)}</span>
                  </p>
                  <div className="flex items-center gap-1 mt-1.5">
                    {Object.keys(p.stages).map(s => {
                      const st = p.stages[s]?.status
                      const on = st === 'completed' || st === 'awaiting_review' || st === 'running'
                      return <span key={s} className={`w-3 h-1.5 rounded-full ${on ? (st === 'completed' ? 'bg-emerald-500' : 'bg-sky-500') : 'bg-slate-100'}`} />
                    })}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 右：项目详情（渲染与前台科研工作台完全一致） */}
          <div className="card-sweep p-5">
            {!selected ? (
              <p className="text-xs text-slate-400 text-center py-16">从左侧选择一条记录查看详情</p>
            ) : (
              <div className="space-y-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="min-w-0">
                    <h3 className="font-display text-lg font-bold text-slate-800">{selected.title}</h3>
                    <p className="text-[11px] text-slate-500 mt-1">兴趣：{selected.interest}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      创建于 {fmtTime(selected.created_at)}
                      {selected.owner && <> · 归属：{selected.owner.name}（{selected.owner.email}）</>}
                      {!selected.owner && <span className="text-amber-600"> · 无主（legacy）</span>}
                    </p>
                  </div>
                </div>

                {/* Research Pipeline 进度（与前台同一组件） */}
                <div className="border-t border-slate-100 pt-4">
                  <ResearchPipeline stages={selected.stages} currentStage={selected.current_stage} />
                </div>

                {/* 7 阶段产出物摘要（与前台同构） */}
                <div className="space-y-2.5 border-t border-slate-100 pt-4">
                  {Object.keys(selected.stages).map(s => {
                    const rec = selected.stages[s]
                    const meta = STATUS_META[rec?.status] ?? STATUS_META.pending
                    return (
                      <div key={s} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="text-base">{STAGE_ICONS[s]}</span>
                            <span className="text-[13px] font-medium text-slate-700">{STAGE_NAMES[s]}</span>
                            {rec?.error && <span className="text-[10px] text-red-600 truncate">{rec.error}</span>}
                          </div>
                          <span className={`text-[10px] shrink-0 px-2 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                        </div>
                        {rec?.output && (
                          <pre className="text-[9px] text-slate-500 whitespace-pre-wrap bg-slate-50 rounded-lg p-2.5 mt-2 max-h-24 overflow-y-auto">
                            {JSON.stringify(rec.output, null, 1).slice(0, 500)}
                          </pre>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ── 用户视图 ── */
        <div className="card p-4">
          <h3 className="sec-label !mb-2">注册用户（{users?.length ?? '…'}）</h3>
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
                    <th className="py-2 font-medium">模型配置</th>
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
                      <td className="py-2.5">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border ${u.llm_configured ? 'text-emerald-600 border-emerald-200 bg-emerald-50' : 'text-slate-400 border-slate-200'}`}>
                          {u.llm_configured ? '已配置' : '未配置'}
                        </span>
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
  )
}
