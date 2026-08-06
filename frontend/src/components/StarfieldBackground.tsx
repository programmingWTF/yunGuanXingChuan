/**
 * 云观星传 V3.0 — 浅色学术装饰背景（他山世界风）
 * 取代 V2 的深空星空：低透明径向光晕（青绿/蓝/琥珀）+ 漂浮粒子，
 * 全部透明度 ≤0.18，只制造"质感"不抢内容（他山调研文档 · 背景装饰技法）。
 */
export default function StarfieldBackground() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden" aria-hidden="true">
      {/* 光晕 1：左上青绿 */}
      <div className="absolute -top-40 -left-40 w-[520px] h-[520px] rounded-full animate-breathe"
        style={{ background: 'radial-gradient(circle, rgba(64,174,176,.10), transparent 62%)' }} />
      {/* 光晕 2：右上蓝 */}
      <div className="absolute -top-24 right-[-10%] w-[460px] h-[460px] rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(14,165,233,.08), transparent 60%)', animation: 'breathe 4.5s ease-in-out infinite' }} />
      {/* 光晕 3：中部暖琥珀（弱） */}
      <div className="absolute top-[38%] left-[42%] w-[380px] h-[380px] rounded-full animate-breathe"
        style={{ background: 'radial-gradient(circle, rgba(243,156,50,.06), transparent 60%)', animationDelay: '1.2s' }} />
      {/* 漂浮粒子（他山 floatDrift 双向往复） */}
      {[
        { left: '12%', top: '22%', s: 5, d: '0s' },
        { left: '78%', top: '30%', s: 7, d: '-1.2s' },
        { left: '24%', top: '68%', s: 6, d: '-2.1s' },
        { left: '62%', top: '74%', s: 4, d: '-0.6s' },
        { left: '88%', top: '58%', s: 8, d: '-1.8s' },
        { left: '6%', top: '52%', s: 4, d: '-2.6s' },
      ].map((p, i) => (
        <span key={i} className="absolute rounded-full animate-float"
          style={{
            left: p.left, top: p.top, width: p.s, height: p.s,
            background: 'rgba(148,163,184,.35)',
            animationDelay: p.d,
          }} />
      ))}
    </div>
  )
}
