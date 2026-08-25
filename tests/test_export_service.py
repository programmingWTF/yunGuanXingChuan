"""
云观星传 - 多格式导出服务单元测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock

from src.export_service import (
    export_json, export_markdown, export_html, export_pdf, export_word,
    get_export_formats, do_export, EXPORT_FORMATS,
    _dict_to_md, _parse_md_blocks,
)

SAMPLE_DATA = {
    "topic": "嫦娥六号",
    "research_background": "月球背面采样返回任务",
    "key_findings": ["发现1", "发现2"],
}
SAMPLE_META = {
    "generator_type": "research_plan",
    "name": "科学假设与研究计划",
    "topic": "嫦娥六号",
}

# 复杂样例：覆盖键值对/嵌套/对象数组/JSON 片段/长文本（issue #118 智能排版）
RICH_DATA = {
    "topic": "天问三号火星采样返回",
    "project_title": "天问三号任务规划研究",
    "risk_level": "中",
    "score": 86,
    "research_background": (
        "火星采样返回是国际深空探测的前沿方向。天问三号作为我国首次火星采样返回任务，"
        "其工程实施涉及发射窗口、轨道设计、着陆采样、上升器交会对接、再入返回等多个关键环节，"
        "各环节之间存在强耦合约束，需要系统级协同优化。"
    ),
    "key_findings": ["发现1", "发现2", "发现3"],
    "methods": [
        {"name": "轨迹优化", "tool": "GMAT", "confidence": 0.92},
        {"name": "多学科耦合分析", "tool": "自研", "confidence": 0.85},
    ],
    "sections": [
        {"title": "引言", "content": "背景与意义..."},
    ],
    "raw_json": '{"window": "2033", "orbit": "Hohmann"}',
}


class TestExportFormats:
    """导出格式注册表测试"""

    def test_base_formats(self):
        """普通生成器应有 5 种格式"""
        formats = get_export_formats("research_plan")
        assert "json" in formats
        assert "markdown" in formats
        assert "html" in formats
        assert "pdf" in formats
        assert "word" in formats
        assert "kg_png" not in formats

    def test_kg_report_has_png(self):
        """kg_report 应额外支持 kg_png"""
        formats = get_export_formats("kg_report")
        assert "kg_png" in formats

    def test_all_formats_registered(self):
        """EXPORT_FORMATS 应包含 6 种格式"""
        assert len(EXPORT_FORMATS) == 6


class TestExportJson:
    """JSON 导出测试"""

    def test_valid_json(self):
        import json
        content = export_json(SAMPLE_DATA, SAMPLE_META)
        parsed = json.loads(content.decode("utf-8"))
        assert parsed["data"]["topic"] == "嫦娥六号"
        assert parsed["export_meta"]["format"] == "json"


class TestExportMarkdown:
    """Markdown 导出测试"""

    def test_contains_title(self):
        content = export_markdown(SAMPLE_DATA, SAMPLE_META).decode("utf-8")
        assert "科学假设与研究计划" in content
        assert "嫦娥六号" in content

    def test_contains_data(self):
        content = export_markdown(SAMPLE_DATA, SAMPLE_META).decode("utf-8")
        assert "月球背面采样返回任务" in content


class TestDictToMd:
    """issue #118：_dict_to_md 结构化排版测试"""

    def _render(self, data):
        lines = []
        _dict_to_md(data, lines, level=2)
        return "\n".join(lines)

    def test_key_value_pairs_become_table(self):
        """标量键值对 → 表格（| 字段 | 值 |）"""
        md = self._render({"topic": "嫦娥六号", "score": 86})
        assert "| 字段 | 值 |" in md
        assert "| --- | --- |" in md
        assert "| topic | 嫦娥六号 |" in md
        assert "| score | 86 |" in md

    def test_scalar_list_becomes_bullets(self):
        """标量数组 → 无序列表"""
        md = self._render({"key_findings": ["发现1", "发现2"]})
        assert "- 发现1" in md
        assert "- 发现2" in md

    def test_object_list_becomes_table(self):
        """对象数组 → 表格（字段名作表头）"""
        md = self._render({"methods": [{"name": "轨迹优化", "confidence": 0.92}, {"name": "耦合分析", "confidence": 0.85}]})
        assert "| name | confidence |" in md
        assert "| 轨迹优化 | 0.92 |" in md
        assert "| 耦合分析 | 0.85 |" in md

    def test_nested_dict_uses_heading_level(self):
        """嵌套 dict → 下一级标题（## / ### 层级递增）"""
        md = self._render({"details": {"inner": {"a": 1}}})
        assert "## details" in md
        assert "### inner" in md
        assert "| a | 1 |" in md

    def test_json_fragment_becomes_code_block(self):
        """JSON 片段字段 → 围栏代码块（```json）"""
        md = self._render({"raw_json": '{"window": "2033"}'})
        assert "```json" in md
        assert '{"window": "2033"}' in md

    def test_long_text_becomes_paragraph(self):
        """长文本不进表格 → 加粗小节标题 + 独立段落"""
        long_text = "长" * 200
        md = self._render({"research_background": long_text})
        assert "**research_background**" in md
        assert long_text in md
        assert "| research_background |" not in md

    def test_empty_values_skipped(self):
        """空值（None/""/[]/{}）跳过"""
        md = self._render({"topic": "t", "empty_list": [], "empty_dict": {}, "none_val": None, "empty_str": ""})
        assert "| topic | t |" in md
        assert "empty_list" not in md
        assert "empty_dict" not in md
        assert "none_val" not in md
        assert "empty_str" not in md

    def test_rich_data_renders_all_structures(self):
        """复杂样例：表格/列表/嵌套标题/代码块齐全"""
        md = self._render(RICH_DATA)
        assert "| 字段 | 值 |" in md                     # 键值对表格
        assert "| risk_level | 中 |" in md               # 短标量进表格
        assert "```json" in md                            # JSON 片段代码块
        assert "| name | tool | confidence |" in md      # 对象数组表头
        assert "| 轨迹优化 | GMAT | 0.92 |" in md        # 对象数组数据行
        assert "- 发现1" in md                            # 标量数组列表
        assert "## methods" in md                          # 嵌套标题（顶层 data 的嵌套键为 ##）
        assert "## sections" in md


