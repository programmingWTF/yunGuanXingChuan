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


# ══════════════════════════════════════════════════════════════
# 以下为补充测试：HTTP 路径 / 主流程 / 落盘合并（Mock 网络，不依赖外网）
# ══════════════════════════════════════════════════════════════
import pytest
from unittest.mock import patch, MagicMock
import json as _json


@pytest.fixture
def enricher():
    """带 mock httpx 客户端的扩充器"""
    e = WikidataEnricher()
    e.client = MagicMock()
    yield e
    e.client.close()


def _resp(json_data):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = json_data
    return r


class TestGetWithRetry:
    """带重试 GET 测试"""

    def test_success_first_try(self, enricher):
        enricher.client.get.return_value = _resp({})
        resp = enricher._get_with_retry("http://x", {})
        assert resp is enricher.client.get.return_value

    def test_retries_then_gives_up(self, enricher):
        """网络异常应重试 max_retries 次后返回 None"""
        # 异常类从被测模块命名空间取：与 _get_with_retry 的 except 子句同源，
        # 免疫其他测试文件运行期对 sys.modules['httpx'] 的 mock 污染
        import src.knowledge.wikidata_enricher as we_mod
        enricher.client.get.side_effect = we_mod.httpx.ConnectError("refused")
        with patch('src.knowledge.wikidata_enricher.time.sleep'):
            assert enricher._get_with_retry("http://x", {}) is None
        assert enricher.client.get.call_count == enricher.max_retries

    def test_retry_succeeds_second_attempt(self, enricher):
        """第一次失败第二次成功应返回响应"""
        import src.knowledge.wikidata_enricher as we_mod
        good = _resp({"ok": 1})
        enricher.client.get.side_effect = [we_mod.httpx.ReadError("reset"), good]
        with patch('src.knowledge.wikidata_enricher.time.sleep'):
            resp = enricher._get_with_retry("http://x", {})
        assert resp is good
        assert enricher.client.get.call_count == 2

    def test_non_retryable_exception_breaks(self, enricher):
        """不可重试异常应立即返回 None（只调用一次）"""
        enricher.client.get.side_effect = ValueError("bad param")
        assert enricher._get_with_retry("http://x", {}) is None
        assert enricher.client.get.call_count == 1


class TestSearchEntities:
    """实体搜索测试"""

    def test_parses_search_results(self, enricher):
        enricher.client.get.return_value = _resp({
            "search": [
                {"id": "Q1", "label": "嫦娥六号", "description": "月球采样任务"},
                {"id": "", "label": "无ID"},       # 无 qid 跳过
                {"id": "Q3", "label": ""},          # 无 label 跳过
            ]
        })
        results = enricher.search_entities("嫦娥六号")
        assert len(results) == 1
        assert results[0]["qid"] == "Q1"
        assert results[0]["label"] == "嫦娥六号"
        assert results[0]["type"] == "mission"  # 默认类型

    def test_network_failure_returns_empty(self, enricher):
        import src.knowledge.wikidata_enricher as we_mod
        enricher.client.get.side_effect = we_mod.httpx.ConnectError("down")
        with patch('src.knowledge.wikidata_enricher.time.sleep'):
            assert enricher.search_entities("嫦娥六号") == []


class TestGetEntityLabel:
    """实体标签获取测试"""

    def test_prefers_zh_label(self, enricher):
        enricher.client.get.return_value = _resp({
            "entities": {"Q1": {"labels": {"zh": {"value": "嫦娥六号"}, "en": {"value": "Chang'e 6"}}}}
        })
        assert enricher._get_entity_label("Q1") == "嫦娥六号"

    def test_falls_back_to_en(self, enricher):
        enricher.client.get.return_value = _resp({
            "entities": {"Q1": {"labels": {"en": {"value": "Chang'e 6"}}}}
        })
        assert enricher._get_entity_label("Q1") == "Chang'e 6"

    def test_no_labels_returns_empty(self, enricher):
        enricher.client.get.return_value = _resp({"entities": {"Q1": {}}})
        assert enricher._get_entity_label("Q1") == ""


