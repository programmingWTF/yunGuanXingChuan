/**
 * 云观星传 — 首页 Hero（对齐效果图：国风星象 × 水墨山水 × AI 科研平台）
 *
 * 结构（自上而下）：
 *   ✣ AI驱动的科学传播分析平台（eyebrow 胶囊标签）
 *   云观星传 / 科学话题传播分析系统（深靛蓝大标题）
 *   副标题（基于多智能体架构……）
 *   [开始分析] [了解更多]（胶囊 CTA）
 *   四张 KPI 卡（处理速度 / 准确率 / 并发数 / 吞吐量）
 *
 * 背景：cloud-bg.jpg 水墨山水星象图（低透明度 + 宣纸罩层），
 * 动态星象系统（AnimatedBackground）由 App 全局承载。
 */
import { Timer, Target, Network, BarChart3, Play, Info, Sparkles } from 'lucide-react'

const KPIS = [
  { icon: Timer, value: '2.4s/任务', label: '处理速度', delta: '↑ 12%' },
  { icon: Target, value: '96.8%', label: '准确率', delta: '↑ 3.2%' },
  { icon: Network, value: '12任务', label: '并发数', delta: '↑ 50%' },
  { icon: BarChart3, value: '847任务/天', label: '吞吐量', delta: '↑ 23%' },
]

export default function HomeHero() {
  return (
    <section className="relative overflow-hidden">
      {/* 水墨山水星象背景（效果图背景层） */}
      <div className="absolute inset-0 z-0">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url('/cloud-bg.jpg')" }}
        />
        {/* 宣纸罩层：让背景融入页面、保证文字可读 */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#f8f9fa]/90 via-[#f8f9fa]/75 to-[#f8f9fa]/95" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#f8f9fa]" />
      </div>

      <div className="relative z-10 w-full px-4 sm:px-10 lg:px-16 pt-10 pb-16 sm:pt-14 sm:pb-20">
        {/* Eyebrow：产品定位标签 */}
        <div className="flex justify-center">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#eef2f7]/80 border border-slate-200/60 text-xs sm:text-[13px] text-[#5E7392] tracking-wide shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-[#C8B37A]" strokeWidth={1.5} />
            AI驱动的科学传播分析平台
          </span>
        </div>

        {/* 主标题 */}
        <div className="mt-8 sm:mt-10 text-center">
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-[#17294F] tracking-[0.12em] leading-tight">
            云观星传
          </h1>
          <p className="mt-3 sm:mt-4 text-2xl sm:text-3xl lg:text-4xl font-semibold text-[#1C315B] tracking-wider">
            科学话题传播分析系统
          </p>
        </div>

        {/* 副标题 */}
        <p className="mt-6 sm:mt-8 mx-auto max-w-2xl text-center text-sm sm:text-base text-[#5E7392] leading-relaxed">
          基于多智能体架构，融合科学事实提取、语境分析与传播策略生成，
          为科学话题提供全方位的传播洞察与决策支持
        </p>

        {/* CTA 按钮（效果图：胶囊按钮） */}
        <div className="mt-8 sm:mt-10 flex items-center justify-center gap-4 flex-wrap">
          <a
            href="#workspace"
            className="inline-flex items-center gap-2.5 px-8 py-3.5 rounded-full text-white font-medium shadow-lg shadow-indigo-200/60 transition-all hover:brightness-110 hover:shadow-xl hover:shadow-indigo-200/70 active:scale-[0.98]"
            style={{ background: 'linear-gradient(to right, #4f46e5, #1d4ed8)' }}
          >
            <Play className="w-4 h-4" strokeWidth={2} />
            开始分析
          </a>
          <a
            href="#footer"
            className="inline-flex items-center gap-2.5 px-8 py-3.5 rounded-full bg-white/70 backdrop-blur-sm border border-[#B6C9DD] text-[#1C315B] font-medium transition-all hover:border-[#8fa8c4] hover:bg-white active:scale-[0.98]"
          >
            <Info className="w-4 h-4" strokeWidth={1.75} />
            了解更多
          </a>
        </div>

        {/* KPI 指标卡（效果图：半透明白、大圆角、轻阴影、金色细线图标） */}
        <div className="mt-12 sm:mt-16 grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
          {KPIS.map((kpi) => (
            <div
              key={kpi.label}
              className="group rounded-[1.5rem] bg-white/70 backdrop-blur-md border border-slate-200/60 p-5 sm:p-6 shadow-[0_8px_30px_rgba(40,60,100,0.06)] transition-all hover:-translate-y-0.5 hover:shadow-[0_16px_40px_rgba(40,60,100,0.10)]"
            >
              <div className="w-9 h-9 rounded-xl bg-[#faf6ec] border border-[#E4D9B8]/70 flex items-center justify-center">
                <kpi.icon className="w-[18px] h-[18px] text-[#C8B37A]" strokeWidth={1.5} />
              </div>
              <div className="mt-3.5 text-xl sm:text-2xl font-bold text-[#17294F] tracking-tight">
                {kpi.value}
              </div>
              <div className="mt-1 text-xs sm:text-sm text-slate-500">{kpi.label}</div>
              <div className="mt-2.5 text-xs font-medium text-[#4DA77A]">{kpi.delta}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}