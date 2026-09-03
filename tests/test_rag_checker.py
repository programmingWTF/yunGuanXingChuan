"""
云观星传 - RAG 校验器单元测试
覆盖 LLM 语义校验判定分级、语义异常回退向量相似度、批量/科学事实校验与摘要统计
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def checker():
    """创建带 mock vector_store 与 llm_client 的 RAGChecker"""
    with patch('src.verification.rag_checker.get_vector_store') as mock_vs:
        vs = MagicMock()
        mock_vs.return_value = vs
        from src.verification.rag_checker import RAGChecker
        llm = MagicMock()
        c = RAGChecker(similarity_threshold=0.5, llm_client=llm)
        c.vector_store = vs
        c.llm_client = llm
        yield c


def _search_results(n=2):
    """构造 vector_store.search 返回"""
    return [
        {"text": "嫦娥六号2024年5月发射" * 3, "score": 0.9, "metadata": {"source": "change6_facts"}},
        {"text": "月球背面采样返回", "score": 0.7, "metadata": {"source": "cnsa"}},
    ][:n]


class TestVerifyClaimSemantic:
    """LLM 语义校验测试"""

    def test_no_results_unverified(self, checker):
        checker.vector_store.search.return_value = []
        r = checker.verify_claim_semantic("某断言")
        assert r["status"] == "unverified"
        assert r["confidence"] == 0.0
        assert "未找到相关文档" in r["message"]

    def test_consistent_high_confidence_supported(self, checker):
        """consistent=true 且 conf≥0.7 → supported"""
        checker.vector_store.search.return_value = _search_results()
        checker.llm_client.chat_json.return_value = {
            "consistent": True, "confidence": 0.9,
            "evidence_summary": "与参考一致", "key_sources": ["change6_facts"], "notes": "ok",
        }
        r = checker.verify_claim_semantic("嫦娥六号2024年发射")
        assert r["status"] == "supported"
        assert r["confidence"] == 0.9
        assert r["semantic_check"] is True
        assert r["evidence"] == "与参考一致"

    def test_inconsistent_high_confidence_partial(self, checker):
        """修复点：consistent=false 但 conf≥0.6 应判 partial 而非 unverified"""
        checker.vector_store.search.return_value = _search_results()
        checker.llm_client.chat_json.return_value = {
            "consistent": False, "confidence": 0.75,
            "evidence_summary": "核心一致细节无法验证", "key_sources": [], "notes": "",
        }
        r = checker.verify_claim_semantic("某断言")
        assert r["status"] == "partial"

    def test_consistent_low_confidence_partial(self, checker):
        """consistent=true 但 conf<0.7 → partial"""
        checker.vector_store.search.return_value = _search_results()
        checker.llm_client.chat_json.return_value = {
            "consistent": True, "confidence": 0.5, "evidence_summary": "s", "key_sources": [], "notes": "",
        }
        r = checker.verify_claim_semantic("某断言")
        assert r["status"] == "partial"

    def test_inconsistent_low_confidence_unverified(self, checker):
        checker.vector_store.search.return_value = _search_results()
        checker.llm_client.chat_json.return_value = {
            "consistent": False, "confidence": 0.3, "evidence_summary": "s", "key_sources": [], "notes": "",
        }
        r = checker.verify_claim_semantic("某断言")
        assert r["status"] == "unverified"

    def test_missing_fields_default(self, checker):
        """LLM 返回缺字段时应使用默认值"""
        checker.vector_store.search.return_value = _search_results()
        checker.llm_client.chat_json.return_value = {}
        r = checker.verify_claim_semantic("某断言")
        assert r["status"] in ("partial", "unverified")  # consistent=False conf=0.5 → partial
        assert r["confidence"] == 0.5

    def test_prompt_contains_search_sources(self, checker):
        """注入 LLM 的 prompt 应包含检索来源"""
        checker.vector_store.search.return_value = _search_results(1)
        checker.llm_client.chat_json.return_value = {"consistent": True, "confidence": 0.8,
                                                     "evidence_summary": "", "key_sources": [], "notes": ""}
        checker.verify_claim_semantic("嫦娥六号")
        user_prompt = checker.llm_client.chat_json.call_args.kwargs["user_prompt"]
        assert "嫦娥六号" in user_prompt
        assert "change6_facts" in user_prompt  # 来源拼进参考文本


class TestVerifyClaim:
    """verify_claim 主入口测试"""

    def test_semantic_success(self, checker):
        """语义校验成功直接返回"""
        with patch.object(checker, 'verify_claim_semantic') as mock_sem:
            mock_sem.return_value = {"claim": "x", "status": "supported", "confidence": 0.9,
                                     "evidence": "e", "source": "s", "message": "m"}
            r = checker.verify_claim("x")
        assert r["status"] == "supported"
        mock_sem.assert_called_once_with("x")

    def test_semantic_failure_falls_back_to_vector(self, checker):
        """语义校验异常应回退向量相似度"""
        with patch.object(checker, 'verify_claim_semantic', side_effect=RuntimeError("LLM down")):
            checker.vector_store.verify_claim.return_value = {
                "status": "supported", "confidence": 0.8, "evidence": "向量证据",
                "source": "s", "message": "找到支持性证据",
            }
            r = checker.verify_claim("x")
        assert r["status"] == "supported"
        assert r["confidence"] == 0.8
        checker.vector_store.verify_claim.assert_called_once_with("x", threshold=0.5)

    def test_vector_failure_top_level_unverified(self, checker):
        """语义与向量都失败 → 顶层降级"""
        with patch.object(checker, 'verify_claim_semantic', side_effect=RuntimeError("LLM down")):
            checker.vector_store.verify_claim.side_effect = RuntimeError("vector down")
            r = checker.verify_claim("x")
        assert r["status"] == "unverified"
        assert r["confidence"] == 0.0
        assert "校验异常" in r["message"]

    def test_vector_partial_mapped(self, checker):
        """向量 partial 结果应正确映射"""
        with patch.object(checker, 'verify_claim_semantic', side_effect=RuntimeError("LLM down")):
            checker.vector_store.verify_claim.return_value = {
                "status": "partial", "confidence": 0.45, "evidence": "部分相关",
                "source": "", "message": "找到部分相关证据",
            }
            r = checker.verify_claim("x")
        assert r["status"] == "partial"


class TestVerifyClaimsBatchAndFacts:
    """批量与科学事实校验测试"""

    def test_batch(self, checker):
        with patch.object(checker, 'verify_claim', side_effect=lambda c: {"claim": c, "status": "supported"}) as mv:
            results = checker.verify_claims_batch(["a", "b", "c"])
        assert len(results) == 3
        assert mv.call_count == 3

    def test_science_facts_empty(self, checker):
        assert checker.verify_science_facts({"key_facts": []}) == []

    def test_science_facts_batch(self, checker):
        with patch.object(checker, 'verify_claim', side_effect=lambda c: {"claim": c, "status": "supported"}):
            results = checker.verify_science_facts({"topic": "嫦娥六号", "key_facts": ["事实1", "事实2"]})
        assert len(results) == 2
        assert results[0]["claim"] == "事实1"


class TestVerificationSummary:
    """摘要统计测试"""

    def test_empty_results(self, checker):
        assert checker.get_verification_summary([]) == {"total": 0, "verified": 0, "partial": 0, "unverified": 0}

    def test_statistics(self, checker):
        results = [
            {"status": "supported", "confidence": 0.9},
            {"status": "partial", "confidence": 0.6},
            {"status": "unverified", "confidence": 0.1},
        ]
        s = checker.get_verification_summary(results)
        assert s["total"] == 3
        assert s["verified"] == 1
        assert s["partial"] == 1
        assert s["unverified"] == 1
        assert abs(s["verification_rate"] - 1 / 3) < 1e-9
        assert abs(s["avg_confidence"] - 0.5333) < 0.01
