"""
云观星传 - 校验路由（/api/verify）与知识图谱路由（/api/kg）单元测试
（Mock 校验器/向量库，KG 用仓库内置图数据）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def _vr(claim="测试断言", status="verified", confidence=0.85):
    """构造 mock 的 VerificationResult（带 model_dump）"""
    m = MagicMock()
    m.model_dump.return_value = {
        "claim": claim,
        "status": status,
        "confidence": confidence,
        "rag_evidence": "",
        "kg_match": None,
        "cross_source_agreement": None,
        "notes": "",
    }
    return m


class TestVerifyClaimEndpoint:
    """POST /api/verify/claim 测试"""

    def test_claim_verified(self, client):
        with patch('api.routes.verify.CrossValidator') as MockV:
            MockV.return_value.cross_validate_claim.return_value = _vr()
            resp = client.post("/api/verify/claim", json={"claim": "嫦娥六号于2024年发射", "entities": ["嫦娥六号"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        MockV.return_value.cross_validate_claim.assert_called_once_with(
            "嫦娥六号于2024年发射", entities=["嫦娥六号"])

    def test_claim_without_entities(self, client):
        """entities 可选"""
        with patch('api.routes.verify.CrossValidator') as MockV:
            MockV.return_value.cross_validate_claim.return_value = _vr(status="unverified", confidence=0.1)
            resp = client.post("/api/verify/claim", json={"claim": "未知断言"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "unverified"


class TestVerifyBatchEndpoint:
    """POST /api/verify/batch 测试"""

    def test_batch_with_summary(self, client):
        with patch('api.routes.verify.CrossValidator') as MockV:
            validator = MockV.return_value
            validator.cross_validate_claim.side_effect = [
                _vr("断言1", "verified", 0.9),
                _vr("断言2", "unverified", 0.1),
            ]
            validator.get_validation_summary.return_value = {"total": 2, "verified": 1}
            # batch 内部将 dict 重建为 VerificationResult，需 mock 其构造
            resp = client.post("/api/verify/batch", json={"claims": ["断言1", "断言2"]})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["summary"] == {"total": 2, "verified": 1}

    def test_batch_empty(self, client):
        with patch('api.routes.verify.CrossValidator') as MockV:
            MockV.return_value.cross_validate_claim.return_value = _vr()
            MockV.return_value.get_validation_summary.return_value = {"total": 0}
            resp = client.post("/api/verify/batch", json={"claims": []})
        assert resp.status_code == 200
        assert resp.json()["results"] == []


class TestVerifyReportEndpoint:
    """GET /api/verify/report 测试"""

    def test_report_exists(self, client, tmp_path, monkeypatch):
        report_file = tmp_path / "verification_report.json"
        report_file.write_text(json.dumps({"topic": "嫦娥六号", "summary": {"total_claims": 3}}), encoding="utf-8")
        # verify.py 内部用 Path(__file__) 定位，patch 其文件存在性判断
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', MagicMock(return_value=report_file.open(encoding='utf-8'))):
            resp = client.get("/api/verify/report")
        assert resp.status_code == 200

    def test_report_missing_message(self, client, monkeypatch):
        """无报告时应返回提示信息（patch Path 使文件不存在）"""
        import api.routes.verify as verify_mod
        # 自闭合 mock：parent 链与 / 运算符都返回自身，exists 恒为 False
        fake_path = MagicMock()
        fake_path.parent = fake_path
        fake_path.__truediv__.return_value = fake_path
        fake_path.exists.return_value = False
        monkeypatch.setattr(verify_mod, "Path", lambda *a, **k: fake_path)
        resp = client.get("/api/verify/report")
        assert resp.status_code == 200
        assert "暂无校验报告" in resp.json()["message"]


class TestVerifyStatusEndpoint:
    """GET /api/verify/status 测试"""

    def test_status_reports_stores(self, client):
        with patch('src.knowledge.vector_store.get_vector_store') as mock_vs, \
             patch('src.knowledge.kg_builder.get_knowledge_graph') as mock_kg:
            mock_vs.return_value.index = None
            mock_graph = MagicMock()
            mock_graph.number_of_nodes.return_value = 100
            mock_graph.number_of_edges.return_value = 200
            mock_kg.return_value.G = mock_graph
            resp = client.get("/api/verify/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vector_store"]["initialized"] is False
        assert data["vector_store"]["vector_count"] == 0
        assert data["knowledge_graph"]["initialized"] is True
        assert data["knowledge_graph"]["entity_count"] == 100
        assert data["knowledge_graph"]["relation_count"] == 200


class TestKGEndpoints:
    """知识图谱路由测试（使用仓库内置 KG 数据）"""

    def test_stats(self, client):
        resp = client.get("/api/kg/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entities"] > 0
        assert data["total_relations"] > 0
        assert isinstance(data["entity_types"], dict)

    def test_entity_found(self, client):
        resp = client.get("/api/kg/entity/嫦娥六号")
        assert resp.status_code == 200
        assert "error" not in resp.json()

    def test_entity_not_found(self, client):
        resp = client.get("/api/kg/entity/绝对不存在的实体XYZ")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_related_entities(self, client):
        resp = client.get("/api/kg/related/嫦娥六号?depth=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "嫦娥六号"
        assert isinstance(data["related"], list)

    def test_related_depth_validation(self, client):
        """depth 超出 [1,3] 应 422"""
        resp = client.get("/api/kg/related/嫦娥六号?depth=9")
        assert resp.status_code == 422

    def test_subgraph(self, client):
        resp = client.get("/api/kg/subgraph/嫦娥六号")
        assert resp.status_code == 200

    def test_search_by_keyword(self, client):
        """关键词搜索应命中含关键词的实体"""
        resp = client.get("/api/kg/search?q=嫦娥")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        assert any("嫦娥" in r["name"] for r in data["results"])

    def test_search_no_match(self, client):
        resp = client.get("/api/kg/search?q=zzzz不存在的关键词zzzz")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_search_missing_query_422(self, client):
        """缺 q 参数应 422"""
        resp = client.get("/api/kg/search")
        assert resp.status_code == 422

    def test_components_summary(self, client):
        """components 应返回连通分量摘要（不含大 nodes 列表）"""
        resp = client.get("/api/kg/components")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_components"] >= 1
        for comp in data["components"]:
            assert "nodes" not in comp  # 不应包含节点大列表
            assert "node_count" in comp
