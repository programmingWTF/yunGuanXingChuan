/**
 * 云观星传 - 二次确认弹窗（他山世界学术风）
 *
 * 用于「重新生成本阶段」「一键生成全部」等可能覆盖已确认产出物的危险操作：
 * 点击危险按钮后弹出确认，避免误触导致旧产出物被不可撤销地覆盖。
 *
 * 样式复用现有设计体系：白底 card（panel-beam 右上光晕）+ 胶囊圆角 +
 * btn-ghost（取消）+ btn-primary（确认，深蓝灰渐变危险操作）。
 */
import type { ReactNode } from 'react'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  description?: ReactNode
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
}

/** 危险操作二次确认弹窗（fixed 遮罩 + 居中卡片） */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmText = '确认',
  cancelText = '取消',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      {/* 半透明遮罩：点击遮罩关闭（等价于取消） */}
      <div
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
        onClick={onCancel}
      />
      {/* 居中卡片：复用他山 card 面板（白底+右上光晕+胶囊圆角+浅阴影） */}
      <div className="card relative w-full max-w-sm p-6 space-y-5 z-10">
        <div className="space-y-1.5">
          <h3 className="font-display text-lg font-semibold text-slate-900 tracking-tight">
            {title}
          </h3>
          {description && (
            <div className="text-[12px] text-slate-500 leading-relaxed">{description}</div>
          )}
        </div>
        <div className="flex items-center justify-end gap-2.5">
          <button type="button" onClick={onCancel} className="btn-ghost !px-5 !py-2 text-xs">
            {cancelText}
          </button>
          <button type="button" onClick={onConfirm} className="btn-primary !px-5 !py-2 text-xs">
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