class TestParseMdBlocks:
    """issue #118：_parse_md_blocks 块解析测试（HTML/PDF/Word 共用）"""

    def test_parses_table(self):
        blocks = _parse_md_blocks("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        assert blocks[0]["type"] == "table"
        assert blocks[0]["headers"] == ["a", "b"]
        assert blocks[0]["rows"] == [["1", "2"]]

    def test_parses_code_block(self):
        blocks = _parse_md_blocks('```json\n{"a": 1}\n```\n')
        assert blocks[0]["type"] == "code"
        assert blocks[0]["lang"] == "json"
        assert blocks[0]["text"] == '{"a": 1}'

    def test_parses_headings_and_lists(self):
        blocks = _parse_md_blocks("## 标题\n- 甲\n- 乙\n")
        types = [b["type"] for b in blocks]
        assert types == ["h2", "ul"]
        assert blocks[1]["items"] == ["甲", "乙"]

    def test_parses_ordered_list(self):
        blocks = _parse_md_blocks("1. 一\n2. 二\n")
        assert blocks[0]["type"] == "ol"
        assert blocks[0]["items"] == ["一", "二"]

    def test_parses_quote_and_para(self):
        blocks = _parse_md_blocks("> 引用\n\n正文段落\n")
        types = [b["type"] for b in blocks]
        assert types == ["quote", "para"]

    def test_html_contains_css_and_table(self):
        """HTML 导出：内联 CSS + 表格结构"""
        content = export_html(RICH_DATA, SAMPLE_META).decode("utf-8")
        assert "<style>" in content
        assert "nth-child(even)" in content            # 斑马纹
        assert "<table>" in content
        assert "<th>" in content
        assert "<pre><code>" in content                # 代码块
        assert "Noto Serif SC" in content              # 中文字体栈

    def test_json_export_unchanged(self):
        """issue #118：JSON 导出必须与之前完全一致（indent=2 原样）"""
        content = export_json(RICH_DATA, SAMPLE_META).decode("utf-8")
        import json as _json
        parsed = _json.loads(content)
        assert parsed["data"] == RICH_DATA
        assert parsed["export_meta"]["format"] == "json"
        assert "\n  " in content  # indent=2 结构保留


class TestExportHtml:
    """HTML 导出测试"""

    def test_valid_html(self):
        content = export_html(SAMPLE_DATA, SAMPLE_META).decode("utf-8")
        assert "<!DOCTYPE html>" in content
        assert "嫦娥六号" in content
        assert "</html>" in content


class TestExportPdf:
    """PDF 导出测试"""

    def test_produces_bytes(self):
        content = export_pdf(SAMPLE_DATA, SAMPLE_META)
        assert isinstance(content, bytes)
        assert len(content) > 100
        assert content[:4] == b"%PDF"


class TestExportWord:
    """Word 导出测试"""

    def test_produces_bytes(self):
        content = export_word(SAMPLE_DATA, SAMPLE_META)
        assert isinstance(content, bytes)
        assert len(content) > 100
        # docx 是 zip 格式，以 PK 开头
        assert content[:2] == b"PK"


class TestDoExport:
    """统一导出接口测试"""

    def test_valid_format(self):
        content = do_export(SAMPLE_DATA, SAMPLE_META, "json")
        assert content is not None

    def test_invalid_format(self):
        content = do_export(SAMPLE_DATA, SAMPLE_META, "xlsx")
        assert content is None
