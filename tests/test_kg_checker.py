"""
云观星传 - 知识图谱校验器（KGChecker）单元测试
覆盖批量关系校验、实体存在性、科学事实整体校验、冲突检查与异常降级
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
def kg_checker():
    """创建 KGChecker 实例（使用仓库内置 KG 数据）"""
    from src.verification.kg_checker import KGChecker
    return KGChecker()


class TestVerifyRelations:
    """批量关系校验测试"""

    def test_batch_returns_per_relation(self, kg_checker):
        """每条关系应返回一个结果"""
        relations = [
            {"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号"},
            {"subject": "不存在的实体A", "predicate": "managed_by", "object": "不存在的实体B"},
        ]
        results = kg_checker.verify_relations(relations)
        assert len(results) == 2
        for r in results:
            assert r["status"] in ("verified", "partial", "unverified")
            assert "confidence" in r

    def test_empty_relations(self, kg_checker):
        assert kg_checker.verify_relations([]) == []

    def test_missing_fields_tolerated(self, kg_checker):
        """缺字段的关系不应崩溃"""
        results = kg_checker.verify_relations([{}])
        assert len(results) == 1
        assert results[0]["status"] in ("verified", "partial", "unverified")


class TestVerifyEntitiesExist:
    """实体存在性检查测试"""

    def test_existing_and_missing_split(self, kg_checker):
        """应正确区分存在/缺失实体"""
        result = kg_checker.verify_entities_exist(["嫦娥六号", "绝对不存在的实体XYZ"])
        assert "嫦娥六号" in result["existing"]
        assert "绝对不存在的实体XYZ" in result["missing"]
        assert result["total"] == 2
        assert abs(result["coverage_rate"] - 0.5) < 1e-9

    def test_empty_entities(self, kg_checker):
        result = kg_checker.verify_entities_exist([])
        assert result["total"] == 0
        assert result["coverage_rate"] == 0
        assert result["existing"] == []
        assert result["missing"] == []


class TestVerifyScienceFacts:
    """科学事实数据整体校验测试"""

    def test_full_facts_check(self, kg_checker):
        """应同时校验实体与关系并输出统计"""
        facts = {
            "entities": [
                {"name": "嫦娥六号"},
                {"name": "绝对不存在的实体XYZ"},
            ],
            "relations": [
                {"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号"},
            ],
        }
        result = kg_checker.verify_science_facts(facts)
        assert result["entity_check"]["total"] == 2
        assert len(result["relation_results"]) == 1
        s = result["summary"]
        assert s["total_relations"] == 1
        assert s["verified"] + s["partial"] + s["unverified"] == 1
        assert abs(s["entity_coverage"] - 0.5) < 1e-9

    def test_empty_facts(self, kg_checker):
        result = kg_checker.verify_science_facts({})
        assert result["entity_check"]["total"] == 0
        assert result["summary"]["total_relations"] == 0


class TestVerifyTripleException:
    """verify_triple 异常降级测试"""

    def test_kg_exception_returns_unverified(self):
        """底层 KG 异常时应降级为 unverified 而非抛出"""
        from src.verification.kg_checker import KGChecker
        checker = KGChecker()
        with patch.object(checker.kg, 'verify_triple', side_effect=RuntimeError("图数据损坏")):
            result = checker.verify_triple("A", "rel", "B")
        assert result["status"] == "unverified"
        assert result["confidence"] == 0.0
        assert "校验异常" in result["message"]


class TestCheckForConflicts:
    """矛盾关系检查测试"""

    def test_conflict_edge_detected(self, kg_checker):
        """competes_with/conflicts_with 边应报冲突"""
        # 构造 mock 图：G[主体][客体] 双层下标返回边数据（模拟 NetworkX AtlasView）
        mock_graph = MagicMock()
        inner = MagicMock()
        inner.__getitem__.return_value = {"predicate": "competes_with"}
        mock_graph.__getitem__.return_value = inner
        mock_graph.has_edge.return_value = True
        with patch.object(kg_checker.kg, 'G', mock_graph):
            result = kg_checker.check_for_conflicts("实体A", "实体B")
        assert result["has_conflict"] is True
        assert result["conflict_type"] == "competes_with"

    def test_normal_edge_no_conflict(self, kg_checker):
        """普通关系边不算冲突"""
        mock_graph = MagicMock()
        inner = MagicMock()
        inner.__getitem__.return_value = {"predicate": "launched_by"}
        mock_graph.__getitem__.return_value = inner
        mock_graph.has_edge.return_value = True
        with patch.object(kg_checker.kg, 'G', mock_graph):
            result = kg_checker.check_for_conflicts("嫦娥六号", "长征五号")
        assert result["has_conflict"] is False

    def test_no_edge_no_conflict(self, kg_checker):
        """无边即无冲突"""
        mock_graph = MagicMock()
        mock_graph.has_edge.return_value = False
        with patch.object(kg_checker.kg, 'G', mock_graph):
            result = kg_checker.check_for_conflicts("A", "B")
        assert result["has_conflict"] is False

    def test_exception_degrades(self, kg_checker):
        """检查异常时应安全返回无冲突"""
        mock_graph = MagicMock()
        mock_graph.has_edge.side_effect = RuntimeError("boom")
        with patch.object(kg_checker.kg, 'G', mock_graph):
            result = kg_checker.check_for_conflicts("A", "B")
        assert result["has_conflict"] is False
        assert "检查异常" in result["message"]


class TestGetRelatedContext:
    """相关上下文获取测试"""

    def test_known_entity_returns_list(self, kg_checker):
        context = kg_checker.get_related_context("嫦娥六号", depth=1)
        assert isinstance(context, list)

    def test_unknown_entity_empty(self, kg_checker):
        context = kg_checker.get_related_context("完全不存在的实体XYZ", depth=1)
        assert not context
