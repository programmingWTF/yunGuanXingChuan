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


class TestFourWayVoteAdaptive:
    """自适应四路投票测试（Issue #116 修复验证）"""

    @staticmethod
    def _mock_heavy_deps():
        """Mock 未安装的重型依赖"""
        for mod_name, mock_mod in [
            ('faiss', MagicMock()),
            ('openai', MagicMock()),
            ('openai.OpenAI', MagicMock()),
            ('httpx', MagicMock()),
        ]:
            if mod_name not in sys.modules:
                sys.modules[mod_name] = mock_mod
        for mod_name in list(sys.modules):
            if any(mod_name.startswith(p) for p in [
                'src.knowledge.vector_store', 'src.verification.rag_checker',
                'src.verification.external_validator', 'src.verification.cross_validator',
                'src.llm_client', 'src.search',
            ]):
                del sys.modules[mod_name]

    def test_two_voters_all_support_verified(self):
        """2 路参与全部支持 → VERIFIED（修复前：PARTIALLY_VERIFIED）"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = []
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "partial", "confidence": 0.6, "evidence": "外部证据",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("嫦娥六号实现月背采样", entities=None)
            assert result.status == VerificationStatus.VERIFIED

    def test_three_voters_majority_support_partial(self):
        """3 路参与（含 entity_found），2 路支持 → PARTIALLY_VERIFIED"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = [
                {"entity": "嫦娥六号", "relation": "launched_by", "direction": "outgoing", "depth": 1, "confidence": 0.9},
            ]
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "partial", "confidence": 0.6, "evidence": "外部证据",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("嫦娥六号实现月背采样", entities=["嫦娥六号"])
            assert result.status == VerificationStatus.PARTIALLY_VERIFIED

    def test_four_voters_two_support_partial(self):
        """4 路模式：2 支持 + 1 entity_found → 多数支持 → PARTIALLY_VERIFIED"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = [
                {"entity": "嫦娥六号", "relation": "launched_by", "direction": "outgoing", "depth": 1, "confidence": 0.9},
            ]
            mock_kg.verify_triple.return_value = {
                "status": "unverified", "confidence": 0.1, "source": "", "message": "不匹配",
            }
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "partial", "confidence": 0.5, "evidence": "外部证据",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("某断言", entities=["嫦娥六号"])
            assert result.status == VerificationStatus.PARTIALLY_VERIFIED

    def test_one_voter_support_partial(self):
        """仅 1 路参与且支持 → PARTIALLY_VERIFIED（修复前：UNVERIFIED）"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = []
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "unverified", "confidence": 0.1, "evidence": "",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("某断言", entities=None)
            assert result.status == VerificationStatus.PARTIALLY_VERIFIED

    def test_all_unverified(self):
        """全部 unverified → UNVERIFIED"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "unverified", "confidence": 0.1, "evidence": "",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = []
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "unverified", "confidence": 0.05, "evidence": "",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("月球由奶酪构成", entities=[])
            assert result.status == VerificationStatus.UNVERIFIED

    def test_conflicting(self):
        """支持+冲突 → CONFLICTING"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = []
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "conflicting", "confidence": 0.6, "evidence": "冲突证据",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("争议性断言", entities=None)
            assert result.status == VerificationStatus.CONFLICTING

    def test_kg_entity_found_not_support(self):
        """KG entity_found 不虚增支持数：RAG=supported + KG=entity_found + Ext=unverified → 1路支持 → PARTIAL"""
        self._mock_heavy_deps()
        import src.verification.cross_validator as cv_module

        with patch.object(cv_module, 'RAGChecker') as MockRAG, \
             patch.object(cv_module, 'KGChecker') as MockKG, \
             patch.object(cv_module, 'get_external_validator') as MockGetExt:
            mock_rag = MockRAG.return_value
            mock_rag.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "RAG证据",
            }
            mock_kg = MockKG.return_value
            mock_kg.get_related_context.return_value = [
                {"entity": "嫦娥六号", "relation": "launched_by", "direction": "outgoing", "depth": 1, "confidence": 0.9},
            ]
            mock_ext = MockGetExt.return_value
            mock_ext.validate.return_value = {
                "status": "unverified", "confidence": 0.1, "evidence": "",
            }
            validator = cv_module.CrossValidator()
            result = validator.cross_validate_claim("某断言", entities=["嫦娥六号"])
            assert result.status == VerificationStatus.PARTIALLY_VERIFIED
            assert "entity_found" in result.notes


