"""
云观星传 - 多格式导出服务
支持：JSON / Markdown / HTML / PDF / Word / KG-PNG
"""
import json
import io
from typing import Dict, Any, Optional
from datetime import datetime


def export_json(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出为 JSON 文件"""
    payload = {
        "export_meta": {
            "generator_type": meta.get("generator_type", ""),
            "topic": meta.get("topic", ""),
            "exported_at": datetime.now().isoformat(),
            "format": "json",
        },
        "data": data,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_markdown(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出为 Markdown 文件"""
    lines = [
        f"# {meta.get('name', '成果')}：{meta.get('topic', '')}",
        "",
        f"> 生成器：{meta.get('generator_type', '')} ｜ 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    _dict_to_md(data, lines, level=2)
    return "\n".join(lines).encode("utf-8")


def _dict_to_md(d: Any, lines: list, level: int = 2):
    """递归将字典/列表转为 Markdown"""
    if isinstance(d, dict):
        for k, v in d.items():
            if v is None or v == "" or v == []:
                continue
            if isinstance(v, (dict, list)):
                lines.append(f"{'#' * level} {k}")
                lines.append("")
                _dict_to_md(v, lines, level + 1)
            else:
                lines.append(f"**{k}**：{v}")
                lines.append("")
    elif isinstance(d, list):
        for item in d:
            if isinstance(item, dict):
                parts = [f"{k}: {v}" for k, v in item.items() if v]
                lines.append(f"- {' | '.join(parts)}")
            else:
                lines.append(f"- {item}")
        lines.append("")


def export_html(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出为 HTML 文件（自包含样式）"""
    md_content = export_markdown(data, meta).decode("utf-8")
    # 简易 Markdown → HTML（标题/列表/加粗/段落）
    html_body = _simple_md_to_html(md_content)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{meta.get('name', '成果')} - {meta.get('topic', '')}</title>
<style>
body {{ font-family: 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.8; color: #333; }}
h1 {{ color: #1a237e; border-bottom: 2px solid #3f51b5; padding-bottom: 8px; }}
h2 {{ color: #283593; margin-top: 24px; }}
h3 {{ color: #3949ab; }}
blockquote {{ color: #666; border-left: 3px solid #ccc; padding-left: 12px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
ul {{ padding-left: 20px; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    return html.encode("utf-8")


def _simple_md_to_html(md: str) -> str:
    """简易 Markdown 转 HTML"""
    lines = md.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{line[2:]}</blockquote>")
        elif line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            # 处理加粗
            content = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if "**" in line else line
            html_lines.append(f"<p>{content}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def _pdf_wrap(pdf, text: str, max_width: float) -> list:
    """使用 get_string_width 逐字测量手动断行。

    fpdf2 内置换行对 CJK 支持不佳：WORD 模式处理无空格长中文会抛
    "Not enough horizontal space"，CHAR 模式在部分 TTC 字体下会死循环。
    这里按真实字宽自行断行，规避上述问题。
    """
    if not text:
        return [""]
    lines, current = [], ""
    for ch in text:
        if current and pdf.get_string_width(current + ch) > max_width:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


def _find_cjk_font() -> tuple:
    """查找可用的 CJK 字体，返回 (font_path, font_name)。

    搜索顺序：
    1. 项目内嵌 config/fonts/NotoSansSC-Regular.ttf（Docker 镜像打包 / 手动放置）
    2. Windows 系统字体（msyh / simsun）
    3. Linux 系统字体（fonts-noto-cjk 安装路径）
    4. macOS 系统字体（PingFang / STSong）

    未找到时返回 (None, "Helvetica")，调用方需做降级处理。
    """
    import os

    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "config", "fonts", "NotoSansSC-Regular.ttf"),
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STSong.ttf",
    ]
    for fp in candidates:
        norm = os.path.normpath(fp)
        if os.path.exists(norm):
            return norm, "CJK"
    return None, "Helvetica"


def export_pdf(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出为 PDF 文件（使用 fpdf2，自动查找中文字体）

    字体策略：
    - 优先使用 CJK 字体（项目内嵌 > 系统 > macOS）
    - 无 CJK 字体时回退 Helvetica，并在 PDF 首行插入警告水印
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    import os
    import logging

    logger = logging.getLogger(__name__)

    pdf = FPDF()
    pdf.add_page()

    font_path, font_name = _find_cjk_font()
    cjk_available = font_path is not None

    if cjk_available:
        try:
            pdf.add_font("CJK", "", font_path)
            pdf.add_font("CJK", "B", font_path)
            font_name = "CJK"
        except Exception as e:
            logger.warning(f"加载 CJK 字体失败 ({font_path}): {e}，回退 Helvetica")
            font_name = "Helvetica"
            cjk_available = False
    else:
        logger.warning(
            "未找到 CJK 字体，PDF 中文将显示为方框。"
            "请将 NotoSansSC-Regular.ttf 放入 config/fonts/ 或安装系统字体（fonts-noto-cjk / 微软雅黑）"
        )

    max_width = pdf.w - pdf.l_margin - pdf.r_margin

    def write(text: str, size: int = 11, bold: bool = False, color=(0, 0, 0), h: float = 6):
        pdf.set_font(font_name, "B" if bold else "", size)
        pdf.set_text_color(*color)
        for phys in _pdf_wrap(pdf, text, max_width):
            pdf.cell(0, h, phys, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if not cjk_available:
        write("⚠ PDF 中文字体缺失 — 中文内容将显示异常", size=10, bold=True, color=(200, 0, 0), h=6)
        write("请将 NotoSansSC-Regular.ttf 放入 config/fonts/ 目录", size=8, color=(150, 0, 0), h=5)
        pdf.ln(4)

    write(f"{meta.get('name', 'Result')}: {meta.get('topic', '')}", size=16, bold=True, h=10)
    pdf.ln(4)
    write(
        f"Generator: {meta.get('generator_type', '')} | Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        size=9, color=(100, 100, 100),
    )
    pdf.ln(6)

    md_lines = export_markdown(data, meta).decode("utf-8").split("\n")
    for line in md_lines[4:]:
        if not line.strip():
            pdf.ln(3)
            continue
        if line.startswith("## "):
            write(line[3:], size=13, bold=True, h=8)
        elif line.startswith("- "):
            write(f"  - {line[2:]}")
        else:
            write(line.replace("**", ""))

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def export_word(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出为 Word (.docx) 文件"""
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()

    # 标题
    title = doc.add_heading(f"{meta.get('name', '成果')}：{meta.get('topic', '')}", level=0)

    # Meta 信息
    p = doc.add_paragraph()
    run = p.add_run(f"生成器：{meta.get('generator_type', '')} ｜ 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(128, 128, 128)

    # 内容
    _dict_to_docx(data, doc)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _dict_to_docx(d: Any, doc, level: int = 1):
    """递归将字典写入 Word 文档"""
    from docx import Document as _D  # noqa

    if isinstance(d, dict):
        for k, v in d.items():
            if v is None or v == "" or v == []:
                continue
            if isinstance(v, (dict, list)):
                doc.add_heading(str(k), level=min(level, 4))
                _dict_to_docx(v, doc, level + 1)
            else:
                p = doc.add_paragraph()
                run = p.add_run(f"{k}：")
                run.bold = True
                p.add_run(str(v))
    elif isinstance(d, list):
        for item in d:
            if isinstance(item, dict):
                parts = [f"{k}: {v}" for k, v in item.items() if v]
                doc.add_paragraph(" | ".join(parts), style="List Bullet")
            else:
                doc.add_paragraph(str(item), style="List Bullet")


def export_kg_png(data: Dict[str, Any], meta: Dict[str, str]) -> bytes:
    """导出知识图谱报告为 PNG 可视化（仅 kg_report 类型）"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_facecolor("#0a0e27")
    fig.patch.set_facecolor("#0a0e27")

    G = nx.Graph()
    topic = meta.get("topic", "")
    G.add_node(topic, node_type="topic")

    # 从 KG 报告数据构建图
    for node_stat in data.get("hot_nodes", [])[:8]:
        name = node_stat.get("name", "")
        if name:
            G.add_node(name, node_type="hot")
            G.add_edge(topic, name)

    for person in data.get("key_persons", [])[:5]:
        name = person.get("name", "")
        if name:
            G.add_node(name, node_type="person")
            G.add_edge(topic, name)

    for org in data.get("organizations", [])[:5]:
        name = org.get("name", "")
        if name:
            G.add_node(name, node_type="org")
            G.add_edge(topic, name)

    for rel in data.get("relations", [])[:10]:
        subj = rel.get("subject", "")
        obj = rel.get("object", "")
        pred = rel.get("predicate", "")
        if subj and obj:
            G.add_edge(subj, obj, label=pred)

    if len(G.nodes) <= 1:
        ax.text(0.5, 0.5, "No KG data available", ha="center", va="center", color="white", fontsize=14)
    else:
        pos = nx.spring_layout(G, seed=42)
        colors = {"topic": "#ffd700", "hot": "#00ced1", "person": "#ff6b6b", "org": "#69db7c"}
        node_colors = [colors.get(G.nodes[n].get("node_type", ""), "#aaa") for n in G.nodes]
        sizes = [800 if G.nodes[n].get("node_type") == "topic" else 400 for n in G.nodes]

        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3, edge_color="#4a5568")
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=sizes, alpha=0.9)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=8, font_color="white", font_family="sans-serif")

    ax.set_title(f"Knowledge Graph: {topic}", color="white", fontsize=14)
    ax.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# 格式注册表
EXPORT_FORMATS = {
    "json": {"handler": export_json, "ext": ".json", "mime": "application/json"},
    "markdown": {"handler": export_markdown, "ext": ".md", "mime": "text/markdown"},
    "html": {"handler": export_html, "ext": ".html", "mime": "text/html"},
    "pdf": {"handler": export_pdf, "ext": ".pdf", "mime": "application/pdf"},
    "word": {"handler": export_word, "ext": ".docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "kg_png": {"handler": export_kg_png, "ext": ".png", "mime": "image/png"},
}


def get_export_formats(generator_type: str) -> list:
    """根据生成器类型返回可用导出格式"""
    base = ["json", "markdown", "html", "pdf", "word"]
    if generator_type == "kg_report":
        base.append("kg_png")
    return base


def do_export(data: Dict[str, Any], meta: Dict[str, str], fmt: str) -> Optional[bytes]:
    """执行导出，返回文件字节内容"""
    handler_info = EXPORT_FORMATS.get(fmt)
    if not handler_info:
        return None
    try:
        return handler_info["handler"](data, meta)
    except Exception as e:
        raise ValueError(f"导出失败 ({fmt}): {e}")