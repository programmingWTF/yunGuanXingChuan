/**
 * 云观星传 - 联网搜索来源列表（可点击链接）
 *
 * Issue #98：把联网搜索结果（search_sources）渲染为可点击链接，供用户查阅原始出处。
 * 每条来源展示：可点击标题 + 来源引擎标识 + 摘要。
 *
 * - 链接新标签页打开（target="_blank" + rel="noopener noreferrer"）
 * - 无合法 URL 的结果不渲染 <a>，仅按纯文本展示，避免空/危险链接
 * - 样式与现有 card / sec-label 风格统一
 * - 来源较多时提供折叠/展开
 */
import { useState } from 'react'
import type { SearchSource } from '../api'

/** 合法的外部链接协议（白名单）：仅 http/https，防止 javascript: 等注入 */
const SAFE_URL = /^https?:\/\//i

/** 来源引擎的展示名（未知/空返回兜底文案） */
export function sourceEngineLabel(source: string): string {
  const s = (source || '').trim()
  return s || 'Web'
}

/** 单条来源行：可点击标题 + 引擎标识 + 摘要 */
function SourceRow({ item, index }: { item: SearchSource; index: number }) {
  const title = (item.title || '').trim()
  const url = SAFE_URL.test(item.url || '') ? item.url!.trim() : null
  const content = (item.content || '').trim()
  const engine = sourceEngineLabel(item.source)

  const titleNode = url ? (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[12.5px] font-medium text-indigo-700 hover:text-indigo-600 hover:underline transition-colors break-words line-clamp-2"
      title={url}
    >
      {title || url}
    </a>
  ) : (
    <span className="text-[12.5px] font-medium text-slate-600 break-words line-clamp-2">
      {title || '(无标题来源)'}
    </span>
  )

  return (
    <li className="flex items-start gap-2.5 rounded-xl bg-slate-50/70 border border-slate-100 px-3.5 py-2.5 hover:border-indigo-200/80 transition-colors">
      <span className="text-[9px] font-mono text-slate-400 mt-1 shrink-0">#{index + 1}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">{titleNode}</div>
          {/* 来源引擎标识（Tavily / 百炼 / 他山 等） */}
          <span className="text-[9px] font-mono text-slate-400 shrink-0 px-1.5 py-0.5 rounded border border-slate-200 bg-white/70 uppercase tracking-wide">
            {engine}
          </span>
        </div>
        {content && <p className="text-[11px] text-slate-500 leading-snug mt-1 line-clamp-2">{content}</p>}
      </div>
    </li>
  )
}

interface SearchSourcesProps {
  sources?: SearchSource[] | null
  /** 默认展示条数（超过则折叠，可通过“展开全部”查看） */
  collapseAfter?: number
  /** 自定义标题文案 */
  title?: string
  /** 本阶段实际使用的搜索查询词（Issue #98 优化：标注“哪个阶段搜了什么”） */
  query?: string
  className?: string
}

/**
 * 联网搜索来源：可折叠的可点击链接列表。
 *
 * 无来源（空数组 / null / undefined）时返回 null，不占版面。
 * query 非空时在标题下方以水墨小字展示“本阶段搜索词”。
 */
export default function SearchSources({
  sources,
  collapseAfter = 3,
  title = '📎 联网搜索来源',
  query = '',
  className = '',
}: SearchSourcesProps) {
  // 注意：useState 必须置于任何提前 return 之前（React Hooks 规则），
  // 否则 sources 从空变非空时会在同一组件上出现 Hook 数量变化导致崩溃
  const [expanded, setExpanded] = useState(false)
  const list = Array.isArray(sources) ? sources.filter(Boolean) : []
  if (list.length === 0) return null

  const shown = expanded ? list : list.slice(0, collapseAfter)
  const hasMore = list.length > collapseAfter
  const queryText = (query || '').trim()

  return (
    <div className={`card p-4 ${className}`}>
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <h3 className="sec-label !mb-0">{title}</h3>
        <span className="text-[10px] font-sans text-slate-400">共 {list.length} 条</span>
      </div>
      {queryText && (
        <div className="flex items-center gap-1.5 mb-2.5 -mt-1">
          <span className="text-[9px] font-mono text-slate-400 shrink-0">搜</span>
          <span className="text-[10px] text-slate-500 leading-snug line-clamp-1 border-l border-slate-200 pl-2">
            {queryText}
          </span>
        </div>
      )}
      <ul className="space-y-1.5">
        {shown.map((item, i) => (
          <SourceRow key={i} item={item as SearchSource} index={i} />
        ))}
      </ul>
      {hasMore && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="mt-2.5 text-[11px] font-medium text-indigo-600 hover:text-indigo-500 transition-colors"
        >
          {expanded ? '收起 △' : `展开剩余 ${list.length - collapseAfter} 条 ▽`}
        </button>
      )}
    </div>
  )
}
