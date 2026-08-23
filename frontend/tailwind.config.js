/** @type {import('tailwindcss').Config} */
// ═══════════════ 云观星传 — 国风山水主题（与《代码2》设计稿一致）═══════════════
// 淡雅水墨配色 / 靛蓝主色 / 无衬线字体栈 / 国风动效
// 设计令牌定义于 src/index.css :root / .dark，此处仅做 Tailwind v3 映射
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── shadcn/ui 设计令牌映射（值来自 index.css CSS 变量，与设计稿一致）──
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: {
          DEFAULT: 'var(--primary)',
          foreground: 'var(--primary-foreground)',
        },
        secondary: {
          DEFAULT: 'var(--secondary)',
          foreground: 'var(--secondary-foreground)',
        },
        destructive: {
          DEFAULT: 'var(--destructive)',
          foreground: 'var(--destructive-foreground)',
        },
        muted: {
          DEFAULT: 'var(--muted)',
          foreground: 'var(--muted-foreground)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          foreground: 'var(--accent-foreground)',
        },
        popover: {
          DEFAULT: 'var(--popover)',
          foreground: 'var(--popover-foreground)',
        },
        card: {
          DEFAULT: 'var(--card)',
          foreground: 'var(--card-foreground)',
        },
        chart: {
          '1': 'var(--chart-1)',
          '2': 'var(--chart-2)',
          '3': 'var(--chart-3)',
          '4': 'var(--chart-4)',
          '5': 'var(--chart-5)',
        },
        sidebar: {
          DEFAULT: 'var(--sidebar)',
          foreground: 'var(--sidebar-foreground)',
          primary: 'var(--sidebar-primary)',
          'primary-foreground': 'var(--sidebar-primary-foreground)',
          accent: 'var(--sidebar-accent)',
          'accent-foreground': 'var(--sidebar-accent-foreground)',
          border: 'var(--sidebar-border)',
          ring: 'var(--sidebar-ring)',
        },
        // ── 旧主题遗留引用（迁移期保留，逐步清理）──
        footer: '#0f172a',
      },
      fontFamily: {
        // 国风山水主字体栈（设计稿原样）
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans SC"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        // 旧衬线类名 → 统一映射到无衬线栈（页面无需逐个改）
        serif: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans SC"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans SC"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        body: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans SC"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        // 设计稿 --radius: 0.625rem 体系
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        btn: 'var(--radius)',
      },
      animation: {
        // ── 国风动画（keyframes 在 index.css）──
        'cloud-float': 'cloudFloat 8s ease-in-out infinite',
        'cloud-float-slow': 'cloudFloatSlow 12s ease-in-out infinite',
        'cloud-float-reverse': 'cloudFloatReverse 10s ease-in-out infinite',
        'star-twinkle': 'starTwinkle 3s ease-in-out infinite',
        'star-pulse': 'starPulse 2s ease-in-out infinite',
        'star-rotate': 'starRotate 20s linear infinite',
        'constellation-shine': 'constellationShine 4s ease-in-out infinite',
        'particle-rise': 'particleRise 15s linear infinite',
        'ink-spread': 'inkSpread 8s ease-out infinite',
        // ── 旧主题遗留动画（少量引用，迁移期映射到国风动画）──
        'breathe': 'starTwinkle 3.2s ease-in-out infinite',
        'float': 'cloudFloatSlow 5.5s ease-in-out infinite',
        // ── shadcn/ui 组件所需动画 ──
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
      keyframes: {
        // ── shadcn/ui keyframes ──
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
