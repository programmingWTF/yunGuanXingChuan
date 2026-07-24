"""
云观星传 - 独立外部校验器
通过 Wikidata 三元组比对和 Wikipedia 段落召回提供不依赖 LLM 的独立校验信号。
解决"用同一个模型生成又校验"的循环论证问题。

校验链路：
  Wikidata 三元组精确匹配 → 结构化事实校验
  Wikipedia 段落语义相似度 → 自然语言事实校验
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import KG_DIR

logger = logging.getLogger(__name__)

# API 端点
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_ZH = "https://zh.wikipedia.org/w/api.php"
WIKIPEDIA_API_EN = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "YunGuanXingChuan/1.0 (Research Project; contact: yunGuanXingChuan@example.com)"

# 缓存：避免重复查询（10 分钟过期）
_CACHE_TTL = 600  # 秒
_query_cache: Dict[str, Tuple[float, Dict]] = {}


def _cache_get(key: str) -> Optional[Dict]:
    """从缓存获取结果"""
    if key in _query_cache:
        ts, result = _query_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return result
        del _query_cache[key]
    return None


def _cache_set(key: str, value: Dict) -> None:
    """写入缓存"""
    _query_cache[key] = (time.time(), value)


class ExternalValidator:
    """
    独立外部校验器：通过 Wikidata 三元组比对和 Wikipedia 段落召回
    提供不依赖 LLM 的独立校验信号。

    特点：
    - 不调用任何 LLM API（无 get_llm_client()）
    - 外部 API 不可达时 graceful degrade（返回 unverified 而非崩溃）
    - 查询结果缓存 10 分钟
    """

    def __init__(self, timeout: float = 5.0):
        """
        Args:
            timeout: 外部 API 请求超时（秒）
        """
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        # 加载本地 KG 实体名（用于快速匹配）
        self._kg_entities: List[str] = self._load_kg_entities()

    def close(self):
        """关闭 HTTP 客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def validate(self, claim: str, entities: Optional[List[str]] = None) -> Dict:
        """
        综合校验入口：结合 Wikidata + Wikipedia 两路独立信号

        Args:
            claim: 待验证的事实断言
            entities: 断言涉及的核心实体列表

        Returns:
            {
                "status": "verified" | "partial" | "unverified",
                "confidence": float,
                "evidence": str,
                "sources": {"wikidata": {...}, "wikipedia": {...}},
            }
        """
        entities = entities or []
        results = {}

        # 路径 1: Wikidata 三元组比对
        wd_result = self.validate_by_wikidata(claim, entities)
        results["wikidata"] = wd_result

        # 路径 2: Wikipedia 段落召回
        wp_result = self.validate_by_wikipedia(claim)
        results["wikipedia"] = wp_result

        # 综合判定
        status, confidence, evidence = self._combine_signals(wd_result, wp_result)

        return {
            "status": status,
            "confidence": confidence,
            "evidence": evidence,
            "sources": results,
        }

    def validate_by_wikidata(self, claim: str, entities: List[str]) -> Dict:
        """
        Wikidata 三元组比对校验（不需要 LLM）

        逻辑：
        1. 从 claim 中匹配已知实体
        2. 查询 Wikidata：这些实体间是否存在 claim 断言的关系
        3. 返回 {status, confidence, evidence}

        Args:
            claim: 待验证断言
            entities: 相关实体列表

        Returns:
            校验结果字典
        """
        cache_key = f"wd:{claim}:{','.join(entities)}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        # 从 claim 中提取实体（字符串匹配 KG 实体）
        matched_entities = self._extract_entities_from_claim(claim, entities)

        if not matched_entities:
            result = {
                "status": "unverified",
                "confidence": 0.0,
                "evidence": "未找到可匹配的实体",
            }
            _cache_set(cache_key, result)
            return result

        # 对每个实体查询 Wikidata 关系
        best_match = None
        best_confidence = 0.0

        for entity in matched_entities[:3]:  # 限制查询数量
            relations = self._query_wikidata_relations(entity)
            for rel in relations:
                # 检查关系是否与 claim 相关
                relevance = self._check_claim_relation_match(claim, rel)
                if relevance > best_confidence:
                    best_confidence = relevance
                    best_match = rel

        if best_match and best_confidence >= 0.7:
            result = {
                "status": "verified",
                "confidence": best_confidence,
                "evidence": f"Wikidata: {best_match.get('subject', '')} "
                           f"-[{best_match.get('predicate', '')}]-> "
                           f"{best_match.get('object', '')}",
            }
        elif best_match and best_confidence >= 0.4:
            result = {
                "status": "partial",
                "confidence": best_confidence,
                "evidence": f"Wikidata 部分匹配: {best_match.get('subject', '')} "
                           f"-[{best_match.get('predicate', '')}]-> "
                           f"{best_match.get('object', '')}",
            }
        else:
            result = {
                "status": "unverified",
                "confidence": best_confidence,
                "evidence": "Wikidata 未找到支持关系",
            }

        _cache_set(cache_key, result)
        return result

    def validate_by_wikipedia(self, claim: str, lang: str = "zh") -> Dict:
        """
        Wikipedia 段落召回校验（不需要 LLM）

        逻辑：
        1. 用 Wikipedia API 搜索相关段落
        2. 计算 claim 和段落的文本相似度（简单关键词重叠 + 长度归一化）
        3. 相似度 ≥ 0.75 → verified, ≥ 0.55 → partial, < 0.55 → unverified

        Args:
            claim: 待验证断言
            lang: 语言代码

        Returns:
            校验结果字典
        """
        cache_key = f"wp:{lang}:{claim}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        # 搜索 Wikipedia
        paragraphs = self._search_wikipedia(claim, lang=lang)

        if not paragraphs:
            # 尝试英文
            if lang == "zh":
                paragraphs = self._search_wikipedia(claim, lang="en")
            if not paragraphs:
                result = {
                    "status": "unverified",
                    "confidence": 0.0,
                    "evidence": "Wikipedia 未找到相关段落",
                }
                _cache_set(cache_key, result)
                return result

        # 计算 claim 与段落的相似度
        best_similarity = 0.0
        best_paragraph = ""

        for para in paragraphs[:5]:
            sim = self._text_similarity(claim, para)
            if sim > best_similarity:
                best_similarity = sim
                best_paragraph = para

        # 判定
        if best_similarity >= 0.75:
            status = "verified"
        elif best_similarity >= 0.55:
            status = "partial"
        else:
            status = "unverified"

        result = {
            "status": status,
            "confidence": min(best_similarity, 1.0),
            "evidence": best_paragraph[:200] if best_paragraph else "",
        }
        _cache_set(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _extract_entities_from_claim(self, claim: str, provided_entities: List[str]) -> List[str]:
        """从 claim 中提取实体（字符串匹配）"""
        matched = []

        # 优先使用提供的实体
        for ent in provided_entities:
            if ent and ent in claim:
                matched.append(ent)

        # 再从 KG 实体库中匹配
        for kg_ent in self._kg_entities:
            if kg_ent in claim and kg_ent not in matched:
                matched.append(kg_ent)
                if len(matched) >= 5:
                    break

        return matched

    def _query_wikidata_relations(self, entity_name: str) -> List[Dict]:
        """查询实体在 Wikidata 上的关系"""
        # 先搜索获取 QID
        qid = self._search_entity_qid(entity_name)
        if not qid:
            return []

        # SPARQL 查询关系
        sparql_query = f"""
        SELECT ?predicateLabel ?objectLabel WHERE {{
          wd:{qid} ?p ?object .
          ?predicate wikibase:directClaim ?p .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "zh,en". }}
        }}
        LIMIT 30
        """
        try:
            resp = self.client.get(
                SPARQL_ENDPOINT,
                params={"query": sparql_query, "format": "json"},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"[ExternalValidator] Wikidata 查询失败: {e}")
            return []

        relations = []
        for binding in data.get("results", {}).get("bindings", []):
            pred = binding.get("predicateLabel", {}).get("value", "")
            obj = binding.get("objectLabel", {}).get("value", "")
            if pred and obj:
                relations.append({
                    "subject": entity_name,
                    "predicate": pred,
                    "object": obj,
                })
        return relations

    def _search_entity_qid(self, name: str) -> str:
        """搜索实体获取 Wikidata QID"""
        cache_key = f"qid:{name}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached.get("qid", "")

        lang = "en" if name.isascii() else "zh"
        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": lang,
            "format": "json",
            "limit": 3,
            "type": "item",
        }
        try:
            resp = self.client.get(WIKIDATA_API, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("search", [])
            qid = results[0]["id"] if results else ""
        except Exception as e:
            logger.debug(f"[ExternalValidator] 搜索实体 '{name}' 失败: {e}")
            qid = ""

        _cache_set(cache_key, {"qid": qid})
        return qid

    def _check_claim_relation_match(self, claim: str, relation: Dict) -> float:
        """
        检查 claim 与 Wikidata 关系的匹配度

        Returns:
            匹配度 0.0 ~ 1.0
        """
        obj = relation.get("object", "")
        pred = relation.get("predicate", "")

        # 对象名出现在 claim 中 → 强匹配
        if obj and obj in claim:
            return 0.9

        # 谓词关键词出现在 claim 中 → 中匹配
        claim_lower = claim.lower()
        pred_keywords = pred.lower().replace("_", " ").split()
        matched_words = sum(1 for w in pred_keywords if w in claim_lower)
        if pred_keywords and matched_words / len(pred_keywords) > 0.5:
            return 0.6

        # 对象名部分匹配
        if obj and len(obj) >= 2:
            # 检查对象名的关键词是否出现在 claim 中
            obj_words = obj.replace("_", " ").split()
            obj_matched = sum(1 for w in obj_words if w in claim)
            if obj_words and obj_matched / len(obj_words) > 0.5:
                return 0.5

        return 0.0

    def _search_wikipedia(self, query: str, lang: str = "zh") -> List[str]:
        """搜索 Wikipedia 获取相关段落"""
        api_url = WIKIPEDIA_API_ZH if lang == "zh" else WIKIPEDIA_API_EN

        # 先搜索获取页面标题
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
        }
        try:
            resp = self.client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"[ExternalValidator] Wikipedia 搜索失败: {e}")
            return []

        titles = [r["title"] for r in data.get("query", {}).get("search", [])]
        if not titles:
            return []

        # 获取页面摘要
        paragraphs = []
        for title in titles[:2]:
            extract = self._get_wikipedia_extract(title, lang)
            if extract:
                paragraphs.append(extract)

        return paragraphs

    def _get_wikipedia_extract(self, title: str, lang: str = "zh") -> str:
        """获取 Wikipedia 页面的摘要段落"""
        api_url = WIKIPEDIA_API_ZH if lang == "zh" else WIKIPEDIA_API_EN
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "format": "json",
        }
        try:
            resp = self.client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                extract = page.get("extract", "")
                if extract:
                    return extract[:1000]  # 限制长度
        except Exception as e:
            logger.debug(f"[ExternalValidator] Wikipedia 获取摘要失败: {e}")
        return ""

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """
        计算两段文本的相似度（基于关键词重叠，不依赖 LLM）

        使用字符 n-gram 重叠 + 关键词覆盖率
        """
        if not text_a or not text_b:
            return 0.0

        # 提取关键词（简单分词：按标点和空格分割，取长度>=2的片段）
        def extract_keywords(text: str) -> set:
            import re
            # 中文按字符 bigram，英文按单词
            words = set()
            # 英文单词
            en_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
            words.update(en_words)
            # 中文 bigram
            zh_chars = re.findall(r'[\u4e00-\u9fff]', text)
            for i in range(len(zh_chars) - 1):
                words.add(zh_chars[i] + zh_chars[i + 1])
            # 数字
            numbers = re.findall(r'\d+', text)
            words.update(numbers)
            return words

        kw_a = extract_keywords(text_a)
        kw_b = extract_keywords(text_b)

        if not kw_a or not kw_b:
            return 0.0

        # Jaccard-like 相似度（以较小集合为基准）
        intersection = kw_a & kw_b
        smaller_set = min(len(kw_a), len(kw_b))
        if smaller_set == 0:
            return 0.0

        # 覆盖率：claim 的关键词在段落中出现的比例
        coverage = len(intersection) / len(kw_a) if kw_a else 0.0
        # Jaccard
        jaccard = len(intersection) / len(kw_a | kw_b)

        # 综合：覆盖率权重更高（claim 通常较短）
        similarity = 0.7 * coverage + 0.3 * jaccard
        return min(similarity, 1.0)

    def _combine_signals(self, wd_result: Dict, wp_result: Dict) -> Tuple[str, float, str]:
        """
        综合 Wikidata 和 Wikipedia 两路信号

        Returns:
            (status, confidence, evidence)
        """
        wd_status = wd_result.get("status", "unverified")
        wp_status = wp_result.get("status", "unverified")
        wd_conf = wd_result.get("confidence", 0.0)
        wp_conf = wp_result.get("confidence", 0.0)

        evidence_parts = []
        if wd_result.get("evidence"):
            evidence_parts.append(wd_result["evidence"])
        if wp_result.get("evidence"):
            evidence_parts.append(wp_result["evidence"][:150])

        # 双方都 verified → 高置信度
        if wd_status == "verified" and wp_status == "verified":
            return "verified", min(0.95, (wd_conf + wp_conf) / 2 + 0.1), " | ".join(evidence_parts)

        # 一方 verified + 另一方 partial → verified
        if (wd_status == "verified" and wp_status == "partial") or \
           (wd_status == "partial" and wp_status == "verified"):
            return "verified", min(0.85, max(wd_conf, wp_conf)), " | ".join(evidence_parts)

        # 一方 verified → partial（单源不够强）
        if wd_status == "verified" or wp_status == "verified":
            return "partial", max(wd_conf, wp_conf) * 0.85, " | ".join(evidence_parts)

        # 双方 partial → partial
        if wd_status == "partial" and wp_status == "partial":
            return "partial", (wd_conf + wp_conf) / 2, " | ".join(evidence_parts)

        # 一方 partial → partial（低置信度）
        if wd_status == "partial" or wp_status == "partial":
            return "partial", max(wd_conf, wp_conf) * 0.7, " | ".join(evidence_parts)

        # 都 unverified
        return "unverified", max(wd_conf, wp_conf) * 0.3, " | ".join(evidence_parts) or "无外部证据支持"

    @staticmethod
    def _load_kg_entities() -> List[str]:
        """加载本地 KG 实体名列表"""
        entities_path = KG_DIR / "entities.json"
        try:
            if entities_path.exists():
                with open(entities_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [e.get("name", "") for e in data if e.get("name")]
        except Exception as e:
            logger.debug(f"[ExternalValidator] 加载 KG 实体失败: {e}")
        return []


# 全局单例
_external_validator: Optional[ExternalValidator] = None


def get_external_validator() -> ExternalValidator:
    """获取全局 ExternalValidator 单例"""
    global _external_validator
    if _external_validator is None:
        _external_validator = ExternalValidator()
    return _external_validator