class TestSubjectiveClaimFilter:
    """断言抽取语义测试（2026-09-01 修复：问题/建议/方向不当作事实断言校验）"""

    def test_inspiration_directions_not_claims(self):
        """选题方向（title/summary）是研究建议而非事实结论 → 不提取校验"""
        from src.workflow.engine import WorkflowEngine
        from src.workflow.stages import WorkflowStage
        engine = WorkflowEngine.__new__(WorkflowEngine)
        output = {
            "directions": [
                {"title": "具有重要意义", "summary": "该方向具有重要的理论和实践意义"},
                {"title": "嫦娥六号月背采样返回技术", "summary": "嫦娥六号于2024年实现人类首次月球背面采样返回"},
            ]
        }
        claims = engine._extract_claims(WorkflowStage.INSPIRATION, output)
        assert claims == []

    def test_review_suggestions_not_claims(self):
        """评审建议（suggestions）是指令性修改意见 → 不提取校验"""
        from src.workflow.engine import WorkflowEngine
        from src.workflow.stages import WorkflowStage
        engine = WorkflowEngine.__new__(WorkflowEngine)
        output = {
            "reviewers": [{"reviewer_id": "R1", "suggestions": ["建议补充样本量论证与信度检验"]}],
        }
        claims = engine._extract_claims(WorkflowStage.REVIEW, output)
        assert claims == []

    def test_writing_sections_kept(self):
        """论文章节内容（结论性断言）应保留"""
        from src.workflow.engine import WorkflowEngine
        from src.workflow.stages import WorkflowStage
        engine = WorkflowEngine.__new__(WorkflowEngine)
        output = {
            "sections": [{"section": "摘要", "content": "嫦娥六号于2024年实现人类首次月球背面采样返回并带回样品。"}],
        }
        claims = engine._extract_claims(WorkflowStage.WRITING, output)
        assert len(claims) > 0