class TestGetEntityType:
    """P31 实体类型推断测试"""

    def test_mapped_type(self, enricher):
        # Q47107 假设映射为 mission（以 TYPE_MAPPING 实际值为准）
        from src.knowledge.wikidata_enricher import TYPE_MAPPING
        some_type_qid = next(iter(TYPE_MAPPING))
        expected = TYPE_MAPPING[some_type_qid]
        enricher.client.get.return_value = _resp({
            "results": {"bindings": [
                {"type": {"value": f"http://www.wikidata.org/entity/{some_type_qid}"}}
            ]}
        })
        assert enricher._get_entity_type("Q1") == expected

    def test_unmapped_defaults_technology(self, enricher):
        enricher.client.get.return_value = _resp({
            "results": {"bindings": [{"type": {"value": "http://www.wikidata.org/entity/Q999999"}}]}
        })
        assert enricher._get_entity_type("Q1") == "technology"

    def test_network_failure_defaults_technology(self, enricher):
        import src.knowledge.wikidata_enricher as we_mod
        enricher.client.get.side_effect = we_mod.httpx.ConnectError("down")
        with patch('src.knowledge.wikidata_enricher.time.sleep'):
            assert enricher._get_entity_type("Q1") == "technology"


class TestGetEntityRelations:
    """SPARQL 关系查询测试"""

    def test_no_label_returns_empty(self, enricher):
        with patch.object(enricher, '_get_entity_label', return_value=""):
            assert enricher.get_entity_relations("Q1") == []

    def test_parses_relations(self, enricher):
        with patch.object(enricher, '_get_entity_label', return_value="嫦娥六号"):
            enricher.client.get.return_value = _resp({
                "results": {"bindings": [
                    {"predicateLabel": {"value": "发射日期"}, "objectLabel": {"value": "2024-05-03"},
                     "object": {"value": "http://wikidata.org/entity/Qdate"}},
                    {"predicateLabel": {"value": "无对象标签"}, "objectLabel": {"value": ""},
                     "object": {"value": ""}},
                ]}
            })
            rels = enricher.get_entity_relations("Q1")
        assert len(rels) == 1
        assert rels[0]["subject"] == "嫦娥六号"
        assert rels[0]["predicate"] == "launched_on"  # 中文归一化为英文谓词

    def test_network_failure_returns_empty(self, enricher):
        import src.knowledge.wikidata_enricher as we_mod
        with patch.object(enricher, '_get_entity_label', return_value="嫦娥六号"):
            enricher.client.get.side_effect = we_mod.httpx.ConnectError("sparql down")
            with patch('src.knowledge.wikidata_enricher.time.sleep'):
                assert enricher.get_entity_relations("Q1") == []


