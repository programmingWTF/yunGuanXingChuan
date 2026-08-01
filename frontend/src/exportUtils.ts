/**
 * 云观星传 V2.0 — 多格式导出工具
 * PDF / Word / Markdown / HTML / JSON / 知识图谱 PNG
 */
import type { OutputGenerateResult } from './api'

type ExportFormat = 'pdf' | 'word' | 'markdown' | 'html' | 'json' | 'png'

const FORMAT_META: Record<ExportFormat, { label: string; icon: string; ext: string }> = {
    pdf: { label: 'PDF', icon: '📄', ext: 'pdf' },
    word: { label: 'Word', icon: '📝', ext: 'docx' },
    markdown: { label: 'Markdown', icon: '⬇', ext: 'md' },
    html: { label: 'HTML', icon: '🌐', ext: 'html' },
    json: { label: 'JSON', icon: '{ }', ext: 'json' },
    png: { label: '图谱 PNG', icon: '🖼', ext: 'png' },
}

export { FORMAT_META }
export type { ExportFormat }

function sanitizeFilename(name: string): string {
    return name.replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, '_').slice(0, 80)
}

function buildFilename(result: OutputGenerateResult, ext: string): string {
    const base = sanitizeFilename(`${result.name}_${result.topic}`)
    const ts = new Date().toISOString().slice(0, 10)
    return `${base}_${ts}.${ext}`
}

function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
}

/* ═══ 数据 → 结构化行 ═══ */
interface StructuredSection {
    label: string
    kind: 'text' | 'list' | 'shots'
    value?: string
    items?: string[]
    shots?: Record<string, unknown>[]
}

function dataToSections(data: Record<string, unknown>): StructuredSection[] {
    const labelMap: Record<string, string> = {
        topic: '研究主题', research_background: '研究背景', research_gap: '研究空白',
        scientific_hypotheses: 'AI 科学假设', suggested_methods: '建议研究方法',
        suggested_data_sources: '建议数据来源', experiment_steps: '建议实验步骤',
        feasibility_analysis: '可行性分析', note: '助研说明',
        target_countries: '目标国家', target_audiences: '目标受众',
        communication_goals: '传播目标', narrative_frameworks: '叙事框架',
        recommended_titles: '推荐标题', keywords: '关键词', risk_warnings: '风险提醒',
        china_media_differences: '中外媒体差异', lead_suggestions: '导语建议',
        body_framework: '正文框架', interview_subjects: '推荐采访对象',
        image_suggestions: '配图建议', platform_suggestions: '传播平台建议',
        paper_title: '论文标题', abstract_framework: '摘要框架',
        introduction_framework: '引言框架', literature_review_framework: '文献综述框架',
        method_framework: '研究方法框架', result_framework: '结果框架',
        discussion_framework: '讨论框架', future_work_framework: '未来工作',
        research_questions: '研究问题', kg_summary: '知识图谱总览',
        hot_nodes: '热点节点', key_persons: '关键人物', organizations: '机构',
        relations: '关系三元组', platform: '目标平台', title: '脚本标题',
        opening_hook: '开场钩子', shots: '分镜脚本', bgm_suggestion: 'BGM 建议',
        hashtags: '话题标签', author_notes: '发布/运营提示',
    }
    return Object.entries(data)
        .filter(([, v]) => v !== undefined && v !== null && v !== '' && !['evidence_sources', 'status'].includes(v as string))
        .map(([k, v]) => {
            const label = labelMap[k] || k
            if (k === 'shots' && Array.isArray(v)) {
                return { label, kind: 'shots' as const, shots: v as Record<string, unknown>[] }
            }
            if (Array.isArray(v)) {
                return {
                    label, kind: 'list' as const,
                    items: v.map((item: unknown) =>
                        typeof item === 'object' && item !== null
                            ? Object.entries(item as Record<string, unknown>)
                                .filter(([, vv]) => vv !== undefined && vv !== null && vv !== '')
                                .map(([kk, vv]) => `${kk}: ${String(vv)}`).join(' | ')
                            : String(item)
                    ),
                }
            }
            if (typeof v === 'object' && v !== null) {
                return {
                    label, kind: 'text' as const,
                    value: Object.entries(v as Record<string, unknown>)
                        .filter(([, vv]) => vv !== undefined && vv !== null && vv !== '')
                        .map(([kk, vv]) => `${kk}: ${String(vv)}`).join('\n'),
                }
            }
            return { label, kind: 'text' as const, value: String(v) }
        })
}

