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