class TestEnrichKg:
    """主流程测试（Mock 搜索与关系查询，patch 限流 sleep）"""

    def test_depth1_flow(self, enricher):
        """depth=1 应只搜种子并拉取关系，不二跳扩展"""
        with patch.object(enricher, 'search_entities', return_value=[
                {"qid": "Q1", "label": "嫦娥六号", "description": "月背采样", "type": "mission"},
                {"qid": "Q1", "label": "嫦娥六号", "description": "重复实体", "type": "mission"},  # 重复 QID 去重
        ]) as mock_search, \
             patch.object(enricher, 'get_entity_relations', return_value=[
                 {"subject": "嫦娥六号", "predicate": "launched_on", "object": "2024-05-03",
                  "confidence": 1.0, "source": "Wikidata"},
             ]) as mock_rels, \
             patch.object(enricher, '_get_entity_type', return_value="mission"), \
             patch('src.knowledge.wikidata_enricher.time.sleep'):
            entities, relations = enricher.enrich_kg(topic_keywords=["嫦娥六号"], depth=1)

        assert len(entities) == 1
        assert entities[0]["name"] == "嫦娥六号"
        assert entities[0]["attributes"]["wikidata_id"] == "Q1"
        assert len(relations) == 1
        assert mock_search.call_count == 1  # depth=1 不做第二轮搜索
        assert mock_rels.call_count == 1

    def test_depth2_expands_new_entities(self, enricher):
        """depth=2 应追踪关系中出现的对象实体"""
        second_round_entities = [
            {"qid": "Q2", "label": "长征五号", "description": "火箭", "type": "technology"},
        ]
        with patch.object(enricher, 'search_entities',
                          side_effect=[  # 第一轮：种子搜索；第二轮：对象名反查
                              [{"qid": "Q1", "label": "嫦娥六号", "description": "", "type": "mission"}],
                              second_round_entities,
                          ]) as mock_search, \
             patch.object(enricher, 'get_entity_relations', return_value=[
                 {"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号",
                  "confidence": 1.0, "source": "Wikidata"},
             ]), \
             patch.object(enricher, '_get_entity_type', return_value="technology"), \
             patch.object(enricher, '_get_entity_label', return_value="长征五号"), \
             patch('src.knowledge.wikidata_enricher.time.sleep'):
            entities, relations = enricher.enrich_kg(topic_keywords=["嫦娥六号"], depth=2)

        names = [e["name"] for e in entities]
        assert "嫦娥六号" in names
        assert "长征五号" in names  # 第二轮扩展进来了
        assert mock_search.call_count == 2

    def test_empty_search_returns_empty(self, enricher):
        with patch.object(enricher, 'search_entities', return_value=[]), \
             patch('src.knowledge.wikidata_enricher.time.sleep'):
            entities, relations = enricher.enrich_kg(topic_keywords=["无结果关键词"], depth=1)
        assert entities == []
        assert relations == []


class TestSaveToKg:
    """落盘合并测试（隔离到临时目录）"""

    def test_merge_dedup_and_renumber(self, enricher, tmp_path, monkeypatch):
        from src.knowledge import wikidata_enricher as we_mod
        # 现有 KG：1 实体 1 关系
        (tmp_path / "entities.json").write_text(
            _json.dumps([{"id": "e001", "name": "嫦娥六号", "type": "mission", "attributes": {}}]),
            encoding="utf-8")
        (tmp_path / "relations.json").write_text(
            _json.dumps([{"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号",
                          "confidence": 1.0, "source": "CNSA"}]),
            encoding="utf-8")
        monkeypatch.setattr(we_mod, "KG_DIR", tmp_path)

        new_entities = [
            {"id": "w001", "name": "嫦娥六号", "type": "mission", "attributes": {}},   # 重名去重
            {"id": "w002", "name": "天问三号", "type": "mission", "attributes": {}},   # 新实体
        ]
        new_relations = [
            {"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号",
             "confidence": 1.0, "source": "Wikidata"},  # 三元组重复去重
            {"subject": "天问三号", "predicate": "探测目标", "object": "火星",
             "confidence": 1.0, "source": "Wikidata"},  # 新关系
        ]
        enricher.save_to_kg(new_entities, new_relations)

        merged_entities = _json.loads((tmp_path / "entities.json").read_text(encoding="utf-8"))
        merged_relations = _json.loads((tmp_path / "relations.json").read_text(encoding="utf-8"))
        assert len(merged_entities) == 2
        names = [e["name"] for e in merged_entities]
        assert names.count("嫦娥六号") == 1
        assert "天问三号" in names
        # 新实体 ID 接续编号
        new_ent = next(e for e in merged_entities if e["name"] == "天问三号")
        assert new_ent["id"] == "e002"
        assert len(merged_relations) == 2

    def test_load_json_corrupt_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        assert WikidataEnricher._load_json(bad) == []
        assert WikidataEnricher._load_json(tmp_path / "missing.json") == []


class TestLifecycle:
    """上下文管理器测试"""

    def test_context_manager_closes(self):
        with patch('src.knowledge.wikidata_enricher.httpx.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            with WikidataEnricher() as e:
                assert e.client is mock_client
            mock_client.close.assert_called_once()