/* ═══ Markdown ═══ */
function buildMarkdown(result: OutputGenerateResult): string {
    const sections = dataToSections(result.data)
    const lines = [
        `# ${result.name}：${result.topic}`,
        '',
        `> 生成时间：${result.created_at} ｜ 生成器：${result.generator_type}`,
        '',
    ]
    for (const s of sections) {
        lines.push(`## ${s.label}`, '')
        if (s.kind === 'shots' && s.shots) {
            s.shots.forEach((shot, idx) => {
                lines.push(`### 第 ${shot.scene_no || idx + 1} 镜头`, '')
                if (shot.scene_description) lines.push(`- 画面：${shot.scene_description}`)
                if (shot.duration_seconds) lines.push(`- 时长：${shot.duration_seconds}s`)
                if (shot.caption) lines.push(`- 字幕：${shot.caption}`)
                if (shot.narration) lines.push(`- 旁白：${shot.narration}`)
                if (shot.visual_suggestion) lines.push(`- 配图建议：${shot.visual_suggestion}`)
                lines.push('')
            })
        } else if (s.kind === 'list' && s.items) {
            s.items.forEach(item => lines.push(`- ${item}`))
            lines.push('')
        } else if (s.value) {
            lines.push(s.value, '')
        }
    }
    return lines.join('\n')
}

