/**
 * 云观星传 V2.0 — 跨文化傳播對照
 * 術語對照 · 隱喻對照 · 表達建議 · 適用媒體語境標注
 */

interface TermEntry {
    zh: string
    en: string
    context: string
    contextType: 'western' | 'global' | 'domestic' | 'neutral'
}

interface MetaphorEntry {
    zh: string
    en: string
    zhNote: string
    enNote: string
    context: string
    contextType: 'western' | 'global' | 'domestic' | 'neutral'
}

interface ExpressionEntry {
    notRecommended: string
    recommended: string
    reason: string
    context: string
    contextType: 'western' | 'global' | 'domestic' | 'neutral'
}

const termData: TermEntry[] = [
    { zh: '天宫', en: 'Tiangong Space Station', context: '欧美主流媒体', contextType: 'western' },
    { zh: '神舟', en: 'Shenzhou Spacecraft', context: '国际航天报道', contextType: 'global' },
    { zh: '嫦娥', en: 'Chang\'e Lunar Program', context: '欧美科技媒体', contextType: 'western' },
    { zh: '北斗', en: 'BeiDou Navigation System', context: '全球行业报道', contextType: 'global' },
    { zh: '长征火箭', en: 'Long March Rocket', context: '国际通讯社', contextType: 'global' },
    { zh: '空间站', en: 'Space Station / Orbital Laboratory', context: '欧美科普媒体', contextType: 'western' },
    { zh: '载人航天', en: 'Human Spaceflight', context: '全球通用', contextType: 'neutral' },
    { zh: '深空探测', en: 'Deep Space Exploration', context: '全球通用', contextType: 'neutral' },
    { zh: '航天员', en: 'Taikonaut / Astronaut', context: '欧美媒体偏好 Astronaut', contextType: 'western' },
    { zh: '太空实验室', en: 'Space Laboratory', context: '国际合作语境', contextType: 'global' },
]

const metaphorData: MetaphorEntry[] = [
    {
        zh: '逐梦星辰', en: 'Exploring the Cosmos',
        zhNote: '诗意化表达，强调梦想与浪漫', enNote: 'Neutral, fact-oriented phrasing',
        context: '欧美媒体', contextType: 'western',
    },
    {
        zh: '飞天', en: 'Human Spaceflight Achievement',
        zhNote: '文化典故，敦煌意象', enNote: 'Direct, technical framing',
        context: '欧美科技媒体', contextType: 'western',
    },
    {
        zh: '星辰大海', en: 'The Final Frontier / Space Exploration',
        zhNote: '宏大叙事，集体愿景', enNote: 'Individual adventure framing (Star Trek trope)',
        context: '欧美流行文化', contextType: 'western',
    },
    {
        zh: '揽月', en: 'Lunar Exploration Milestone',
        zhNote: '诗意化，源自毛泽东诗词', enNote: 'Achievement-oriented, milestone framing',
        context: '国际通讯社', contextType: 'global',
    },
    {
        zh: '九天揽月', en: 'Reaching the Moon / Lunar Ambition',
        zhNote: '古典文学意象', enNote: 'Ambition/goal-oriented, avoids poetic overload',
        context: '智库/政策分析', contextType: 'global',
    },
    {
        zh: '太空长征', en: 'Space Journey / Extended Mission',
        zhNote: '历史隐喻，革命叙事', enNote: 'Neutral mission framing, avoids political echo',
        context: '欧美媒体', contextType: 'western',
    },
]

