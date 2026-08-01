"""
云观星传 - 知识图谱报告生成器单元测试（数据驱动，不依赖 LLM）
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


class TestKGReportGenerator:
    """知识图谱报告生成器测试"""

    def test_hot_nodes_no_unknown(self):
        """热点节点不应包含 unknown 类型"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["hot_nodes"], "热点节点不应为空"
        for node in report["hot_nodes"]:
            assert node["type"] != "unknown"
            assert node["degree"] > 0

    def test_key_persons_are_persons(self):
        """关键人物应全部为 person 类型"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["key_persons"], "关键人物不应为空"
        for p in report["key_persons"]:
            assert p["type"] == "person"

    def test_organizations_are_organizations(self):
        """机构应全部为 organization 类型"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["organizations"], "机构不应为空"
        for org in report["organizations"]:
            assert org["type"] == "organization"

    def test_topic_relations_have_sources(self):
        """围绕议题的关系应含证据来源"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["relations"], "议题关系不应为空"
        for rel in report["relations"]:
            assert "source" in rel
            assert "confidence" in rel

    def test_evidence_sources_no_wikidata(self):
        """证据来源应排除 wikidata"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["evidence_sources"], "证据来源不应为空"
        for src in report["evidence_sources"]:
            assert src != "wikidata"

    def test_kg_summary_nonempty(self):
        """图谱总览段落非空且含关键词"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "嫦娥六号"})
        assert report["kg_summary"]
        assert "实体" in report["kg_summary"]
        assert "关系" in report["kg_summary"]

    def test_unknown_topic_graceful(self):
        """未知议题应优雅降级，不抛异常"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({"topic": "不存在的议题XYZ123"})
        assert report["topic"] == "不存在的议题XYZ123"
        assert report["kg_summary"]
        assert report["hot_nodes"]

    def test_no_topic_graceful(self):
        """无 topic 时应展示全图统计"""
        from src.agents.kg_report_generator import generate_kg_report
        report = generate_kg_report({})
        assert report["topic"] == ""
        assert report["kg_summary"]
        assert "未在图中找到" in report["kg_summary"]