/* ═══ HTML ═══ */
function buildHTML(result: OutputGenerateResult): string {
    const sections = dataToSections(result.data)
    const bodyBlocks = sections.map(s => {
        if (s.kind === 'shots' && s.shots) {
            const items = s.shots.map((shot, idx) => `
        <div class="shot">
          <h4>第 ${shot.scene_no || idx + 1} 镜头</h4>
          ${shot.scene_description ? `<p><strong>画面：</strong>${shot.scene_description}</p>` : ''}
          ${shot.duration_seconds ? `<p><strong>时长：</strong>${shot.duration_seconds}s</p>` : ''}
          ${shot.caption ? `<p><strong>字幕：</strong>${shot.caption}</p>` : ''}
          ${shot.narration ? `<p><strong>旁白：</strong>${shot.narration}</p>` : ''}
          ${shot.visual_suggestion ? `<p><strong>配图建议：</strong>${shot.visual_suggestion}</p>` : ''}
        </div>`).join('')
            return `<section><h2>${s.label}</h2>${items}</section>`
        }
        if (s.kind === 'list' && s.items) {
            const li = s.items.map(i => `<li>${i}</li>`).join('')
            return `<section><h2>${s.label}</h2><ul>${li}</ul></section>`
        }
        if (s.value) {
            return `<section><h2>${s.label}</h2><p>${s.value.replace(/\n/g, '<br>')}</p></section>`
        }
        return ''
    }).join('\n')

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${result.name}：${result.topic}</title>
  <style>
    body { font-family: 'Noto Sans SC', system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1e293b; line-height: 1.8; }
    h1 { border-bottom: 2px solid #0cb8e8; padding-bottom: 8px; }
    h2 { color: #0e7490; margin-top: 24px; }
    .meta { color: #64748b; font-size: 13px; }
    section { margin: 16px 0; padding: 12px 0; border-bottom: 1px solid #e2e8f0; }
    ul { padding-left: 20px; }
    li { margin: 4px 0; }
    .shot { background: #f8fafc; padding: 10px 14px; border-radius: 8px; margin: 8px 0; }
  </style>
</head>
<body>
  <h1>${result.name}：${result.topic}</h1>
  <p class="meta">生成时间：${result.created_at} ｜ 生成器：${result.generator_type}</p>
  ${bodyBlocks}
</body>
</html>`
}

/* ═══ JSON ═══ */
function buildJSON(result: OutputGenerateResult): string {
    return JSON.stringify({
        name: result.name,
        topic: result.topic,
        generator_type: result.generator_type,
        created_at: result.created_at,
        data: result.data,
    }, null, 2)
}

/* ═══ PDF（浏览器打印） ═══ */
function exportPDF(result: OutputGenerateResult) {
    const html = buildHTML(result)
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(html)
    win.document.close()
    win.onload = () => { win.print() }
}

/* ═══ Word（HTML-based .doc） ═══ */
function buildWordHTML(result: OutputGenerateResult): string {
    const sections = dataToSections(result.data)
    const bodyBlocks = sections.map(s => {
        if (s.kind === 'shots' && s.shots) {
            const items = s.shots.map((shot, idx) => `
        <div style="margin:8px 0;padding:8px 12px;background:#f5f5f5;border-radius:4px">
          <p><b>第 ${shot.scene_no || idx + 1} 镜头</b></p>
          ${shot.scene_description ? `<p>画面：${shot.scene_description}</p>` : ''}
          ${shot.duration_seconds ? `<p>时长：${shot.duration_seconds}s</p>` : ''}
          ${shot.caption ? `<p>字幕：${shot.caption}</p>` : ''}
          ${shot.narration ? `<p>旁白：${shot.narration}</p>` : ''}
          ${shot.visual_suggestion ? `<p>配图建议：${shot.visual_suggestion}</p>` : ''}
        </div>`).join('')
            return `<h2 style="color:#0e7490">${s.label}</h2>${items}`
        }
        if (s.kind === 'list' && s.items) {
            const li = s.items.map(i => `<li>${i}</li>`).join('')
            return `<h2 style="color:#0e7490">${s.label}</h2><ul>${li}</ul>`
        }
        if (s.value) {
            return `<h2 style="color:#0e7490">${s.label}</h2><p>${s.value.replace(/\n/g, '<br>')}</p>`
        }
        return ''
    }).join('')

    return `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>${result.name}</title>
<style>body{font-family:'Noto Sans SC',sans-serif;font-size:12pt;line-height:1.8}h1{font-size:18pt}h2{font-size:14pt;margin-top:16pt}ul{padding-left:20pt}</style>
</head>
<body>
<h1>${result.name}：${result.topic}</h1>
<p style="color:#666;font-size:10pt">生成时间：${result.created_at} ｜ 生成器：${result.generator_type}</p>
${bodyBlocks}
</body></html>`
}

/* ═══ 知识图谱 PNG ═══ */
function exportKGPNG(result: OutputGenerateResult) {
    const kgEl = document.querySelector('[data-kg-chart] canvas') as HTMLCanvasElement | null
        || document.querySelector('.echarts-for-react canvas') as HTMLCanvasElement | null
    if (!kgEl) {
        alert('未找到知识图谱图表，请先打开知识图谱页面并确保图表已渲染。')
        return
    }
    const dataUrl = kgEl.toDataURL('image/png')
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = buildFilename(result, 'png')
    a.click()
}

/* ═══ 统一导出入口 ═══ */
export function exportResult(result: OutputGenerateResult, format: ExportFormat) {
    const filename = buildFilename(result, FORMAT_META[format].ext)

    switch (format) {
        case 'markdown': {
            const content = buildMarkdown(result)
            const blob = new Blob(['\uFEFF' + content], { type: 'text/markdown;charset=utf-8' })
            downloadBlob(blob, filename)
            break
        }
        case 'html': {
            const content = buildHTML(result)
            const blob = new Blob([content], { type: 'text/html;charset=utf-8' })
            downloadBlob(blob, filename)
            break
        }
        case 'json': {
            const content = buildJSON(result)
            const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
            downloadBlob(blob, filename)
            break
        }
        case 'pdf': {
            exportPDF(result)
            break
        }
        case 'word': {
            const content = buildWordHTML(result)
            const blob = new Blob([content], { type: 'application/msword;charset=utf-8' })
            downloadBlob(blob, filename)
            break
        }
        case 'png': {
            exportKGPNG(result)
            break
        }
    }
}