import { useEffect, useState } from "react";

// ═══════════════ 国风山水动态背景（《代码2》设计稿原版移植）═══════════════
// 组成：远山轮廓×2 + 云纹×6 + 背景星星×30 + 上升粒子×15 + 星图网格 + 水墨晕染×3
// 依赖 index.css 中的国风动画 keyframes（cloudFloat / starTwinkle / ...）

// 生成随机位置的星星
interface Star {
  id: number;
  x: number;
  y: number;
  size: number;
  delay: number;
  duration: number;
}

// 生成云纹位置
interface Cloud {
  id: number;
  x: number;
  y: number;
  scale: number;
  delay: number;
  duration: number;
  type: "float" | "slow" | "reverse";
}

export function AnimatedBackground() {
  const [stars, setStars] = useState<Star[]>([]);
  const [clouds, setClouds] = useState<Cloud[]>([]);
  const [particles, setParticles] = useState<Star[]>([]);

  useEffect(() => {
    // 生成背景星星
    const generatedStars: Star[] = Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2 + 1,
      delay: Math.random() * 5,
      duration: Math.random() * 2 + 2,
    }));
    setStars(generatedStars);

    // 生成云纹
    const generatedClouds: Cloud[] = Array.from({ length: 6 }, (_, i) => ({
      id: i,
      x: Math.random() * 90 + 5,
      y: Math.random() * 80 + 10,
      scale: Math.random() * 0.5 + 0.8,
      delay: Math.random() * 3,
      duration: Math.random() * 4 + 8,
      type: ["float", "slow", "reverse"][Math.floor(Math.random() * 3)] as Cloud["type"],
    }));
    setClouds(generatedClouds);

    // 生成上升粒子
    const generatedParticles: Star[] = Array.from({ length: 15 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 2,
      delay: Math.random() * 10,
      duration: Math.random() * 5 + 10,
    }));
    setParticles(generatedParticles);
  }, []);

  const getCloudAnimationClass = (type: Cloud["type"]) => {
    switch (type) {
      case "slow":
        return "animate-cloud-float-slow";
      case "reverse":
        return "animate-cloud-float-reverse";
      default:
        return "animate-cloud-float";
    }
  };

  return (
    <div className="animated-background">
      {/* 远山轮廓 - 带轻微动画 */}
      <svg
        className="absolute bottom-0 left-0 w-full h-[40vh] opacity-[0.04] animate-cloud-float-slow"
        viewBox="0 0 1440 400"
        preserveAspectRatio="none"
      >
        <path
          d="M0,300 Q200,200 400,280 T800,250 T1200,300 T1440,280 L1440,400 L0,400 Z"
          fill="currentColor"
          className="text-slate-600"
        />
      </svg>

      {/* 第二层远山 */}
      <svg
        className="absolute bottom-0 left-0 w-full h-[30vh] opacity-[0.03] animate-cloud-float-reverse delay-3000"
        viewBox="0 0 1440 300"
        preserveAspectRatio="none"
      >
        <path
          d="M0,250 Q300,150 600,220 T1000,180 T1440,240 L1440,300 L0,300 Z"
          fill="currentColor"
          className="text-slate-500"
        />
      </svg>

      {/* 云纹装饰 */}
      {clouds.map((cloud) => (
        <div
          key={cloud.id}
          className={`cloud-pattern ${getCloudAnimationClass(cloud.type)}`}
          style={{
            left: `${cloud.x}%`,
            top: `${cloud.y}%`,
            transform: `scale(${cloud.scale})`,
            animationDelay: `${cloud.delay}s`,
          }}
        >
          <svg
            width="120"
            height="60"
            viewBox="0 0 120 60"
            fill="none"
          >
            <path
              d="M10,40 Q20,20 40,30 T70,25 T100,35 T110,45"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
              className="text-slate-400"
            />
            <path
              d="M15,45 Q30,30 50,38 T80,32 T105,42"
              stroke="currentColor"
              strokeWidth="1"
              fill="none"
              className="text-slate-300"
            />
          </svg>
        </div>
      ))}

      {/* 背景星星 */}
      {stars.map((star) => (
        <div
          key={star.id}
          className="star-decoration animate-star-twinkle"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            animationDelay: `${star.delay}s`,
            animationDuration: `${star.duration}s`,
          }}
        >
          <div
            className="w-full h-full rounded-full bg-amber-400"
            style={{
              boxShadow: `0 0 ${star.size * 2}px rgba(251, 191, 36, 0.5)`,
            }}
          />
        </div>
      ))}

      {/* 上升粒子 */}
      {particles.map((particle) => (
        <div
          key={`particle-${particle.id}`}
          className="floating-particle animate-particle-rise"
          style={{
            left: `${particle.x}%`,
            bottom: "-10px",
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            animationDelay: `${particle.delay}s`,
            animationDuration: `${particle.duration}s`,
          }}
        />
      ))}

      {/* 星图网格背景 */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.3) 0%, transparent 50%),
            radial-gradient(circle at 80% 70%, rgba(99, 102, 241, 0.2) 0%, transparent 40%),
            radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.1) 0%, transparent 60%)
          `,
        }}
      />

      {/* 水墨晕染效果 */}
      <div
        className="absolute top-[20%] left-[10%] w-64 h-64 rounded-full animate-ink-spread delay-1000"
        style={{
          background: "radial-gradient(circle, rgba(99, 102, 241, 0.08) 0%, transparent 70%)",
        }}
      />
      <div
        className="absolute top-[60%] right-[15%] w-48 h-48 rounded-full animate-ink-spread delay-3000"
        style={{
          background: "radial-gradient(circle, rgba(59, 130, 246, 0.06) 0%, transparent 70%)",
        }}
      />
      <div
        className="absolute bottom-[20%] left-[30%] w-56 h-56 rounded-full animate-ink-spread delay-5000"
        style={{
          background: "radial-gradient(circle, rgba(139, 92, 246, 0.05) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}

// 北斗七星组件
export function BigDipperConstellation() {
  const stars = [
    { cx: 10, cy: 20, label: "天枢" },
    { cx: 25, cy: 35, label: "天璇" },
    { cx: 40, cy: 30, label: "天玑" },
    { cx: 55, cy: 45, label: "天权" },
    { cx: 70, cy: 50, label: "玉衡" },
    { cx: 85, cy: 65, label: "开阳" },
    { cx: 95, cy: 80, label: "摇光" },
  ];

  return (
    <div className="absolute top-[15%] left-[8%] w-32 h-32 animate-cloud-float-slow">
      <svg className="w-full h-full" viewBox="0 0 100 100">
        {/* 连线 */}
        <path
          d="M10,20 L25,35 L40,30 L55,45 L70,50 L85,65 L95,80"
          stroke="currentColor"
          strokeWidth="0.5"
          fill="none"
          className="text-amber-400/50 animate-constellation-shine"
        />
        {/* 星星 */}
        {stars.map((star, i) => (
          <g key={i}>
            <circle
              cx={star.cx}
              cy={star.cy}
              r="2"
              fill="currentColor"
              className={`text-amber-400 animate-star-pulse delay-${(i + 1) * 200}`}
            />
            {/* 光晕 */}
            <circle
              cx={star.cx}
              cy={star.cy}
              r="4"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.3"
              className="text-amber-400/30 animate-star-twinkle"
              style={{ animationDelay: `${i * 0.3}s` }}
            />
          </g>
        ))}
      </svg>
      {/* 标签 */}
      <div className="absolute top-[18%] left-[5%] text-[10px] text-slate-500/60 writing-vertical animate-star-twinkle">
        天枢
      </div>
      <div className="absolute top-[28%] left-[18%] text-[10px] text-slate-500/60 animate-star-twinkle delay-500">
        天璇
      </div>
    </div>
  );
}

// 北极星组件
export function Polaris() {
  return (
    <div className="absolute top-[12%] right-[15%] animate-cloud-float">
      <svg className="w-16 h-16 animate-star-rotate" viewBox="0 0 50 50">
        {/* 光芒 */}
        {[0, 45, 90, 135].map((deg) => (
          <line
            key={deg}
            x1="25"
            y1="25"
            x2={25 + 20 * Math.cos((deg * Math.PI) / 180)}
            y2={25 + 20 * Math.sin((deg * Math.PI) / 180)}
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-blue-400/40"
          />
        ))}
        {/* 中心星 */}
        <circle
          cx="25"
          cy="25"
          r="3"
          fill="currentColor"
          className="text-blue-400 animate-star-pulse"
        />
        {/* 光晕 */}
        <circle
          cx="25"
          cy="25"
          r="6"
          fill="none"
          stroke="currentColor"
          strokeWidth="0.5"
          className="text-blue-400/20 animate-star-twinkle"
        />
      </svg>
      <span className="absolute -bottom-4 left-1/2 -translate-x-1/2 text-[10px] text-slate-500 whitespace-nowrap animate-star-twinkle">
        北极
      </span>
    </div>
  );
}

// 装饰性云纹组件
export function DecorativeClouds() {
  return (
    <>
      {/* 左上角云纹 */}
      <div className="absolute top-[5%] left-[2%] opacity-10 animate-cloud-float-slow">
        <svg width="80" height="40" viewBox="0 0 80 40">
          <path
            d="M5,30 Q15,15 30,22 T55,18 T75,28"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            className="text-slate-400"
          />
        </svg>
      </div>

      {/* 右上角云纹 */}
      <div className="absolute top-[8%] right-[5%] opacity-10 animate-cloud-float-reverse delay-2000">
        <svg width="100" height="50" viewBox="0 0 100 50">
          <path
            d="M10,35 Q25,20 45,28 T75,22 T95,32"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
            className="text-slate-400"
          />
        </svg>
      </div>

      {/* 底部云纹 */}
      <div className="absolute bottom-[10%] left-[20%] opacity-[0.08] animate-cloud-float delay-3000">
        <svg width="120" height="60" viewBox="0 0 120 60">
          <path
            d="M10,45 Q30,25 55,35 T90,28 T115,40"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            className="text-slate-400"
          />
        </svg>
      </div>

      {/* 右下角云纹 */}
      <div className="absolute bottom-[15%] right-[10%] opacity-10 animate-cloud-float-slow delay-4000">
        <svg width="90" height="45" viewBox="0 0 90 45">
          <path
            d="M8,32 Q20,18 38,25 T65,20 T85,30"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            className="text-slate-400"
          />
        </svg>
      </div>
    </>
  );
}
