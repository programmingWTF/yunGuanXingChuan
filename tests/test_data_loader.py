"""
云观星传 - 数据加载模块单元测试
验证科学数据、媒体语料、受众画像、KG 数据的加载逻辑（使用真实数据文件）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def loader():
    """创建 DataLoader 实例"""
    from src.knowledge.data_loader import DataLoader
    return DataLoader()


class TestLoadScienceFacts:
    """科学事实数据加载"""

    def test_loads_all_facts(self, loader):
        """不指定 topic 应加载全部科学数据"""
        facts = loader.load_science_facts()
        assert isinstance(facts, list)
        assert len(facts) > 0  # data/science/ 目录下有数据文件

    def test_each_fact_has_topic(self, loader):
        """每个科学数据集应有 topic 字段"""
        facts = loader.load_science_facts()
        for fact in facts:
            assert "topic" in fact or "key_facts" in fact

    def test_filter_by_topic(self, loader):
        """按 topic 过滤应只返回匹配项"""
        all_facts = loader.load_science_facts()
        if all_facts:
            first_topic = all_facts[0].get("topic", "")
            if first_topic:
                filtered = loader.load_science_facts(first_topic)
                assert all(f.get("topic") == first_topic for f in filtered)

    def test_nonexistent_topic_returns_empty(self, loader):
        """不存在的 topic 应返回空列表"""
        facts = loader.load_science_facts("完全不存在的议题XYZ")
        assert facts == []


class TestLoadMediaReports:
    """媒体报道数据加载"""

    def test_loads_all_reports(self, loader):
        """不指定国家应加载全部媒体数据"""
        reports = loader.load_media_reports()
        assert isinstance(reports, list)
        assert len(reports) > 0  # data/media/ 目录下有数据

    def test_reports_have_fields(self, loader):
        """报道应包含基本字段"""
        reports = loader.load_media_reports()
        if reports:
            report = reports[0]
            # 至少应有部分标准字段
            has_fields = any(k in report for k in ["title", "source", "country", "content"])
            assert has_fields

    def test_filter_by_country(self, loader):
        """按国家过滤"""
        from config.settings import MEDIA_DIR
        # 获取第一个可用的国家目录
        countries = [d.name for d in MEDIA_DIR.iterdir() if d.is_dir()]
        if countries:
            reports = loader.load_media_reports(countries[0])
            assert isinstance(reports, list)

    def test_nonexistent_country_returns_empty(self, loader):
        """不存在的国家应返回空列表"""
        reports = loader.load_media_reports("不存在的国家XYZ")
        assert reports == []


class TestLoadAudienceProfiles:
    """受众画像加载"""

    def test_loads_profiles(self, loader):
        """应加载所有受众画像"""
        profiles = loader.load_audience_profiles()
        assert isinstance(profiles, dict)
        assert len(profiles) > 0  # data/audience_profiles/ 有数据

    def test_profile_key_is_filename_stem(self, loader):
        """画像 key 应为文件名（不含扩展名）"""
        profiles = loader.load_audience_profiles()
        # 已知有 domestic_youth, global_south_public, us_policy_elite
        expected_keys = {"domestic_youth", "global_south_public", "us_policy_elite"}
        assert expected_keys.issubset(set(profiles.keys()))

    def test_profiles_are_dicts(self, loader):
        """每个画像应为字典"""
        profiles = loader.load_audience_profiles()
        for key, profile in profiles.items():
            assert isinstance(profile, dict), f"{key} 不是字典"


class TestLoadKGData:
    """知识图谱数据加载"""

    def test_loads_entities_and_relations(self, loader):
        """应加载实体和关系"""
        kg = loader.load_kg_data()
        assert "entities" in kg
        assert "relations" in kg
        assert len(kg["entities"]) > 0
        assert len(kg["relations"]) > 0

    def test_entities_have_name(self, loader):
        """实体应有 name 字段"""
        kg = loader.load_kg_data()
        for entity in kg["entities"][:5]:
            assert "name" in entity


class TestMediaSummary:
    """媒体数据统计摘要"""

    def test_summary_structure(self, loader):
        """摘要应按国家分组"""
        summary = loader.get_media_summary()
        assert isinstance(summary, dict)
        for country, data in summary.items():
            assert "total" in data
            assert "frameworks" in data
            assert "sentiments" in data
            assert "sources" in data
            assert data["total"] > 0


class TestGetAllDataForTopic:
    """获取议题全部相关数据"""

    def test_returns_all_sections(self, loader):
        """应返回所有数据分区"""
        data = loader.get_all_data_for_topic("嫦娥六号")
        assert "topic" in data
        assert "science_facts" in data
        assert "media_reports" in data
        assert "audience_profiles" in data
        assert "kg_data" in data
        assert data["topic"] == "嫦娥六号"


class TestSingleton:
    """全局单例"""

    def test_get_data_loader_returns_same_instance(self):
        """多次调用应返回同一实例"""
        from src.knowledge.data_loader import get_data_loader
        a = get_data_loader()
        b = get_data_loader()
        assert a is b
