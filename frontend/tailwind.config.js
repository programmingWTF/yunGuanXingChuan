/** @type {import('tailwindcss').Config} */
// ═══════════════ 云观星传 V3.0 设计系统 — 他山世界学术风 ═══════════════
// 依据《他山世界-设计风格调研.md》：宋体衬线 + 大留白 + 低饱和青蓝 + 浅色主调
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── 品牌蓝（交互态 / 主 CTA 配套）──
        brand: {
          100: '#DBEAFE', 200: '#BFDBFE', 300: '#93C5FD',
          400: '#60A5FA', 500: '#3B82F6', 600: '#2563EB', 700: '#1D4ED8', 800: '#1E40AF',
        },
        // ── 强调天蓝（激活态 / 链接 / 雷达装饰）──
        accent: {
          100: '#E0F2FE', 200: '#BAE6FD', 300: '#7DD3FC',
          400: '#38BDF8', 500: '#0EA5E9', 600: '#0284C7', 700: '#0369A1',
        },
        // ── 青绿（数据可视化 / 装饰光晕）──
        teal: {
          100: '#CCFBF1', 200: '#99F6E4', 300: '#5EEAD4',
          400: '#2DD4BF', 500: '#14B8A6', 600: '#0D9488',
        },
        // ── 琥珀橙（暖色点缀 / 灵感共创）──
        amber: {
          100: '#FEF3C7', 200: '#FDE68A', 300: '#FCD34D',
          400: '#FBBF24', 500: '#F59E0B', 600: '#D97706',
        },
        // ── 状态色（语义）──
        success: { 400: '#34D399', 500: '#10B981', 600: '#059669' },
        danger: { 400: '#F87171', 500: '#EF4444', 600: '#DC2626' },
        // ── 页脚深海军蓝（全站唯一大面积深色）──
        footer: '#0E2E4F',
        // 兼容旧深色主题的少量遗留引用（无实际使用）
        abyss: { 900: '#0F172A', 800: '#1E293B', 700: '#334155' },
      },
      fontFamily: {
        // 中文正文/标题：宋体衬线（他山风核心）
        serif: ['"Noto Serif SC"', 'Georgia', 'STSong', 'SimSun', 'serif'],
        display: ['"Noto Serif SC"', 'Georgia', 'STSong', 'SimSun', 'serif'],
        body: ['"Noto Serif SC"', 'Georgia', 'STSong', 'SimSun', 'serif'],
        // 无衬线（英文小标签 / 少量场景）
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Helvetica Neue', 'Arial', 'sans-serif'],
        // 等宽（代码 / URL / 数字）
        mono: ['"MonaspaceRadonFrozen"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        // 他山标志性大圆角体系
        card: '1.75rem',        // 28px
        cardlg: '2rem',         // 32px
        mid: '1.25rem',         // 20px
        btn: '1rem',            // 16px
      },
      boxShadow: {
        // 极克制的浅阴影（他山：卡片几乎不用阴影）
        card: '0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04)',
        cardh: '0 10px 15px rgba(0,0,0,.08), 0 4px 6px rgba(0,0,0,.05)',
        btn: '0 1px 2px rgba(0,0,0,.08)',
      },
      letterSpacing: {
        // 他山字距体系
        tag: '0.22em',   // 英文大写小标签
        tagwide: '0.28em',
        tightitle: '-0.04em', // 大标题收紧
        ctag: '0.08em',  // 中文标签
      },
      animation: {
        'rise': 'rise .45s cubic-bezier(.22,1,.36,1) both',
        'breathe': 'breathe 3.2s ease-in-out infinite',
        'float': 'floatDrift 5.5s ease-in-out infinite',
        'sweep': 'cardSweep 2.8s ease-in-out infinite',
        'shimmer': 'shimmer 2.4s linear infinite',
        'radar': 'radarSpin 10s linear infinite',
        'flow': 'flowDash 1.2s linear infinite',
        'scanline': 'scanline 3s ease-in-out infinite',
      },
      keyframes: {
        rise: { '0%': { opacity: '0', transform: 'translateY(18px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        breathe: { '0%,100%': { opacity: '.45', transform: 'scale(1)' }, '50%': { opacity: '.9', transform: 'scale(1.05)' } },
        floatDrift: { '0%,100%': { transform: 'translateY(0) translateX(0)' }, '50%': { transform: 'translateY(-12px) translateX(6px)' } },
        // 卡片扫光：105deg 半透明白斜条从左侧扫过（他山 cardSpecularSweep）
        cardSweep: {
          '0%': { transform: 'translateX(-120%) skewX(-18deg)' },
          '60%,100%': { transform: 'translateX(220%) skewX(-18deg)' },
        },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        radarSpin: { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } },
        flowDash: { to: { strokeDashoffset: '-24' } },
        scanline: { '0%,100%': { top: '-30%' }, '50%': { top: '100%' } },
      },
    },
  },
  plugins: [],
}
