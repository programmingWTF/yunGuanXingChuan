"""
云观星传 - 文档预处理与智能切片模块单元测试
验证文件解析、智能切片（Markdown/段落）、元数据提取与入库（Mock 向量库）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def preprocessor():
    """创建 DocumentPreprocessor 实例"""
    from src.knowledge.preprocessor import DocumentPreprocessor
    return DocumentPreprocessor()


class TestExtractText:
    """文件解析测试"""

    def test_txt_extraction(self, preprocessor, tmp_path):
        """应正确读取 .txt 文件"""
        f = tmp_path / "test.txt"
        f.write_text("第一段内容。\n\n第二段内容。", encoding="utf-8")
        result = preprocessor.extract_text(f)
        assert "第一段内容" in result
        assert "第二段内容" in result

    def test_md_extraction(self, preprocessor, tmp_path):
        """应正确读取 .md 文件"""
        f = tmp_path / "test.md"
        f.write_text("# 标题\n\n正文内容", encoding="utf-8")
        result = preprocessor.extract_text(f)
        assert "# 标题" in result
        assert "正文内容" in result

    def test_pdf_extraction(self, preprocessor, tmp_path):
        """应通过 pypdf 提取 PDF 文本"""
        f = tmp_path / "x.pdf"
        f.write_bytes(b"%PDF dummy")
        with patch("src.knowledge.preprocessor.PdfReader") as MockReader:
            page_mock = MagicMock()
            page_mock.extract_text.return_value = "PDF 内容第一页"
            MockReader.return_value.pages = [page_mock]
            result = preprocessor.extract_text(f)
            assert "PDF 内容第一页" in result

    def test_docx_extraction(self, preprocessor, tmp_path):
        """应通过 python-docx 提取 docx 文本"""
        f = tmp_path / "y.docx"
        f.write_bytes(b"PK dummy docx")
        with patch("src.knowledge.preprocessor.docx") as MockDocx:
            doc = MockDocx.Document.return_value
            para1 = MagicMock(text="段落一")
            doc.paragraphs = [para1]
            table = MagicMock()
            row1 = MagicMock()
            cell1 = MagicMock(text="表格单元")
            row1.cells = [cell1]
            table.rows = [row1]
            doc.tables = [table]

            result = preprocessor.extract_text(f)
            assert "段落一" in result
            assert "表格单元" in result

    def test_unsupported_extension(self, preprocessor, tmp_path):
        """不支持的文件类型应抛 ValueError"""
        f = tmp_path / "test.exe"
        f.write_bytes(b"\x00\x01")
        with pytest.raises(ValueError):
            preprocessor.extract_text(f)

    def test_nonexistent_file(self, preprocessor):
        """不存在的文件应抛 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            preprocessor.extract_text("nonexistent/file.txt")


class TestLanguageAndDate:
    """语言与日期提取"""

    def test_detect_chinese(self, preprocessor):
        from src.knowledge.preprocessor import DocumentPreprocessor
        assert DocumentPreprocessor.detect_language("这是中文内容") == "zh"

    def test_detect_english(self, preprocessor):
        from src.knowledge.preprocessor import DocumentPreprocessor
        assert DocumentPreprocessor.detect_language("This is English text") == "en"

    def test_extract_date_iso(self, preprocessor):
        from src.knowledge.preprocessor import DocumentPreprocessor
        assert DocumentPreprocessor.extract_date("发布于 2026-07-12 的消息") == "2026-07-12"

    def test_extract_date_chinese_style(self, preprocessor):
        from src.knowledge.preprocessor import DocumentPreprocessor
        assert DocumentPreprocessor.extract_date("2026年7月12日发布") == "2026-07-12"

    def test_extract_date_none(self, preprocessor):
        from src.knowledge.preprocessor import DocumentPreprocessor
        assert DocumentPreprocessor.extract_date("没有任何日期") == ""


