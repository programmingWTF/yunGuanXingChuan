"""
云观星传 - Wikidata 知识图谱扩充模块测试

覆盖不依赖网络的纯逻辑：QID→类型映射、谓词归一化。
（搜索/SPARQL 联网部分不在此测试）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge.wikidata_enricher import TYPE_MAPPING, WikidataEnricher


class TestTypeMapping:
    def test_key_mappings_present(self):
        # 本项目核心实体类型都应出现在映射表
        for qid in ("Q21198", "Q40218", "Q11424", "Q4830453", "Q5", "Q1656682"):
            assert qid in TYPE_MAPPING, f"缺少常见类型 {qid}"

    def test_mapping_values_valid(self):
        valid_types = {"mission", "body", "technology", "organization", "person", "event"}
        for v in TYPE_MAPPING.values():
            assert v in valid_types, f"非法类型 {v}"


class TestNormalizePredicate:
    def setup_method(self):
        self.enricher = WikidataEnricher()

    def test_zh_predicate(self):
        assert self.enricher._normalize_predicate("属于") == "part_of"
        assert self.enricher._normalize_predicate("发射日期") == "launched_on"
        assert self.enricher._normalize_predicate("合作方") == "collaborates_with"

    def test_en_predicate_snake_case(self):
        assert self.enricher._normalize_predicate("part of") == "part_of"
        assert self.enricher._normalize_predicate("launch date") == "launch_date"
        assert self.enricher._normalize_predicate("Started-by") == "started_by"

    def test_empty_or_unknown(self):
        assert self.enricher._normalize_predicate("") == "related_to"
        # 全符号输入归一化后为空 → 兜底 related_to
        assert self.enricher._normalize_predicate("!!!") == "related_to"