const expressionData: ExpressionEntry[] = [
    {
        notRecommended: '民族复兴', recommended: 'Global Scientific Cooperation',
        reason: '"民族复兴"在欧美语境易被解读为民族主义叙事，触发意识形态警觉；"Global Scientific Cooperation"强调合作共享，契合国际传播目标',
        context: '欧美主流媒体', contextType: 'western',
    },
    {
        notRecommended: '大国重器', recommended: 'Landmark Engineering Achievement',
        reason: '"大国重器"暗示地缘竞争与军事化；"Landmark Engineering Achievement"聚焦技术成就本身',
        context: '欧美科技媒体', contextType: 'western',
    },
    {
        notRecommended: '自主创新', recommended: 'Independent R&D / Indigenous Innovation',
        reason: '"自主创新"在西方可被解读为技术脱钩信号；"Indigenous Innovation"更中性，强调研发能力',
        context: '国际行业报道', contextType: 'global',
    },
    {
        notRecommended: '弯道超车', recommended: 'Rapid Technological Advancement',
        reason: '"弯道超车"暗示不公平竞争或捷径；"Rapid Technological Advancement"为中性进步叙事',
        context: '欧美商业媒体', contextType: 'western',
    },
    {
        notRecommended: '太空竞赛', recommended: 'Collaborative Space Endeavor',
        reason: '"太空竞赛"激活冷战框架，强化零和博弈叙事；"Collaborative Space Endeavor"转向合作框架',
        context: '欧美主流媒体', contextType: 'western',
    },
    {
        notRecommended: '自力更生', recommended: 'Self-Reliant Development',
        reason: '"自力更生"在西方语境关联孤立主义；"Self-Reliant Development"更中性，强调发展路径',
        context: '智库/政策分析', contextType: 'global',
    },
]

const contextBadge: Record<string, { label: string; color: string }> = {
    western: { label: '欧美媒体', color: 'text-astro-300 bg-astro-500/10 border-astro-500/25' },
    global: { label: '国际通用', color: 'text-nova-400 bg-nova-400/10 border-nova-400/25' },
    domestic: { label: '国内传播', color: 'text-aurora-400 bg-aurora-400/10 border-aurora-400/25' },
    neutral: { label: '通用', color: 'text-slate-300 bg-slate-500/10 border-slate-500/25' },
}

function ContextTag({ type }: { type: string }) {
    const cfg = contextBadge[type] || contextBadge.neutral
    return (
        <span className={`px-2 py-0.5 rounded text-[10px] font-mono tracking-wide border whitespace-nowrap ${cfg.color}`}>
            {cfg.label}
        </span>
    )
}

function BilingualRow({ zh, en, children }: { zh: string; en: string; children?: React.ReactNode }) {
    return (
        <div className="grid grid-cols-2 gap-0 border-b border-white/[0.04] last:border-b-0">
            <div className="px-5 py-3.5 border-r border-white/[0.04]">
                <span className="text-sm text-slate-200 leading-relaxed">{zh}</span>
            </div>
            <div className="px-5 py-3.5 flex items-center justify-between gap-3">
                <span className="text-sm text-slate-200 leading-relaxed">{en}</span>
                {children}
            </div>
        </div>
    )
}

function SectionHeader({ zh, en }: { zh: string; en: string }) {
    return (
        <div className="grid grid-cols-2 gap-0 border-b border-astro-500/20">
            <div className="px-5 py-2.5 bg-astro-500/5">
                <span className="text-[11px] font-medium text-astro-300 tracking-wide">{zh}</span>
            </div>
            <div className="px-5 py-2.5 bg-astro-500/5">
                <span className="text-[11px] font-medium text-astro-300 tracking-wide">{en}</span>
            </div>
        </div>
    )
}

