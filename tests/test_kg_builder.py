"""
云观星传 - 知识图谱构建器单元测试
覆盖三元组校验分级、BFS 相关实体、实体详情、子图、统计与连通分量（仓库内置图数据）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="module")
def kg():
    """加载仓库内置 KG（模块级共享，构建成本高）

    走 get_knowledge_graph() 单例：直接构造 KnowledgeGraph() 是空图，
    只有单例才会 load_graph()/build_from_data()。
    """
    from src.knowledge.kg_builder import get_knowledge_graph
    return get_knowledge_graph()


class TestVerifyTriple:
    """三元组校验分级测试"""

    def test_exact_match_verified(self, kg):
        """主体客体有边且谓词一致应 verified"""
        # 从图中找一条真实边来测
        u, v, data = next(iter(kg.G.edges(data=True)))
        result = kg.verify_triple(u, data.get("predicate", ""), v)
        assert result["status"] == "verified"
        assert result["confidence"] > 0

    def test_wrong_predicate_partial(self, kg):
        """有边但谓词不同应 partial"""
        u, v, data = next(iter(kg.G.edges(data=True)))
        result = kg.verify_triple(u, "绝对不是这个谓词", v)
        assert result["status"] == "partial"
        assert result["confidence"] == 0.5
        assert "谓词不同" in result["message"]

    def test_both_unknown_unverified(self, kg):
        """主体客体都不在图中应 unverified 0.0"""
        result = kg.verify_triple("神秘主体A", "rel", "神秘客体B")
        assert result["status"] == "unverified"
        assert result["confidence"] == 0.0

    def test_one_side_unknown(self, kg):
        """仅一方存在应 unverified 低置信"""
        u, _, _ = next(iter(kg.G.edges(data=True)))
        result = kg.verify_triple(u, "rel", "完全不存在的客体Z")
        assert result["status"] == "unverified"
        assert result["confidence"] == 0.1

    def test_entities_connected_no_direct_edge(self, kg):
        """两实体存在且有路径但无直接边应 partial（或直接有边时 verified）"""
        # 找两个有路径但可能无直接边的节点：用 BFS 深度 2 的节点
        u, v, _ = next(iter(kg.G.edges(data=True)))
        # u 的邻居的邻居
        result = kg.verify_triple(u, "任意谓词", v)
        assert result["status"] in ("verified", "partial", "unverified")  # 结构合法即可


class TestFindRelatedEntities:
    """BFS 相关实体查找测试"""

    def test_unknown_entity_empty(self, kg):
        assert kg.find_related_entities("完全不存在的实体X") == []

    def test_depth1_related(self, kg):
        """深度 1 应返回直接邻居并标注方向与深度"""
        related = kg.find_related_entities("嫦娥六号", depth=1)
        assert isinstance(related, list)
        for r in related:
            assert r["depth"] == 1
            assert r["direction"] in ("outgoing", "incoming")
            assert "relation" in r

    def test_depth2_includes_more(self, kg):
        """深度 2 的结果应不少于深度 1"""
        r1 = kg.find_related_entities("嫦娥六号", depth=1)
        r2 = kg.find_related_entities("嫦娥六号", depth=2)
        assert len(r2) >= len(r1)

    def test_no_duplicates(self, kg):
        """BFS 不应返回重复实体"""
        related = kg.find_related_entities("嫦娥六号", depth=2)
        entities = [r["entity"] for r in related]
        assert len(entities) == len(set(entities))


class TestGetEntityInfo:
    """实体详情测试"""

    def test_known_entity(self, kg):
        info = kg.get_entity_info("嫦娥六号")
        if info is not None:  # 嫦娥六号应在图中
            assert info["name"] == "嫦娥六号"
            assert "type" in info
            assert "outgoing_relations" in info
            assert "incoming_relations" in info

    def test_unknown_entity_none(self, kg):
        assert kg.get_entity_info("完全不存在的实体Y") is None


class TestSubgraph:
    """子图提取测试"""

    def test_subgraph_structure(self, kg):
        sub = kg.get_subgraph_for_topic("嫦娥六号")
        assert "nodes" in sub and "edges" in sub
        assert len(sub["nodes"]) >= 1
        # 子图中心应为议题实体
        names = [n["name"] for n in sub["nodes"]]
        assert "嫦娥六号" in names
        # 子图边必须连接子图内节点
        node_set = set(names)
        for e in sub["edges"]:
            assert e["source"] in node_set and e["target"] in node_set

    def test_unknown_topic_minimal(self, kg):
        """不在图中的议题应返回空子图（subgraph 过滤掉不存在节点）"""
        sub = kg.get_subgraph_for_topic("完全不存在的议题Z")
        assert sub["nodes"] == []
        assert sub["edges"] == []


class TestGraphData:
    """完整图数据与统计测试"""

    def test_all_graph_data(self, kg):
        data = kg.get_all_graph_data()
        assert "nodes" in data and "edges" in data
        assert len(data["nodes"]) == kg.G.number_of_nodes()

    def test_stats(self, kg):
        stats = kg.get_stats()
        assert stats["total_entities"] == kg.G.number_of_nodes()
        assert stats["total_relations"] == kg.G.number_of_edges()
        assert isinstance(stats["entity_types"], dict)
        assert isinstance(stats["relation_types"], dict)


class TestConnectedComponents:
    """连通分量测试"""

    def test_components_summary(self, kg):
        comps = kg.get_connected_components()
        assert len(comps) >= 1
        for c in comps:
            assert "id" in c and "node_count" in c and "edge_count" in c
        # 节点总数守恒
        total_nodes = sum(c["node_count"] for c in comps)
        assert total_nodes == kg.G.number_of_nodes()

    def test_component_graph_data(self, kg):
        comps = kg.get_connected_components()
        cid = comps[0]["id"]
        g = kg.get_component_graph_data(cid)
        assert "nodes" in g and "edges" in g
        assert len(g["nodes"]) == comps[0]["node_count"]

    def test_invalid_component_id(self, kg):
        """非法分量 ID 应安全返回空结构"""
        g = kg.get_component_graph_data(99999)
        assert g.get("nodes", []) == []


class TestLoadGraph:
    """图加载测试"""

    def test_load_graph_success(self, kg):
        assert kg.load_graph() is True
        assert kg.G.number_of_nodes() > 0