class TestSmartChunk:
    """智能切片测试"""

    def test_split_markdown_sections(self, preprocessor):
        """Markdown 应按标题切分"""
        from src.knowledge.preprocessor import DocumentPreprocessor
        text = "# 第一章\n\n内容A\n\n## 第二章\n\n内容B\n\n### 2.1\n\n内容C"
        sections = DocumentPreprocessor.split_markdown_sections(text)
        assert len(sections) == 3
        assert sections[0]["heading"] == "第一章"
        assert "内容A" in sections[0]["content"]
        assert sections[1]["heading"] == "第二章"
        assert sections[2]["heading"] == "2.1"

    def test_chunk_paragraphs_respects_overlap(self, preprocessor):
        """段落分块应保留重叠"""
        from src.knowledge.preprocessor import DocumentPreprocessor
        # 构造 5 个足够长的段落，各 ~400 字，确保切成多块
        paragraphs = []
        for i in range(5):
            paragraphs.append(f"第{i}段 " + "内容" * 200)
        text = "\n\n".join(paragraphs)
        chunks = DocumentPreprocessor.chunk_paragraphs(text, chunk_min=300,
                                                       chunk_max=500, overlap=50)
        assert len(chunks) >= 2

    def test_smart_chunk_markdown_with_metadata(self, preprocessor):
        """Markdown 智能切片应保留章节元数据"""
        text = "# 嫦娥七号任务概述\n\n这是关于任务的整体介绍。\n\n" \
               "# 技术参数（2026年5月）\n\n发动机推力参数说明。"
        chunks = preprocessor.smart_chunk(text, source="doc.md")
        assert len(chunks) >= 2
        assert chunks[0].source == "doc.md"
        assert chunks[0].section == "嫦娥七号任务概述"
        # 第二个块的标题或日期应保留
        assert any("技术参数" in c.section for c in chunks)
        assert chunks[0].language == "zh"

    def test_smart_chunk_plain_text(self, preprocessor):
        """无标题的普通文本应能分块且 section 为空"""
        text = ("第一段。" * 150) + "\n\n" + ("第二段。" * 150)
        chunks = preprocessor.smart_chunk(text, source="plain.txt")
        assert len(chunks) >= 1
        # 无 Markdown 标题，section 应为空
        assert all(c.section == "" for c in chunks[:1])

    def test_smart_chunk_empty(self, preprocessor):
        """空文本应返回空列表"""
        chunks = preprocessor.smart_chunk("   \n\n  ", source="empty.txt")
        assert chunks == []

    def test_language_en_detection_per_chunk(self, preprocessor):
        """英文文档块 language 应为 en"""
        text = "This is a good paragraph about the mission.\n\nAnother paragraph here."
        chunks = preprocessor.smart_chunk(text, source="en.md")
        assert len(chunks) >= 1
        assert all(c.language == "en" for c in chunks)


class TestIngest:
    """入库测试（Mock 向量库）"""

    def test_preprocess_to_chunks(self, preprocessor, tmp_path):
        """preprocess 应返回文档块（不 mock 网络）"""
        f = tmp_path / "note.md"
        f.write_text("# 主题\n\n正文内容。", encoding="utf-8")
        chunks = preprocessor.preprocess(f, vector_store=MagicMock())
        assert len(chunks) == 1
        assert chunks[0].text == "正文内容。"
        assert chunks[0].source == "note.md"

    def test_ingest_chunks_writes_to_vector_store(self, preprocessor):
        """ingest_chunks 应调用 vector_store.build_index"""
        from src.knowledge.preprocessor import DocumentChunk
        mock_store = MagicMock()
        chunks = [
            DocumentChunk(text="块A内容", source="a.md", section="标题A", date="2026-07-01"),
            DocumentChunk(text="块B内容", source="a.md", section="标题B", date="2026-07-02"),
        ]
        result = preprocessor.ingest_chunks(chunks, vector_store=mock_store)
        assert result == 2
        mock_store.build_index.assert_called_once()
        docs = mock_store.build_index.call_args[0][0]
        assert len(docs) == 2
        assert docs[0]["type"] == "user_upload"
        assert docs[0]["title"] == "标题A"
        assert docs[0]["source"] == "a.md"

    def test_ingest_empty_returns_zero(self, preprocessor):
        """空块列表不应调用向量库"""
        mock_store = MagicMock()
        result = preprocessor.ingest_chunks([], vector_store=mock_store)
        assert result == 0
        mock_store.build_index.assert_not_called()

    def test_preprocess_with_ingest(self, preprocessor, tmp_path):
        """preprocess(ingest=True) 应调用入库"""
        f = tmp_path / "doc.md"
        f.write_text("# 标题\n\n内容区域。", encoding="utf-8")
        with patch.object(preprocessor, "ingest_chunks", wraps=preprocessor.ingest_chunks) as mock_ingest:
            chunks = preprocessor.preprocess(f, vector_store=MagicMock(), ingest=True)
        assert len(chunks) == 1
        mock_ingest.assert_called_once()


class TestSingleton:
    """全局单例"""

    def test_get_preprocessor_returns_same_instance(self):
        from src.knowledge.preprocessor import get_preprocessor
        a = get_preprocessor()
        b = get_preprocessor()
        assert a is b