function CrossCultural() {
    return (
        <div className="space-y-8">
            <div>
                <p className="sec-label mb-1">Cross-Cultural Communication</p>
                <h2 className="font-display text-2xl font-bold text-white">跨文化传播对照</h2>
                <p className="text-sm text-slate-500 mt-2 max-w-2xl">
                    基于传播学差异化能力，为航天叙事提供中英术语、隐喻与表达策略的系统性对照，标注适用媒体语境，避免跨文化误读与框架冲突。
                </p>
            </div>

            {/* ═══ 术语对照 ═══ */}
            <div className="panel overflow-hidden">
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-astro-500/10 border border-astro-500/20 flex items-center justify-center text-astro-400 text-sm">T</span>
                    <div>
                        <h3 className="text-base font-bold text-white">术语对照</h3>
                        <p className="text-[11px] text-slate-500 font-mono tracking-wide">Terminology Mapping</p>
                    </div>
                </div>
                <SectionHeader zh="中文术语" en="English Terminology" />
                {termData.map((item, i) => (
                    <BilingualRow key={i} zh={item.zh} en={item.en}>
                        <ContextTag type={item.contextType} />
                    </BilingualRow>
                ))}
            </div>

            {/* ═══ 隐喻对照 ═══ */}
            <div className="panel overflow-hidden">
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-nova-400/10 border border-nova-400/20 flex items-center justify-center text-nova-400 text-sm">M</span>
                    <div>
                        <h3 className="text-base font-bold text-white">隐喻对照</h3>
                        <p className="text-[11px] text-slate-500 font-mono tracking-wide">Metaphor Mapping</p>
                    </div>
                </div>
                <SectionHeader zh="中文隐喻 / 语义说明" en="English Metaphor / Semantic Note" />
                {metaphorData.map((item, i) => (
                    <div key={i} className="grid grid-cols-2 gap-0 border-b border-white/[0.04] last:border-b-0">
                        <div className="px-5 py-3.5 border-r border-white/[0.04] space-y-1">
                            <span className="text-sm text-slate-200 leading-relaxed">{item.zh}</span>
                            <p className="text-[11px] text-slate-500 leading-relaxed">{item.zhNote}</p>
                        </div>
                        <div className="px-5 py-3.5 space-y-1">
                            <div className="flex items-center justify-between gap-3">
                                <span className="text-sm text-slate-200 leading-relaxed">{item.en}</span>
                                <ContextTag type={item.contextType} />
                            </div>
                            <p className="text-[11px] text-slate-500 leading-relaxed">{item.enNote}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* ═══ 表达建议 ═══ */}
            <div className="panel overflow-hidden">
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-3">
                    <span className="w-8 h-8 rounded-lg bg-flare-400/10 border border-flare-400/20 flex items-center justify-center text-flare-400 text-sm">E</span>
                    <div>
                        <h3 className="text-base font-bold text-white">表达建议</h3>
                        <p className="text-[11px] text-slate-500 font-mono tracking-wide">Expression Recommendations</p>
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-0 border-b border-astro-500/20">
                    <div className="px-5 py-2.5 bg-flare-400/5">
                        <span className="text-[11px] font-medium text-flare-400 tracking-wide">不建议表达 ✗</span>
                    </div>
                    <div className="px-5 py-2.5 bg-aurora-400/5">
                        <span className="text-[11px] font-medium text-aurora-400 tracking-wide">建议表达 ✓</span>
                    </div>
                </div>
                {expressionData.map((item, i) => (
                    <div key={i} className="grid grid-cols-2 gap-0 border-b border-white/[0.04] last:border-b-0">
                        <div className="px-5 py-4 border-r border-white/[0.04] space-y-2">
                            <span className="text-sm text-flare-400 leading-relaxed line-through decoration-flare-400/40">{item.notRecommended}</span>
                            <p className="text-[11px] text-slate-500 leading-relaxed">{item.reason}</p>
                        </div>
                        <div className="px-5 py-4 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <span className="text-sm text-aurora-400 leading-relaxed font-medium">{item.recommended}</span>
                                <ContextTag type={item.contextType} />
                            </div>
                            <p className="text-[11px] text-slate-500 leading-relaxed">{item.context}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* ═══ 媒体语境图例 ═══ */}
            <div className="panel px-6 py-5">
                <p className="sec-label mb-3">Media Context Legend</p>
                <div className="flex flex-wrap gap-4">
                    {Object.entries(contextBadge).map(([key, val]) => (
                        <div key={key} className="flex items-center gap-2">
                            <span className={`px-2.5 py-1 rounded text-[10px] font-mono tracking-wide border ${val.color}`}>
                                {val.label}
                            </span>
                            <span className="text-[11px] text-slate-500">
                                {key === 'western' && '适合欧美主流/科技媒体语境'}
                                {key === 'global' && '适合国际通讯社/行业报道语境'}
                                {key === 'domestic' && '适合国内传播语境'}
                                {key === 'neutral' && '跨文化通用，无特殊语境限制'}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default CrossCultural