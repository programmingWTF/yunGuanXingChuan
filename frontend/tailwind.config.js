/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 深空基底
        abyss: { 950: '#040810', 900: '#060d1c', 800: '#0a1428', 700: '#0e1c38', 600: '#132548' },
        // 星辉青（主色）
        astro: { 300: '#7de8ff', 400: '#38d4f8', 500: '#0cb8e8', 600: '#0891c4', glow: 'rgba(12,184,232,0.35)' },
        // 星金（洞察）
        nova: { 300: '#ffe08a', 400: '#fbbf24', 500: '#f59e0b', glow: 'rgba(251,191,36,0.3)' },
        // 极光绿（验证通过）
        aurora: { 400: '#34d399', 500: '#10b981' },
        // 警报玫红
        flare: { 400: '#fb7185', 500: '#f43f5e' },
        // 旧名兼容
        'space-dark': '#0a1428',
        'star-blue': '#0cb8e8',
        'star-gold': '#fbbf24',
        'star-orange': '#ff6b35',
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Noto Sans SC"', 'sans-serif'],
        body: ['"Noto Sans SC"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 24px rgba(12,184,232,0.18), inset 0 1px 0 rgba(255,255,255,0.06)',
        'glow-gold': '0 0 24px rgba(251,191,36,0.15)',
        panel: '0 8px 32px rgba(0,0,0,0.45)',
      },
      animation: {
        'pulse-slow': 'pulse 3.5s cubic-bezier(0.4,0,0.6,1) infinite',
        'orbit': 'orbit 12s linear infinite',
        'scan': 'scan 3s ease-in-out infinite',
        'rise': 'rise 0.5s cubic-bezier(0.22,1,0.36,1) both',
        'shimmer': 'shimmer 2.4s linear infinite',
      },
      keyframes: {
        orbit: { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } },
        // 扫描线：top 百分比相对父容器高度，使光带扫满整个面板（translateY 百分比只相对自身高度，行程过短）
        scan: { '0%,100%': { top: '-30%' }, '50%': { top: '100%' } },
        rise: { '0%': { opacity: '0', transform: 'translateY(16px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
    },
  },
  plugins: [],
}
