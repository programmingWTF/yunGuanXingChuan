/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'space-dark': '#0A1628',
        'space-purple': '#1A0A3E',
        'star-blue': '#00D4FF',
        'star-gold': '#FFD700',
        'star-orange': '#FF6B35',
      },
    },
  },
  plugins: [],
}
