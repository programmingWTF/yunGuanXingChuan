/**
 * 深空观测站背景
 * Canvas 星空（闪烁 + 流星）+ CSS 星云层叠
 */
import { useEffect, useRef } from 'react'

interface Star { x: number; y: number; r: number; base: number; phase: number; speed: number }
interface Meteor { x: number; y: number; vx: number; vy: number; life: number; maxLife: number }

export default function StarfieldBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let w = 0, h = 0, raf = 0
    let stars: Star[] = []
    let meteors: Meteor[] = []
    let lastMeteor = 0

    const resize = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
      const count = Math.min(260, Math.floor((w * h) / 6000))
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.3 + 0.3,
        base: Math.random() * 0.5 + 0.25,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.8 + 0.3,
      }))
    }

    const spawnMeteor = (t: number) => {
      meteors.push({
        x: Math.random() * w * 0.8 + w * 0.15,
        y: -20,
        vx: -(Math.random() * 3 + 2.5),
        vy: Math.random() * 4 + 5,
        life: 0,
        maxLife: 70 + Math.random() * 40,
      })
      lastMeteor = t
    }

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h)
      const time = t / 1000

      // 星星
      for (const s of stars) {
        const tw = s.base + Math.sin(time * s.speed + s.phase) * 0.3
        const alpha = Math.max(0.05, Math.min(1, tw))
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(200, 230, 255, ${alpha})`
        ctx.fill()
        // 亮星十字辉光
        if (s.r > 1.2) {
          ctx.strokeStyle = `rgba(160, 220, 255, ${alpha * 0.25})`
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(s.x - s.r * 3, s.y); ctx.lineTo(s.x + s.r * 3, s.y)
          ctx.moveTo(s.x, s.y - s.r * 3); ctx.lineTo(s.x, s.y + s.r * 3)
          ctx.stroke()
        }
      }

      // 流星
      if (t - lastMeteor > 4000 + Math.random() * 6000) spawnMeteor(t)
      meteors = meteors.filter(m => m.life < m.maxLife)
      for (const m of meteors) {
        m.x += m.vx; m.y += m.vy; m.life++
        const fade = 1 - m.life / m.maxLife
        const grad = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 12, m.y - m.vy * 12)
        grad.addColorStop(0, `rgba(180, 235, 255, ${0.85 * fade})`)
        grad.addColorStop(1, 'rgba(180, 235, 255, 0)')
        ctx.strokeStyle = grad
        ctx.lineWidth = 1.4
        ctx.beginPath()
        ctx.moveTo(m.x, m.y)
        ctx.lineTo(m.x - m.vx * 12, m.y - m.vy * 12)
        ctx.stroke()
      }

      raf = requestAnimationFrame(draw)
    }

    resize()
    window.addEventListener('resize', resize)
    raf = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <div className="fixed inset-0 z-0 pointer-events-none" aria-hidden>
      {/* 深空基底渐变 */}
      <div className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse 120% 90% at 70% -10%, #0e1c38 0%, #060d1c 45%, #040810 100%)' }} />
      {/* 星云层：青色 */}
      <div className="absolute inset-0 opacity-40 animate-breathe"
        style={{ background: 'radial-gradient(ellipse 55% 40% at 18% 22%, rgba(12,184,232,0.10) 0%, transparent 70%)' }} />
      {/* 星云层：金色（右下） */}
      <div className="absolute inset-0 opacity-30"
        style={{ background: 'radial-gradient(ellipse 45% 35% at 85% 80%, rgba(251,191,36,0.06) 0%, transparent 70%)' }} />
      {/* 星云层：紫色（左上远端） */}
      <div className="absolute inset-0 opacity-25"
        style={{ background: 'radial-gradient(ellipse 40% 30% at 8% 85%, rgba(99,102,241,0.07) 0%, transparent 70%)' }} />
      {/* 地平线辉光 */}
      <div className="absolute bottom-0 left-0 right-0 h-48"
        style={{ background: 'linear-gradient(to top, rgba(12,184,232,0.05), transparent)' }} />
      {/* Canvas 星空 */}
      <canvas ref={canvasRef} className="absolute inset-0" />
      {/* 网格经纬线（观测站质感） */}
      <div className="absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(56,212,248,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(56,212,248,0.6) 1px, transparent 1px)',
          backgroundSize: '72px 72px',
        }} />
    </div>
  )
}