class TestExternalValidatorMultiSource:
    """多数据源校验增强测试（2026-09-01 数据扩充）"""

    def _make_validator(self):
        """构造不触发网络的校验器（方法级纯逻辑测试）"""
        from src.verification.external_validator import ExternalValidator
        v = ExternalValidator.__new__(ExternalValidator)
        v._kg_entities = ["嫦娥六号", "月球", "AlphaGo", "DeepMind", "南极-艾特肯盆地"]
        return v

    def test_weak_meta_relation_rejected(self):
        """弱元数据关系（得名自/所在天体）不能作为断言证据"""
        v = self._make_validator()
        assert v._check_claim_relation_match(
            "嫦娥六号采集样品2000克",
            {"subject": "嫦娥六号", "predicate": "得名自", "object": "嫦娥"},
        ) == 0.0
        assert v._check_claim_relation_match(
            "着陆点位于月球背面南极-艾特肯盆地",
            {"subject": "南极-艾特肯盆地", "predicate": "所在天体", "object": "月球"},
        ) == 0.0

    def test_substring_object_not_strong_match(self):
        """对象是 claim 内更长词的子串（嫦娥 ⊂ 嫦娥六号）不算独立命中"""
        v = self._make_validator()
        # claim 无「嫦娥」独立出现，只是「嫦娥六号」的一部分
        score = v._check_claim_relation_match(
            "嫦娥六号于2015年发射",
            {"subject": "嫦娥六号", "predicate": "得名自", "object": "嫦娥"},
        )
        # 弱关系已被过滤为 0；即便不过滤，子串也不该强匹配
        assert score < 0.5

    def test_year_conflict_suppressed(self):
        """年份矛盾：claim 说 2015 发射，Wikidata 记录 2024 → 矛盾压制为 0"""
        v = self._make_validator()
        score = v._check_claim_relation_match(
            "嫦娥六号于2015年发射",
            {"subject": "嫦娥六号", "predicate": "launch date", "object": "2024-05-03"},
        )
        assert score == 0.0

    def test_year_match_strong(self):
        """年份一致：Wikidata launch date 2024 → claim 2024 → 强证据"""
        v = self._make_validator()
        score = v._check_claim_relation_match(
            "嫦娥六号于2024年5月3日发射",
            {"subject": "嫦娥六号", "predicate": "launch date", "object": "2024-05-03T00:00:00Z"},
        )
        assert score >= 0.8

    def test_entity_extraction_uses_provided_entities(self):
        """调用方提供的实体即使不在 claim 字面也要采纳（任务历时53天 → 嫦娥六号）"""
        v = self._make_validator()
        matched = v._extract_entities_from_claim("任务历时53天", ["嫦娥六号"])
        assert "嫦娥六号" in matched

    def test_combine_signals_single_academic_no_wiki(self):
        """单路 academic 强证据 + wd/wp 全 unverified → 低置信 partial（荒谬断言防护）"""
        from src.verification.external_validator import ExternalValidator
        v = ExternalValidator.__new__(ExternalValidator)
        wd = {"status": "unverified", "confidence": 0.0, "evidence": ""}
        wp = {"status": "unverified", "confidence": 0.0, "evidence": ""}
        ac = {"status": "verified", "confidence": 0.76, "evidence": "学术(title): 中国月球探测促进月球与行星科学创新发展"}
        status, conf, _ = v._combine_signals(wd, wp, ac)
        assert status == "partial"
        assert conf <= 0.5

    def test_combine_signals_wiki_plus_academic_verified(self):
        """wd+academic 双路强证据 → verified 高置信"""
        from src.verification.external_validator import ExternalValidator
        v = ExternalValidator.__new__(ExternalValidator)
        wd = {"status": "verified", "confidence": 0.88, "evidence": "wd evidence"}
        wp = {"status": "unverified", "confidence": 0.0, "evidence": ""}
        ac = {"status": "verified", "confidence": 0.83, "evidence": "ac evidence"}
        status, conf, _ = v._combine_signals(wd, wp, ac)
        assert status == "verified"
        assert conf >= 0.9

    def test_numbers_overlap(self):
        """数值断言重合检测：1935.3 精确命中"""
        from src.verification.external_validator import _numbers_overlap
        r = _numbers_overlap("采集月球背面样品约1935.3克", "嫦娥六号采集了1935.3克月球样品")
        assert r["hit"] is True
        assert "1935.3" in r["matched"]

    def test_numbers_no_overlap(self):
        """数值不一致（2000 vs 1935.3）不命中"""
        from src.verification.external_validator import _numbers_overlap
        r = _numbers_overlap("采集样品约2000克", "嫦娥六号采集了1935.3克月球样品")
        assert r["hit"] is False


class TestRagPartialCountsAsSupport:
    """RAG partial 计为支持信号（2026-09-01 修复：置信度 0.85 的 partial 不再被投票打成 UNVERIFIED）"""

    def test_rag_partial_single_support(self):
        """RAG partial 高置信 + KG/External unverified → PARTIALLY_VERIFIED 非 UNVERIFIED"""
        from src.verification.cross_validator import CrossValidator
        from src.schemas import VerificationStatus
        v = CrossValidator.__new__(CrossValidator)
        status, conf = v._four_way_vote("partial", 0.85, "unverified", 0.0, "unverified", 0.0)
        assert status == VerificationStatus.PARTIALLY_VERIFIED
        assert conf >= 0.6

    def test_rag_partial_with_external_partial(self):
        """RAG partial + External partial 双路支持 → VERIFIED（两路独立信号）"""
        from src.verification.cross_validator import CrossValidator
        from src.schemas import VerificationStatus
        v = CrossValidator.__new__(CrossValidator)
        status, conf = v._four_way_vote("partial", 0.7, "unverified", 0.0, "partial", 0.5)
        assert status == VerificationStatus.VERIFIED
        assert conf >= 0.6

    def test_rag_unverified_still_unverified(self):
        """RAG 真 unverified 仍保持 UNVERIFIED（不虚增）"""
        from src.verification.cross_validator import CrossValidator
        from src.schemas import VerificationStatus
        v = CrossValidator.__new__(CrossValidator)
        status, conf = v._four_way_vote("unverified", 0.1, "unverified", 0.0, "unverified", 0.0)
        assert status == VerificationStatus.UNVERIFIED
