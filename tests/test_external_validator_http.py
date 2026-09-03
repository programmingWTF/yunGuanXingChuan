"""
云观星传 - 外部校验器（ExternalValidator）HTTP 路径单元测试
覆盖 Crossref / OpenAlex / Wikipedia / Wikidata 查询解析、三路校验分级、
缓存、上下文管理与单例（Mock httpx，不依赖网络）
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture(autouse=True)
def clear_cache():
    """每个用例前后清空模块级查询缓存，避免用例间污染"""
    import src.verification.external_validator as ev
    ev._query_cache.clear()
    yield
    ev._query_cache.clear()


@pytest.fixture
def validator():
    """创建 mock 掉 httpx 客户端的外部校验器"""
    from src.verification.external_validator import ExternalValidator
    v = ExternalValidator(timeout=5.0)
    v.client = MagicMock()
    # KG 实体库固定为可控集合
    v._kg_entities = ["嫦娥六号", "天问三号", "长征五号"]
    yield v
    v.client.close()


def _mock_resp(json_data=None, raise_error=None):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_data
    if raise_error:
        resp.raise_for_status.side_effect = raise_error
    return resp


class TestQueryCrossref:
    """Crossref 元数据查询测试"""

    def test_parses_items(self, validator):
        """应解析标题/年份/作者/期刊"""
        validator.client.get.return_value = _mock_resp({
            "message": {
                "items": [
                    {
                        "title": ["Chang'e 6 lunar far-side samples"],
                        "container-title": ["Nature"],
                        "published-print": {"date-parts": [[2024, 6]]},
                        "author": [{"family": "Li"}, {"family": "Wang"}, {"name": "CNSA Team"}],
                        "abstract": "<p>study of samples</p>",
                    }
                ]
            }
        })
        items = validator._query_crossref("chang'e 6 samples")
        assert len(items) == 1
        assert items[0]["title"] == "Chang'e 6 lunar far-side samples"
        assert items[0]["published_year"] == "2024"
        assert "Li" in items[0]["authors"]
        assert items[0]["container_title"] == "Nature"

    def test_skips_empty_title(self, validator):
        """无标题的条目应跳过"""
        validator.client.get.return_value = _mock_resp({
            "message": {"items": [{"title": [], "author": [{"family": "X"}]}]}
        })
        assert validator._query_crossref("q") == []

    def test_error_returns_empty(self, validator):
        """网络异常应返回空列表"""
        validator.client.get.side_effect = ConnectionError("boom")
        assert validator._query_crossref("q") == []


class TestQueryOpenAlex:
    """OpenAlex 元数据查询测试（含倒排摘要重建）"""

    def test_parses_items_and_rebuilds_abstract(self, validator):
        """应重建 abstract_inverted_index 为顺序摘要"""
        validator.client.get.return_value = _mock_resp({
            "results": [
                {
                    "display_name": "Far-side lunar samples study",
                    "publication_year": 2024,
                    "authorships": [{"author": {"display_name": "Zhang Wei"}}],
                    "abstract_inverted_index": {
                        "lunar": [1], "far-side": [0], "samples": [2],
                    },
                }
            ]
        })
        items = validator._query_openalex("lunar samples")
        assert len(items) == 1
        assert items[0]["title"] == "Far-side lunar samples study"
        assert items[0]["publication_year"] == 2024
        # 倒排索引按位置重建：far-side(0) lunar(1) samples(2)
        assert items[0]["abstract"] == "far-side lunar samples"
        assert items[0]["authors"] == ["Zhang Wei"]

    def test_error_returns_empty(self, validator):
        validator.client.get.side_effect = ConnectionError("timeout")
        assert validator._query_openalex("q") == []


class TestSearchWikipedia:
    """Wikipedia 搜索与摘要测试"""

    def test_search_returns_extracts(self, validator):
        """应先搜标题再取摘要"""
        search_resp = _mock_resp({"query": {"search": [{"title": "嫦娥六号"}]}})
        extract_resp = _mock_resp({
            "query": {"pages": {"123": {"extract": "嫦娥六号是中国的月球采样返回任务"}}}
        })
        validator.client.get.side_effect = [search_resp, extract_resp]
        paras = validator._search_wikipedia("嫦娥六号", lang="zh")
        assert paras == ["嫦娥六号是中国的月球采样返回任务"]

    def test_search_no_results(self, validator):
        validator.client.get.return_value = _mock_resp({"query": {"search": []}})
        assert validator._search_wikipedia("不存在的话题") == []

    def test_search_error_returns_empty(self, validator):
        validator.client.get.side_effect = ConnectionError("net")
        assert validator._search_wikipedia("q") == []

    def test_extract_truncated_to_1500(self, validator):
        """摘要应截断到 1500 字符"""
        long_text = "月" * 2000
        validator.client.get.return_value = _mock_resp({
            "query": {"pages": {"1": {"extract": long_text}}}
        })
        assert len(validator._get_wikipedia_extract("嫦娥六号")) == 1500

    def test_extract_missing_returns_empty(self, validator):
        validator.client.get.return_value = _mock_resp({"query": {"pages": {"1": {}}}})
        assert validator._get_wikipedia_extract("x") == ""


class TestSearchEntityQid:
    """Wikidata 实体 QID 搜索测试"""

    def test_chinese_entity_found(self, validator):
        validator.client.get.return_value = _mock_resp({"search": [{"id": "Q11134"}]})
        assert validator._search_entity_qid("嫦娥六号") == "Q11134"

    def test_english_fallback_for_zh_miss(self, validator):
        """中文无结果时应回退英文再试"""
        zh_miss = _mock_resp({"search": []})
        en_hit = _mock_resp({"search": [{"id": "Q223"}]})
        validator.client.get.side_effect = [zh_miss, en_hit]
        assert validator._search_entity_qid("嫦娥六号") == "Q223"

    def test_not_found_returns_empty(self, validator):
        validator.client.get.return_value = _mock_resp({"search": []})
        assert validator._search_entity_qid("未知实体") == ""

    def test_qid_cached(self, validator):
        """QID 结果应写入缓存，二次查询不发请求"""
        validator.client.get.return_value = _mock_resp({"search": [{"id": "Q1"}]})
        validator._search_entity_qid("天问三号")
        call_count = validator.client.get.call_count
        assert validator._search_entity_qid("天问三号") == "Q1"
        assert validator.client.get.call_count == call_count


class TestQueryWikidataRelations:
    """Wikidata 关系 SPARQL 查询测试"""

    def test_no_qid_returns_empty(self, validator):
        with patch.object(validator, '_search_entity_qid', return_value=""):
            assert validator._query_wikidata_relations("未知") == []

    def test_parses_and_filters_relations(self, validator):
        """应过滤 http/Q 开头的 object 并解析绑定"""
        with patch.object(validator, '_search_entity_qid', return_value="Q1"):
            validator.client.get.return_value = _mock_resp({
                "results": {
                    "bindings": [
                        {"predicateLabel": {"value": "发射火箭"}, "objectLabel": {"value": "长征五号"}},
                        {"predicateLabel": {"value": "描述URL"}, "objectLabel": {"value": "http://x"}},
                        {"predicateLabel": {"value": "编号"}, "objectLabel": {"value": "Q12345"}},
                        {"predicateLabel": {"value": ""}, "objectLabel": {"value": "空谓词"}},
                    ]
                }
            })
            rels = validator._query_wikidata_relations("嫦娥六号")
        assert len(rels) == 1
        assert rels[0] == {"subject": "嫦娥六号", "predicate": "发射火箭", "object": "长征五号"}

    def test_sparql_error_returns_empty(self, validator):
        with patch.object(validator, '_search_entity_qid', return_value="Q1"):
            validator.client.get.side_effect = ConnectionError("sparql down")
            assert validator._query_wikidata_relations("嫦娥六号") == []


class TestValidateByWikidata:
    """Wikidata 三元组校验分级测试"""

    def test_no_entities_unverified(self, validator):
        """无可匹配实体应直接 unverified"""
        result = validator.validate_by_wikidata("某个完全无关的断言", [])
        assert result["status"] == "unverified"
        assert "未找到可匹配的实体" in result["evidence"]

    def test_provided_entities_take_priority(self, validator):
        """显式提供的实体应无条件采纳"""
        matched = validator._extract_entities_from_claim("任务历时53天", ["嫦娥六号"])
        assert "嫦娥六号" in matched

    def test_verified_when_strong_match(self, validator):
        """高置信关系（>=0.75）应判 verified"""
        rel = {"subject": "嫦娥六号", "predicate": "发射火箭", "object": "长征五号"}
        with patch.object(validator, '_query_wikidata_relations', return_value=[rel]), \
             patch.object(validator, '_check_claim_relation_match', return_value=0.9):
            result = validator.validate_by_wikidata("嫦娥六号由长征五号发射", ["嫦娥六号"])
        assert result["status"] == "verified"
        assert result["confidence"] == 0.9
        assert "长征五号" in result["evidence"]

    def test_partial_when_medium_match(self, validator):
        """中等置信（0.45~0.75）应判 partial"""
        rel = {"subject": "嫦娥六号", "predicate": "采样", "object": "月球背面"}
        with patch.object(validator, '_query_wikidata_relations', return_value=[rel]), \
             patch.object(validator, '_check_claim_relation_match', return_value=0.55):
            result = validator.validate_by_wikidata("嫦娥六号采集样品", ["嫦娥六号"])
        assert result["status"] == "partial"

    def test_unverified_when_weak_match(self, validator):
        """低置信（<0.45）应判 unverified"""
        rel = {"subject": "嫦娥六号", "predicate": "质量", "object": "8.2吨"}
        with patch.object(validator, '_query_wikidata_relations', return_value=[rel]), \
             patch.object(validator, '_check_claim_relation_match', return_value=0.2):
            result = validator.validate_by_wikidata("嫦娥六号质量为8.2吨", ["嫦娥六号"])
        assert result["status"] == "unverified"

    def test_result_cached(self, validator):
        """同一断言二次校验应命中缓存（不再发起 Wikidata 查询）"""
        rel = {"subject": "嫦娥六号", "predicate": "发射火箭", "object": "长征五号"}
        with patch.object(validator, '_query_wikidata_relations', return_value=[rel]) as mock_q, \
             patch.object(validator, '_check_claim_relation_match', return_value=0.9):
            r1 = validator.validate_by_wikidata("嫦娥六号由长征五号发射", ["嫦娥六号"])
            first_round_calls = mock_q.call_count  # claim 匹配到的每个实体各查一次
            assert first_round_calls >= 1
            r2 = validator.validate_by_wikidata("嫦娥六号由长征五号发射", ["嫦娥六号"])
        assert r1 == r2
        # 二次调用命中缓存：总查询次数与首次持平
        assert mock_q.call_count == first_round_calls


class TestValidateByWikipedia:
    """Wikipedia 双语校验测试"""

    def test_no_paragraphs_unverified(self, validator):
        with patch.object(validator, '_search_wikipedia', return_value=[]):
            result = validator.validate_by_wikipedia_dual("某断言", ["实体A"])
        assert result["status"] == "unverified"

    def test_verified_with_matching_paragraph(self, validator):
        """高相似段落应判 verified"""
        claim = "嫦娥六号任务历时53天"
        para = "嫦娥六号任务历时53天，2024年6月25日返回地球"
        with patch.object(validator, '_search_wikipedia', return_value=[para]):
            result = validator.validate_by_wikipedia_dual(claim, ["嫦娥六号"])
        assert result["status"] in ("verified", "partial")
        assert result["confidence"] > 0.4

    def test_fallback_to_claim_search(self, validator):
        """实体搜索无结果时应用整句 claim 兜底再搜"""
        with patch.object(validator, '_search_wikipedia', side_effect=[[], [], [], ["兜底段落内容"]]) as mock_s:
            validator.validate_by_wikipedia_dual("某断言内容", ["实体A"])
        # zh 实体搜索 + en 实体搜索 + zh claim 兜底 + en claim 兜底
        assert mock_s.call_count >= 3

    def test_lang_tag_in_evidence(self, validator):
        """证据应带语言标签"""
        para = "这是一段中文百科内容，与断言相关"
        with patch.object(validator, '_search_wikipedia', return_value=[para]):
            result = validator.validate_by_wikipedia_dual("断言：百科内容相关", ["实体"])
        if result["evidence"]:
            assert result["evidence"].startswith("[zh]") or result["evidence"].startswith("[en]")

    def test_compat_entry_delegates_to_dual(self, validator):
        """validate_by_wikipedia 兼容入口应委托双语版"""
        with patch.object(validator, 'validate_by_wikipedia_dual') as mock_dual:
            mock_dual.return_value = {"status": "verified", "confidence": 0.8, "lang": "zh"}
            result = validator.validate_by_wikipedia("claim", lang="zh")
        mock_dual.assert_called_once_with("claim")
        assert result["status"] == "verified"


class TestValidateByAcademic:
    """学术文献校验测试"""

    def test_no_results_unverified(self, validator):
        with patch.object(validator, '_query_crossref', return_value=[]), \
             patch.object(validator, '_query_openalex', return_value=[]):
            result = validator.validate_by_academic("某论文断言", ["实体"])
        assert result["status"] == "unverified"
        assert "未找到" in result["evidence"]

    def test_matching_title_verified(self, validator):
        """标题高度匹配应判 verified 或 partial"""
        items = [{"title": "Chang'e 6 lunar far side sample return mission", "published_year": "2024",
                  "authors": ["Li"], "abstract": "", "container_title": "Nature"}]
        with patch.object(validator, '_query_crossref', return_value=items), \
             patch.object(validator, '_query_openalex', return_value=[]), \
             patch.object(validator, '_text_similarity', return_value=0.85), \
             patch.object(validator, '_apply_year_conflict', return_value=0.85):
            result = validator.validate_by_academic(
                "Chang'e 6 lunar far side sample return mission study", ["Chang'e 6"])
        assert result["status"] in ("verified", "partial")
        assert result["crossref_count"] == 1

    def test_anchor_penalty_for_wrong_entity(self, validator):
        """标题未提及断言实体时应被锚定降权（防张冠李戴）"""
        items = [{"title": "Lunar sample analysis 2024", "published_year": "2024",
                  "authors": [], "abstract": "", "container_title": ""}]
        base_sim = 0.9

        def sim_no_boost(a, b):
            return base_sim

        with patch.object(validator, '_query_crossref', return_value=items), \
             patch.object(validator, '_query_openalex', return_value=[]), \
             patch.object(validator, '_text_similarity', side_effect=sim_no_boost), \
             patch.object(validator, '_apply_year_conflict', side_effect=lambda c, t, s: s):
            result = validator.validate_by_academic("月球样品研究断言", ["嫦娥六号"])
        # 实体未在标题出现 → sim *= 0.5 = 0.45 → partial
        assert result["status"] == "partial"
        assert abs(result["confidence"] - 0.45) < 1e-6

    def test_build_academic_query(self, validator):
        """查询构造：实体 + 断言主干"""
        q = validator._build_academic_query("嫦娥六号采集样品1935.3克", ["嫦娥六号"])
        assert "嫦娥六号" in q
        # 断言主干不应与实体重复追加
        assert q.count("嫦娥六号") == 1

    def test_build_query_empty_claim(self, validator):
        """空断言兜底"""
        q = validator._build_academic_query("断言", [])
        assert len(q) > 0


class TestValidateEntry:
    """validate 综合入口测试"""

    def test_combines_three_channels(self, validator):
        """应并行调用三路并综合判定"""
        with patch.object(validator, 'validate_by_wikidata') as mock_wd, \
             patch.object(validator, 'validate_by_wikipedia_dual') as mock_wp, \
             patch.object(validator, 'validate_by_academic') as mock_ac:
            mock_wd.return_value = {"status": "verified", "confidence": 0.9, "evidence": "wd"}
            mock_wp.return_value = {"status": "verified", "confidence": 0.8, "evidence": "wp"}
            mock_ac.return_value = {"status": "partial", "confidence": 0.5, "evidence": "ac"}
            result = validator.validate("嫦娥六号由长征五号发射", ["嫦娥六号"])
        assert set(result["sources"].keys()) == {"wikidata", "wikipedia", "academic"}
        assert result["status"] in ("verified", "partial")
        assert result["confidence"] > 0
        mock_wd.assert_called_once()
        mock_wp.assert_called_once()
        mock_ac.assert_called_once()

    def test_all_unverified(self, validator):
        """三路均无结果应综合为 unverified"""
        with patch.object(validator, 'validate_by_wikidata',
                          return_value={"status": "unverified", "confidence": 0.0, "evidence": ""}), \
             patch.object(validator, 'validate_by_wikipedia_dual',
                          return_value={"status": "unverified", "confidence": 0.0, "evidence": ""}), \
             patch.object(validator, 'validate_by_academic',
                          return_value={"status": "unverified", "confidence": 0.0, "evidence": ""}):
            result = validator.validate("无法验证的断言", [])
        assert result["status"] == "unverified"


class TestTextSimilarity:
    """文本相似度测试"""

    def test_identical_text(self, validator):
        assert validator._text_similarity("嫦娥六号任务", "嫦娥六号任务") == 1.0

    def test_empty_text(self, validator):
        assert validator._text_similarity("", "abc") == 0.0
        assert validator._text_similarity("abc", "") == 0.0

    def test_disjoint_text_low(self, validator):
        sim = validator._text_similarity("苹果香蕉橘子", "量子计算机芯片")
        assert sim < 0.15

    def test_partial_overlap_between(self, validator):
        sim = validator._text_similarity("嫦娥六号", "嫦娥六号月球背面采样返回任务")
        assert 0.0 < sim < 1.0

    def test_number_token_matching(self, validator):
        """数字应作为独立 token 参与匹配"""
        sim = validator._text_similarity("任务历时53天", "任务历时53天")
        assert sim == 1.0


class TestExtractNumbers:
    """数值提取测试"""

    def test_extracts_number_with_unit(self):
        from src.verification.external_validator import _extract_numbers
        nums = _extract_numbers("采集样品约1935.3克，任务历时53天")
        values = [n[0] for n in nums]
        assert "1935.3" in values
        assert "53" in values

    def test_no_numbers(self):
        from src.verification.external_validator import _extract_numbers
        assert _extract_numbers("纯中文断言没有数字") == []


class TestCache:
    """查询缓存测试"""

    def test_cache_roundtrip(self):
        import src.verification.external_validator as ev
        ev._query_cache.clear()
        ev._cache_set("k1", {"status": "ok"})
        assert ev._cache_get("k1") == {"status": "ok"}
        assert ev._cache_get("missing") is None
        ev._query_cache.clear()

    def test_cache_ttl_expiry(self):
        import src.verification.external_validator as ev
        ev._query_cache.clear()
        # 手动写入过期时间戳
        ev._query_cache["old"] = (time.time() - ev._CACHE_TTL - 1, {"status": "stale"})
        assert ev._cache_get("old") is None
        assert "old" not in ev._query_cache
        ev._query_cache.clear()


class TestLifecycle:
    """生命周期与单例测试"""

    def test_context_manager_closes(self):
        from src.verification.external_validator import ExternalValidator
        with patch('src.verification.external_validator.httpx.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            with ExternalValidator() as v:
                assert v.client is mock_client
            mock_client.close.assert_called_once()

    def test_get_validator_singleton(self):
        from src.verification.external_validator import get_external_validator, ExternalValidator
        v1 = get_external_validator()
        v2 = get_external_validator()
        assert v1 is v2
        assert isinstance(v1, ExternalValidator)


class TestCheckClaimRelationMatch:
    """断言-关系匹配度测试（全分支纯逻辑）"""

    def _m(self, validator, claim, obj="", pred=""):
        return validator._check_claim_relation_match(claim, {"object": obj, "predicate": pred})

    def test_weak_metadata_relation_zero(self, validator):
        """弱元数据关系不得作为断言证据"""
        assert self._m(validator, "嫦娥六号任务", obj="嫦娥六号", pred="得名自") == 0.0
        assert self._m(validator, "任务", obj="x", pred="instance of") == 0.0
        assert self._m(validator, "任务", obj="x", pred="位于") == 0.0

    def test_object_independent_hit(self, validator):
        """对象独立出现在 claim（英文边界）→ 强匹配"""
        assert self._m(validator, "The mission used Long March 5 rocket", obj="Long March 5", pred="x") == 0.88

    def test_substring_object_not_hit(self, validator):
        """「嫦娥」⊂「嫦娥六号」不算独立命中"""
        assert self._m(validator, "嫦娥六号任务", obj="嫦娥") == 0.0
        # 中文对象前后紧贴中文（无空格/标点）同样视为子串包裹
        assert self._m(validator, "任务着陆于月球背面", obj="月球背面", pred="x") == 0.0

    def test_year_exact_strong(self, validator):
        """年份精确一致 → 0.95"""
        assert self._m(validator, "任务历时53天 2024年返回", obj="2024", pred="返回日期") == 0.95

    def test_year_conflict_zero(self, validator):
        """claim 含其他年份且对象年份不同 → 矛盾压制"""
        assert self._m(validator, "2023年发射的任务", obj="2024", pred="发射日期") == 0.0

    def test_year_no_claim_year(self, validator):
        """对象为年份但 claim 无年份 → 0.7"""
        assert self._m(validator, "某次发射任务", obj="2024", pred="launch date") == 0.7

    def test_date_object_normalized(self, validator):
        """日期对象归一化为年份再比对"""
        assert self._m(validator, "2024年5月发射", obj="2024-05-03T00:00:00Z", pred="launch") == 0.95

    def test_numeric_exact_hit(self, validator):
        """数值精确命中 → 0.85"""
        assert self._m(validator, "采集样品1935.3克", obj="1935.3", pred="质量") == 0.85

    def test_numeric_mismatch_zero(self, validator):
        assert self._m(validator, "采集样品1935.3克", obj="888.8", pred="质量") == 0.0

    def test_en_predicate_keyword_match(self, validator):
        """英文谓词关键词出现在 claim → 中匹配"""
        score = self._m(validator, "嫦娥六号 successfully landed on 月球", obj="x", pred="landed on")
        assert score > 0.5

    def test_zh_predicate_hint_match(self, validator):
        """英文谓词词干映射到中文关键词命中"""
        # returns → 词干 return → 中文映射 返回
        score = self._m(validator, "嫦娥六号返回地球", obj="x", pred="returns")
        assert score == 0.6

    def test_en_object_word_overlap(self, validator):
        """英文对象词覆盖 → 0.5"""
        score = self._m(validator, "Chang e 6 carried out sample return mission",
                        obj="Chang e 6", pred="something")
        assert score >= 0.5

    def test_no_match_zero(self, validator):
        assert self._m(validator, "完全无关的断言文本", obj="另一个实体", pred="other_pred") == 0.0


class TestCombineSignalsFull:
    """三路信号综合判定全分支测试"""

    def _c(self, validator, wd, wp, ac=None):
        return validator._combine_signals(wd, wp, ac)

    def test_two_strong_verified(self, validator):
        status, conf, _ = self._c(validator,
                                  {"status": "verified", "confidence": 0.8, "evidence": "a"},
                                  {"status": "verified", "confidence": 0.7, "evidence": "b"})
        assert status == "verified"
        assert conf > 0.8

    def test_one_strong_plus_real_partial(self, validator):
        status, _, _ = self._c(validator,
                               {"status": "verified", "confidence": 0.9, "evidence": "a"},
                               {"status": "partial", "confidence": 0.5, "evidence": "b"})
        assert status == "verified"

    def test_one_strong_plus_empty_partial_not_verified(self, validator):
        """佐证 partial 置信度 <0.3 不算有效佐证"""
        status, _, _ = self._c(validator,
                               {"status": "verified", "confidence": 0.9, "evidence": "a"},
                               {"status": "partial", "confidence": 0.1, "evidence": ""})
        assert status == "partial"

    def test_single_academic_without_wiki_evidence_low_partial(self, validator):
        """仅学术强证据 + wd/wp 未命中 → 低置信 partial（防荒谬断言）"""
        status, conf, _ = self._c(validator,
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""},
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""},
                                  {"status": "verified", "confidence": 0.9, "evidence": "论文"})
        assert status == "partial"
        assert conf == 0.5  # min(0.5, 0.9)

    def test_single_strong_plain_partial(self, validator):
        status, conf, _ = self._c(validator,
                                  {"status": "verified", "confidence": 0.9, "evidence": "a"},
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""})
        assert status == "partial"
        assert conf == 0.75

    def test_two_partial_with_wiki_backing(self, validator):
        status, conf, _ = self._c(validator,
                                  {"status": "partial", "confidence": 0.6, "evidence": "a"},
                                  {"status": "partial", "confidence": 0.5, "evidence": "b"})
        assert status == "partial"
        assert abs(conf - 0.6) < 1e-9  # min(0.65, (0.6+0.5)/2+0.05)

    def test_two_partial_no_wiki_evidence(self, validator):
        """wd/wp 未命中时两路弱 partial 不上浮"""
        status, conf, _ = self._c(validator,
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""},
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""},
                                  {"status": "partial", "confidence": 0.5, "evidence": "c"},
                                  )
        # 只有一路 partial（academic）→ 单路 partial 低置信
        assert status == "partial"
        assert conf == 0.5

    def test_single_partial(self, validator):
        status, conf, _ = self._c(validator,
                                  {"status": "partial", "confidence": 0.6, "evidence": "a"},
                                  {"status": "unverified", "confidence": 0.0, "evidence": ""})
        assert status == "partial"
        assert conf == 0.5

    def test_all_unverified_default_evidence(self, validator):
        status, conf, evidence = self._c(validator,
                                         {"status": "unverified", "confidence": 0.2, "evidence": ""},
                                         {"status": "unverified", "confidence": 0.0, "evidence": ""})
        assert status == "unverified"
        assert abs(conf - 0.08) < 1e-9  # max*0.4
        assert evidence == "无外部证据支持"

    def test_academic_none_treated_empty(self, validator):
        status, _, _ = self._c(validator,
                               {"status": "unverified", "confidence": 0.0, "evidence": ""},
                               {"status": "partial", "confidence": 0.6, "evidence": "b"},
                               None)
        assert status == "partial"
