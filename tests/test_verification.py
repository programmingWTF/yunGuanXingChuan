"""
云观星传 - 校验层单元测试
验证 KG 校验、交叉验证逻辑（不依赖 LLM）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from src.schemas import VerificationStatus


class TestKGChecker:
    """知识图谱校验器测试"""

    @pytest.fixture
    def kg_checker(self):
        """创建 KGChecker 实例（使用真实 KG 数据）"""
        from src.verification.kg_checker import KGChecker
        return KGChecker()

    def test_existing_entity_found(self, kg_checker):
        """图中存在的实体应能被找到"""
        context = kg_checker.get_related_context("嫦娥六号", depth=1)
        # 嫦娥六号在 KG 中应存在
        assert context is not None

    def test_nonexistent_entity(self, kg_checker):
        """不存在的实体应返回空"""
        context = kg_checker.get_related_context("完全不存在的实体XYZ", depth=1)
        # 不存在的实体应返回空或 None
        assert not context or len(context) == 0

    def test_verify_triple_structure(self, kg_checker):
        """verify_triple 返回结构正确"""
        result = kg_checker.verify_triple("嫦娥六号", "launched_by", "长征五号")
        assert "status" in result
        assert "confidence" in result
        assert result["status"] in ["verified", "partial", "unverified"]


class TestCrossValidator:
    """交叉验证器测试"""

    @staticmethod
    def _mock_heavy_deps():
        """Mock 未安装的重型依赖（faiss, openai），让测试可以导入校验模块"""
        for mod_name, mock_mod in [
            ('faiss', MagicMock()),
            ('openai', MagicMock()),
            ('openai.OpenAI', MagicMock()),
            ('httpx', MagicMock()),
        ]:
            if mod_name not in sys.modules:
                sys.modules[mod_name] = mock_mod
        # 清理因依赖缺失而半初始化的缓存模块
        for mod_name in list(sys.modules):
            if any(mod_name.startswith(p) for p in [
                'src.knowledge.vector_store', 'src.verification.rag_checker',
                'src.verification.external_validator', 'src.verification.cross_validator',
                'src.llm_client', 'src.search',
            ]):
                del sys.modules[mod_name]

    @pytest.fixture
    def mock_cross_validator(self):
        """创建带 mock 的 CrossValidator（不依赖 LLM）"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        # 必须 patch cross_validator 模块命名空间中的引用（而非源模块）
        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported",
                "confidence": 0.85,
                "evidence": "嫦娥六号实现人类首次月背采样返回",
            }
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "partial",
                "confidence": 0.5,
                "evidence": "外部校验结果",
            }
            yield cv_module.CrossValidator()
            # 恢复被 _mock_heavy_deps 替换的 sys.modules 条目（防止污染后续测试：
            # openai 内部 isinstance(httpx.URL) 检查在 httpx 为 MagicMock 时会 TypeError）
            for mod_name in ('faiss', 'httpx', 'openai', 'openai.OpenAI'):
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
            # 让依赖模块在真实依赖下重新导入
            for mod_name in list(sys.modules):
                if any(mod_name.startswith(p) for p in [
                    'src.knowledge.vector_store', 'src.verification.rag_checker',
                    'src.verification.external_validator', 'src.verification.cross_validator',
                    'src.llm_client', 'src.search',
                ]):
                    del sys.modules[mod_name]

    def test_dual_support_verified(self, mock_cross_validator):
        """RAG + KG 双方支持 → VERIFIED 或 PARTIAL"""
        result = mock_cross_validator.cross_validate_claim(
            "嫦娥六号实现了人类首次月球背面采样返回",
            entities=["嫦娥六号"],
        )
        assert result.status in [VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED]
        assert result.confidence >= 0.5  # KG partial 0.5 + External partial 0.5 → 2 supports → partial ≥ 0.5

    def test_no_entities_still_works(self, mock_cross_validator):
        """无实体列表时仍能通过 RAG 校验"""
        result = mock_cross_validator.cross_validate_claim(
            "嫦娥六号于2024年发射",
            entities=None,
        )
        assert result.status is not None
        assert result.claim == "嫦娥六号于2024年发射"

    def test_rag_unsupported(self):
        """RAG 不支持时应返回较低置信度"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "unverified",
                "confidence": 0.2,
                "evidence": "",
            }
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "unverified",
                "confidence": 0.1,
                "evidence": "",
            }
            validator = cv_module.CrossValidator()

            result = validator.cross_validate_claim(
                "月球是由奶酪构成的",
                entities=[],
            )
            assert result.confidence < 0.5


class TestVerificationResult:
    """VerificationResult 模型测试"""

    def test_result_fields(self):
        """验证结果字段完整性"""
        from src.schemas import VerificationResult
        result = VerificationResult(
            claim="测试断言",
            status=VerificationStatus.VERIFIED,
            rag_evidence="证据文本",
            kg_match="KG匹配",
            cross_source_agreement=True,
            confidence=0.9,
            notes="测试备注",
        )
        assert result.claim == "测试断言"
        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence == 0.9
        assert result.cross_source_agreement is True

    def test_optional_fields_default(self):
        """可选字段默认为 None"""
        from src.schemas import VerificationResult
        result = VerificationResult(
            claim="测试",
            status=VerificationStatus.UNVERIFIED,
            confidence=0.3,
        )
        assert result.rag_evidence is None
        assert result.kg_match is None
        assert result.cross_source_agreement is None
