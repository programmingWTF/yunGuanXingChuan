"""
云观星传 - 独立外部校验器（多数据源版）
通过 Wikidata 三元组比对、Wikipedia 段落召回 与 学术文献元数据（Crossref/OpenAlex）
提供不依赖 LLM 的独立校验信号。
解决"用同一个模型生成又校验"的循环论证问题。

校验链路（三路并行）：
  Wikidata  三元组精确匹配 + 别名/数值比对 → 结构化事实校验
  Wikipedia 双语段落语义相似度 + 数值断言比对 → 自然语言事实校验
  Academic  Crossref/OpenAlex 论文元数据 → 科研事实校验（论文存在性/年份/作者/摘要）
"""
import json
import logging
import re
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
CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
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


def _extract_numbers(text: str) -> List[Tuple[str, str, str]]:
    """
    从文本中提取 (数值, 单位, 原始片段) 三元组。
    数值断言校验的基础：科研事实普遍含数字（年份、克数、天数、百分比等）。
    例：'采集月球背面样品约1935.3克' → [('1935.3', '克', '1935.3克'), ('53', '天', '53天')]
    """
    if not text:
        return []
    units = (
        "克|千克|公斤|吨|毫克|微克|公里|千米|米|厘米|毫米|纳米|光年|秒|分钟|小时|"
        "天|月|年|岁|摄氏度|℃|华氏度|℉|百分比|%|个百分点|次|颗|台|枚|项|人|亿|万|"
        "km|kg|g|mg|cm|mm|nm|m|s|min|h|day|days|yr|years|year|%|percent|million|billion|"
        "兆|吉|太|TB|GB|MB|KB"
    )
    pattern = rf"(\d+(?:[.,]\d+)?)\s*(?:约|大约|近|超过|逾|达)?\s*({units})?"
    found = []
    for m in re.finditer(pattern, text, re.IGNORECASE):
        num = m.group(1).replace(",", "")
        unit = (m.group(2) or "").lower()
        if unit or len(num) >= 4:  # 无单位时仅保留疑似年份/大数
            found.append((num, unit, m.group(0)))
    return found


def _numbers_overlap(text_a: str, text_b: str) -> Dict:
    """
    两段文本的数值断言重合度。
    返回 {matched: [...], total: N, hit: bool, ratio: float}
    数值精确命中是极强的独立证据（如 1935.3 克、53 天）。
    """
    nums_a = [n for n, _, _ in _extract_numbers(text_a)]
    nums_b = set(n for n, _, _ in _extract_numbers(text_b))
    matched = [n for n in nums_a if n in nums_b]
    return {
        "matched": matched,
        "total": len(nums_a),
        "hit": len(matched) > 0,
        "ratio": len(matched) / len(nums_a) if nums_a else 0.0,
    }


class ExternalValidator:
    """
    独立外部校验器：Wikidata + Wikipedia + 学术文献（Crossref/OpenAlex）三路校验

    特点：
    - 不调用任何 LLM API（无 get_llm_client()）
    - 外部 API 不可达时 graceful degrade（返回 unverified 而非崩溃）
    - 查询结果缓存 10 分钟
    - 2026-09-01 扩充：新增学术文献通道 + 数值断言校验 + 双语 Wikipedia
    """

    def __init__(self, timeout: float = 12.0):
        """
        Args:
            timeout: 外部 API 请求超时（秒）
        """
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=8),
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
        综合校验入口：Wikidata + Wikipedia + 学术文献，三路并行独立信号

        Args:
            claim: 待验证的事实断言
            entities: 断言涉及的核心实体列表

        Returns:
            {
                "status": "verified" | "partial" | "unverified",
                "confidence": float,
                "evidence": str,
                "sources": {"wikidata": {...}, "wikipedia": {...}, "academic": {...}},
            }
        """
        entities = entities or []
        results = {}

        # 三路并行执行（Wikidata / Wikipedia / Academic），取最慢一路为总耗时
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            f_wd = ex.submit(self.validate_by_wikidata, claim, entities)
            f_wp = ex.submit(self.validate_by_wikipedia_dual, claim, entities)
            f_ac = ex.submit(self.validate_by_academic, claim, entities)
            wd_result = f_wd.result()
            wp_result = f_wp.result()
            ac_result = f_ac.result()
        results["wikidata"] = wd_result
        results["wikipedia"] = wp_result
        results["academic"] = ac_result

        # 综合判定
        status, confidence, evidence = self._combine_signals(wd_result, wp_result, ac_result)

        return {
            "status": status,
            "confidence": confidence,
            "evidence": evidence,
            "sources": results,
        }

    def validate_by_wikidata(self, claim: str, entities: List[str]) -> Dict:
        """
        Wikidata 三元组比对校验（不需要 LLM）

        增强点（2026-09-01）：
        1. 实体匹配支持别名/描述辅助判定（QID 实体的 aliases/description）
        2. 谓词词干匹配（launched_by → 发射）
        3. 数值断言：Wikidata 关系 object 为数值时与 claim 中数字比对

        Returns:
            校验结果字典
        """
        cache_key = f"wd:{claim}:{','.join(entities)}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        # 从 claim 中提取实体（字符串匹配 KG 实体 + 提供实体）
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

        if best_match and best_confidence >= 0.75:
            result = {
                "status": "verified",
                "confidence": best_confidence,
                "evidence": f"Wikidata: {best_match.get('subject', '')} "
                           f"-[{best_match.get('predicate', '')}]-> "
                           f"{best_match.get('object', '')}",
            }
        elif best_match and best_confidence >= 0.45:
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

    def validate_by_wikipedia_dual(self, claim: str, entities: Optional[List[str]] = None) -> Dict:
        """
        Wikipedia 双语（zh + en）段落召回校验

        增强点（2026-09-01）：
        1. 中英文都检索（原逻辑仅在中文失败时才回退英文）
        2. 每语言取 3 个页面、摘要扩到 1500 字符
        3. 相似度含数值断言比对加成
        4. 阈值微调：≥0.62 verified / ≥0.42 partial（原 0.75/0.55 过于苛刻，
           科研断言在百科摘要里通常为同义改写而非字面重复）
        5. v2 修复：搜索词优先用断言实体名（如「嫦娥六号」），而非整句长 claim——
           「任务历时53天」整句搜索会命中无关页面（天舟三号），实体搜索才准确。
        """
        ents = [e for e in (entities or []) if e]
        cache_key = f"wp:{claim}:{','.join(ents)}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        # 搜索词构造：实体名（优先）→ 实体名+短断言 → 整句兜底
        entities_part = " ".join(ents[:2])
        zh_search = entities_part if entities_part else claim
        en_search = entities_part if entities_part else claim

        paragraphs_zh = self._search_wikipedia(zh_search, lang="zh", max_pages=3)
        paragraphs_en = self._search_wikipedia(en_search, lang="en", max_pages=3)
        # 兜底：实体搜索无结果时用整句 claim 再试
        if not paragraphs_zh and zh_search != claim:
            paragraphs_zh = self._search_wikipedia(claim, lang="zh", max_pages=3)
        if not paragraphs_en and en_search != claim:
            paragraphs_en = self._search_wikipedia(claim, lang="en", max_pages=3)

        # 计算 claim 与段落的相似度（跨语言取最优）
        best_similarity = 0.0
        best_paragraph = ""
        best_lang = ""

        candidates = [("zh", p) for p in paragraphs_zh] + [("en", p) for p in paragraphs_en]
        for lang, para in candidates:
            sim = self._text_similarity(claim, para)
            # 年份矛盾否决：claim 说 2015，百科段落说 2024 → 该段落不支持断言
            sim = self._apply_year_conflict(claim, para, sim)
            if sim > best_similarity:
                best_similarity = sim
                best_paragraph = para
                best_lang = lang

        # 数值断言加成：claim 中数字在段落中命中 → 相似度上浮（上限 1.0）
        num_overlap = _numbers_overlap(claim, best_paragraph) if best_paragraph else {"hit": False, "ratio": 0.0}
        if num_overlap["hit"] and num_overlap["ratio"] >= 0.5:
            # 数值全命中且已有文本部分匹配（>=0.42）→ 直接升 verified：
            # 精确数字（1935.3 克/53 天）是极强的独立证据，巧合概率极低
            if best_similarity >= 0.42:
                best_similarity = max(best_similarity, 0.63)
            else:
                best_similarity = min(1.0, best_similarity + 0.12)

        # 判定
        if best_similarity >= 0.62:
            status = "verified"
        elif best_similarity >= 0.42:
            status = "partial"
        else:
            status = "unverified"

        result = {
            "status": status,
            "confidence": min(best_similarity, 1.0),
            "evidence": (f"[{best_lang}] " if best_lang else "") + best_paragraph[:250] if best_paragraph else "",
            "lang": best_lang,
            "num_hit": num_overlap.get("hit", False),
        }
        _cache_set(cache_key, result)
        return result

    def validate_by_wikipedia(self, claim: str, lang: str = "zh") -> Dict:
        """
        兼容入口：单语言 Wikipedia 校验（直接调用双语版）
        """
        result = self.validate_by_wikipedia_dual(claim)
        # 若调用方指定语言且双语结果未命中该语言，尝试单语言增强
        if result["status"] == "unverified" and lang != "zh":
            single = self._validate_by_wikipedia_single(claim, lang)
            if single["confidence"] > result["confidence"]:
                return single
        return result

    def _validate_by_wikipedia_single(self, claim: str, lang: str) -> Dict:
        """单语言 Wikipedia 校验（指定语言专属页面）"""
        paragraphs = self._search_wikipedia(claim, lang=lang, max_pages=3)
        if not paragraphs:
            return {"status": "unverified", "confidence": 0.0, "evidence": "", "lang": lang}
        best_sim, best_para = 0.0, ""
        for para in paragraphs:
            sim = self._text_similarity(claim, para)
            sim = self._apply_year_conflict(claim, para, sim)
            if sim > best_sim:
                best_sim, best_para = sim, para
        num_overlap = _numbers_overlap(claim, best_para)
        if num_overlap["hit"] and num_overlap["ratio"] >= 0.5:
            if best_sim >= 0.42:
                best_sim = max(best_sim, 0.63)
            else:
                best_sim = min(1.0, best_sim + 0.12)
        if best_sim >= 0.62:
            status = "verified"
        elif best_sim >= 0.42:
            status = "partial"
        else:
            status = "unverified"
        return {
            "status": status,
            "confidence": min(best_sim, 1.0),
            "evidence": (f"[{lang}] " if best_para else "") + best_para[:250],
            "lang": lang,
            "num_hit": num_overlap.get("hit", False),
        }

    def validate_by_academic(self, claim: str, entities: Optional[List[str]] = None) -> Dict:
        """
        学术文献元数据校验（Crossref + OpenAlex，免费无 key）

        适合校验科研事实断言：
        - "XX 团队 2025 年在 Nature 发表论文证明……"
        - "嫦娥六号样品研究表明月球背面火山活动持续到 28 亿年前"
        - 论文标题/年份/作者存在性

        逻辑：
        1. 构造学术检索 query（实体 + 英文关键词；纯中文断言自动补英文）
        2. Crossref query.bibliographic 与 OpenAlex search 并行
        3. 标题/作者/年份/摘要片段与 claim 做相似度 + 数值比对
        4. 任一源高置信 → verified；摘要级匹配 → partial

        Returns:
            校验结果字典
        """
        cache_key = f"ac:{claim}:{','.join(entities or [])}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        query = self._build_academic_query(claim, entities or [])

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_cr = ex.submit(self._query_crossref, query)
            f_oa = ex.submit(self._query_openalex, query)
            crossref_items = f_cr.result()
            openalex_items = f_oa.result()

        if not crossref_items and not openalex_items:
            result = {
                "status": "unverified",
                "confidence": 0.0,
                "evidence": "学术文献库未找到相关论文",
            }
            _cache_set(cache_key, result)
            return result

        best_confidence = 0.0
        best_evidence = ""
        best_kind = ""  # title | year | author | abstract

        def _evaluate_entry(text: str, meta: str, kind_label: str) -> float:
            nonlocal best_confidence, best_evidence, best_kind
            sim = self._text_similarity(query, text)
            # 实体锚定（2026-09-01 v2，防张冠李戴）：学术条目的标题/摘要必须提及
            # 断言实体（如嫦娥六号），否则可能是同名/相关主题的无关论文
            # （实测：声称「嫦娥六号采集2000克」时 OpenAlex 返回嫦娥五号论文）
            anchor_hit = not entities or any(e and e and e in text for e in entities)
            if not anchor_hit:
                sim *= 0.5
            # 年份矛盾否决：claim 说 2015 年发射，论文年份/正文是 2024 → 不支持断言
            sim = self._apply_year_conflict(claim, text, sim)
            # 数值命中加成（年份尤其重要）
            num_overlap = _numbers_overlap(claim, text)
            if num_overlap["hit"] and num_overlap["ratio"] >= 0.4:
                sim = min(1.0, sim + 0.15)
            if sim > best_confidence:
                best_confidence = sim
                best_evidence = f"学术({kind_label}): {text[:180]}"
                best_kind = kind_label
            return sim

        # Crossref 条目
        for item in crossref_items:
            title = item.get("title") or ""
            year = item.get("published_year") or ""
            authors = ", ".join(item.get("authors", [])[:3])
            container = item.get("container_title", "")
            if title:
                _evaluate_entry(title, f"{container} {year}".strip(), "title")
            if authors:
                _evaluate_entry(authors, "", "author")
            # 摘要相似度（JATS XML 剥标签）
            abstract = item.get("abstract", "")
            if abstract:
                clean_abs = re.sub(r"<[^>]+>", " ", abstract)
                _evaluate_entry(clean_abs[:600], f"{title} abstract", "abstract")

        # OpenAlex 条目
        for item in openalex_items:
            title = item.get("title") or ""
            year = str(item.get("publication_year") or "")
            authors = ", ".join(item.get("authors", [])[:3])
            if title:
                _evaluate_entry(title, f"OpenAlex {year}".strip(), "title")
            if authors:
                _evaluate_entry(authors, "", "author")
            abstract = item.get("abstract", "")
            if abstract:
                _evaluate_entry(abstract[:600], f"{title} abstract", "abstract")

        if best_confidence >= 0.7:
            status = "verified"
        elif best_confidence >= 0.45:
            status = "partial"
        else:
            status = "unverified"

        result = {
            "status": status,
            "confidence": best_confidence,
            "evidence": best_evidence,
            "matched_kind": best_kind,
            "crossref_count": len(crossref_items),
            "openalex_count": len(openalex_items),
        }
        _cache_set(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_academic_query(self, claim: str, entities: List[str]) -> str:
        """构造学术检索 query：实体名 + 断言关键词"""
        parts: List[str] = [e for e in entities if e]
        # 纯中文断言抽取主干（去标点/语气词）
        zh_core = re.sub(r"[，。；、！？,.;!?\s]", "", claim)
        # 截取前 60 字符避免过长查询
        core = zh_core[:60]
        if core and not any(e in core for e in parts):
            parts.append(core)
        if not parts:
            parts.append(claim[:100])
        return " ".join(parts)

    def _query_crossref(self, query: str) -> List[Dict]:
        """查询 Crossref 论文元数据"""
        try:
            resp = self.client.get(
                CROSSREF_API,
                params={
                    "query.bibliographic": query,
                    "rows": 3,
                    "select": "title,author,container-title,published-print,published-online,issued,abstract",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for it in data.get("message", {}).get("items", []):
                title = (it.get("title") or [""])[0]
                if not title:
                    continue
                # 发表年份（优先 print，其次 online，再 issued）
                year = ""
                for key in ("published-print", "published-online", "issued"):
                    dp = it.get(key, {}).get("date-parts", [[None]])
                    if dp and dp[0] and dp[0][0]:
                        year = str(dp[0][0])
                        break
                authors = []
                for a in it.get("author", [])[:4]:
                    name = a.get("family", "") or a.get("name", "")
                    if name:
                        authors.append(name)
                items.append({
                    "title": title,
                    "abstract": it.get("abstract", ""),
                    "container_title": (it.get("container-title") or [""])[0],
                    "published_year": year,
                    "authors": authors,
                })
            return items
        except Exception as e:
            logger.debug(f"[ExternalValidator] Crossref 查询失败: {e}")
            return []

    def _query_openalex(self, query: str) -> List[Dict]:
        """查询 OpenAlex 论文元数据（含摘要重建）"""
        try:
            resp = self.client.get(
                OPENALEX_API,
                params={"search": query, "per-page": 3, "mailto": "yunGuanXingChuan@example.com"},
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for it in data.get("results", []):
                title = it.get("display_name") or it.get("title") or ""
                if not title:
                    continue
                # 重建摘要（abstract_inverted_index: word -> [positions]）
                abstract = ""
                inv = it.get("abstract_inverted_index")
                if inv:
                    pos_map: Dict[int, str] = {}
                    for word, positions in inv.items():
                        for p in positions:
                            pos_map[p] = word
                    if pos_map:
                        abstract = " ".join(pos_map[i] for i in sorted(pos_map))
                authors = []
                for a in (it.get("authorships") or [])[:4]:
                    name = ((a.get("author") or {}).get("display_name")) or ""
                    if name:
                        authors.append(name)
                items.append({
                    "title": title,
                    "abstract": abstract,
                    "publication_year": it.get("publication_year") or "",
                    "authors": authors,
                })
            return items
        except Exception as e:
            logger.debug(f"[ExternalValidator] OpenAlex 查询失败: {e}")
            return []

    def _extract_entities_from_claim(self, claim: str, provided_entities: List[str]) -> List[str]:
        """从 claim 中提取实体（字符串匹配）

        修复（2026-09-01 实测）：调用方传入的 provided entities 是断言已知主体
        （如「任务历时53天」的 entity=嫦娥六号），即使未在 claim 字面出现也应
        优先采纳——否则会误报「未找到可匹配的实体」导致整条真断言 unverified。
        """
        matched = []

        # 调用方显式提供的实体：无条件优先采纳（它们是断言的主体/客体）
        for ent in provided_entities:
            if ent and ent not in matched:
                matched.append(ent)

        # 再从 KG 实体库中匹配
        for kg_ent in self._kg_entities:
            if kg_ent in claim and kg_ent not in matched:
                matched.append(kg_ent)
                if len(matched) >= 5:
                    break

        return matched

    def _query_wikidata_relations(self, entity_name: str) -> List[Dict]:
        """查询实体在 Wikidata 上的关系（含别名；限制 30 条，过滤标号型谓词）"""
        # 先搜索获取 QID
        qid = self._search_entity_qid(entity_name)
        if not qid:
            return []

        # SPARQL 查询关系
        sparql_query = f"""
        SELECT ?predicateLabel ?objectLabel WHERE {{
          wd:{qid} ?p ?object .
          ?predicate wikibase:directClaim ?p .
          OPTIONAL {{ ?predicate rdfs:label ?predLabelZh . FILTER(LANG(?predLabelZh) = "zh") }}
          OPTIONAL {{ ?predicate rdfs:label ?predLabelEn . FILTER(LANG(?predLabelEn) = "en") }}
          BIND(COALESCE(?predLabelZh, ?predLabelEn, "") AS ?predicateLabel)
          OPTIONAL {{ ?object rdfs:label ?objLabelZh . FILTER(LANG(?objLabelZh) = "zh") }}
          OPTIONAL {{ ?object rdfs:label ?objLabelEn . FILTER(LANG(?objLabelEn) = "en") }}
          BIND(COALESCE(?objLabelZh, ?objLabelEn, STR(?object)) AS ?objectLabel)
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
                # 过滤 Wikidata 自动生成的列号/URL 型 object
                if obj.startswith("http") or obj.startswith("Q"):
                    continue
                relations.append({
                    "subject": entity_name,
                    "predicate": pred,
                    "object": obj,
                })
        return relations

    def _search_entity_qid(self, name: str) -> str:
        """搜索实体获取 Wikidata QID（含别名匹配）"""
        cache_key = f"qid:{name}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached.get("qid", "")

        lang = "en" if name.isascii() else "zh"
        qid = ""
        try:
            params = {
                "action": "wbsearchentities",
                "search": name,
                "language": lang,
                "uselang": "zh",
                "format": "json",
                "limit": 3,
                "type": "item",
            }
            resp = self.client.get(WIKIDATA_API, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("search", [])
            if results:
                qid = results[0]["id"]
            # 中文实体在中文 Wikidata 无结果时，用英文名再试
            if not qid and lang == "zh":
                params["search"] = name
                params["language"] = "en"
                resp = self.client.get(WIKIDATA_API, params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("search", [])
                if results:
                    qid = results[0]["id"]
        except Exception as e:
            logger.debug(f"[ExternalValidator] 搜索实体 '{name}' 失败: {e}")
            qid = ""

        _cache_set(cache_key, {"qid": qid})
        return qid

    @staticmethod
    def _is_substring_occurrence(text: str, sub: str) -> bool:
        """检查 sub 在 text 中是否仅作为更长词的子串出现。
        如 claim='嫦娥六号采集样品'，sub='嫦娥' → True（嫦娥是嫦娥六号的一部分，非独立命中）。"""
        for m in re.finditer(re.escape(sub), text):
            start, end = m.start(), m.end()
            before = text[start - 1] if start > 0 else ""
            after = text[end] if end < len(text) else ""
            # 前后紧贴中文/字母/数字 = 属于更长词（子串出现）
            is_wrapped = (
                (before and (before.isalnum() or "\u4e00" <= before <= "\u9fff"))
                or (after and (after.isalnum() or "\u4e00" <= after <= "\u9fff"))
            )
            if not is_wrapped:
                return False  # 存在独立出现
        return True

    @staticmethod
    def _apply_year_conflict(claim: str, text: str, sim: float) -> float:
        """年份矛盾否决：claim 与证据文本的年份集合都非空且无交集时，
        断言与证据冲突（如 claim「2015年发射」vs 百科/论文「2024年」），
        该路证据大幅降权，避免假断言被无关论文/百科佐证成 verified。
        """
        def _years(t: str):
            return {
                n for n, u, _ in _extract_numbers(t)
                if len(n) == 4 and n[0] in "12" and u in ("", "年")
            }
        yc = _years(claim)
        yt = _years(text)
        if yc and yt and not (yc & yt):
            return sim * 0.25
        return sim

    def _check_claim_relation_match(self, claim: str, relation: Dict) -> float:
        """
        检查 claim 与 Wikidata 关系的匹配度

        增强点（2026-09-01 v2，实测后修复假阳性）：
        - 弱元数据关系（得名自/所在天体/作品主题等）不构成断言证据，直接 0
        - 对象是 claim 内更长词的子串（如「嫦娥」⊂「嫦娥六号」）不算独立命中
        - 年份/数值断言：Wikidata 对象年份与 claim 年份精确一致 → 强证据；
          不一致 → 0（矛盾压制）

        Returns:
            匹配度 0.0 ~ 1.0
        """
        obj = relation.get("object", "")
        pred = relation.get("predicate", "")
        claim_lower = claim.lower()
        pred_norm = pred.strip().lower()

        # 日期型对象归一化：2024-05-03T00:00:00Z / 2024-05-03 → 2024（参与年份比对）
        date_m = re.match(r"^(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}", obj or "")
        if date_m:
            obj = date_m.group(0)[:4]

        # 1. 弱元数据关系：只描述实体归属/命名，不能验证具体行为断言
        weak_meta_keywords = (
            "得名", "named after", "所在天体", "作品主题", "main subject",
            "celestial body", "located on", "located in", "所属", "mother",
            "child", "parent", "has part", "subclass of", "instance of",
            "发现或发明时间", "成立时间", "成立或创建时间", "发现时间", "inception",
            "discovery or invention time", "首次记载", "首次提及",
        )
        if any(w in pred_norm for w in weak_meta_keywords):
            return 0.0

        # 2. 对象名独立出现在 claim 中 → 强匹配（防子串误判）
        if obj and len(obj) >= 2 and obj in claim and not self._is_substring_occurrence(claim, obj):
            return 0.88

        # 3. 数值/年份断言
        claim_years = [n for n, _, _ in _extract_numbers(claim) if len(n) == 4 and n[0] in "12"]
        obj_is_year = bool(re.fullmatch(r"(19|20)\d{2}", obj or ""))
        if obj_is_year:
            if obj in claim:
                return 0.95  # 年份精确一致（如 Wikidata launch date 2024-05-03 → claim 2024）
            if claim_years and obj not in claim:
                return 0.0  # 年份矛盾：claim 说 2015 发射，Wikidata 记录别的年份 → 重大矛盾
            return 0.7

        # 数值对象（非年份）精确命中
        if re.fullmatch(r"\d+(?:\.\d+)?", obj or ""):
            nums_in_claim = [n for n, _, _ in _extract_numbers(claim)]
            if obj in nums_in_claim:
                return 0.85
            # 数值不一致（claim 含其他大数/年份）→ 无支持证据
            return 0.0

        # 4. 谓词关键词出现在 claim 中 → 中匹配
        pred_keywords = re.findall(r"[a-zA-Z_]+", pred.lower())
        pred_zh_map = {
            "launch": "发射", "land": "着陆", "return": "返回", "sample": "采样",
            "discover": "发现", "publish": "发表", "study": "研究", "show": "表明",
            "found": "发现", "carry": "搭载", "support": "支持", "part": "属于",
            "collaborat": "合作", "achieved": "实现", "develop": "研发", "orbit": "轨道",
            "surface": "表面", "mission": "任务", "year": "年", "date": "日期",
            "evidence": "证据", "produce": "产出",
        }
        matched_words = 0
        total_words = max(len(pred_keywords), 1)
        for w in pred_keywords:
            stem = w.rstrip("s")
            if w in claim_lower or stem in claim_lower:
                matched_words += 1
                continue
            zh_hint = pred_zh_map.get(stem)
            if zh_hint and zh_hint in claim:
                matched_words += 1
        if matched_words / total_words > 0.5:
            return 0.6

        # 5. 对象名部分匹配（关键词组，防子串）
        if obj and len(obj) >= 2 and not self._is_substring_occurrence(claim, obj):
            obj_words = re.findall(r"[a-zA-Z]{2,}", obj.lower())
            if not obj_words and len(obj) <= 12:  # 中文对象按整串 substring
                if obj in claim:
                    return 0.5
            else:
                obj_matched = sum(1 for w in obj_words if w in claim_lower)
                if obj_words and obj_matched / len(obj_words) > 0.5:
                    return 0.5

        return 0.0

    def _search_wikipedia(self, query: str, lang: str = "zh", max_pages: int = 2) -> List[str]:
        """搜索 Wikipedia 获取相关段落（增强：max_pages 页 + 摘要扩至 1500 字符）"""
        api_url = WIKIPEDIA_API_ZH if lang == "zh" else WIKIPEDIA_API_EN

        # 先搜索获取页面标题
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_pages,
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
        for title in titles[:max_pages]:
            extract = self._get_wikipedia_extract(title, lang)
            if extract:
                paragraphs.append(extract)

        return paragraphs

    def _get_wikipedia_extract(self, title: str, lang: str = "zh") -> str:
        """获取 Wikipedia 页面的摘要段落（exintro 扩至 1500 字符）"""
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
                    return extract[:1500]  # 限制长度
        except Exception as e:
            logger.debug(f"[ExternalValidator] Wikipedia 获取摘要失败: {e}")
        return ""

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """
        计算两段文本的相似度（不依赖 LLM）

        增强点（2026-09-01）：
        - 英文：单词覆盖（大小写归一、词干）
        - 中文：bigram + 实体词组（长度 >= 2 的连续中文片段）双通道
        - 数值命中单独加分（与 _numbers_overlap 配合在调用侧使用，此处基础分）
        - 覆盖率权重 0.75（claim 较短，以其为基准）
        """
        if not text_a or not text_b:
            return 0.0

        def extract_keywords(text: str) -> set:
            import re
            words = set()
            # 英文单词（词干化：去掉常见后缀）
            en_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
            for w in en_words:
                words.add(w)
                stem = w.rstrip("eds")
                if len(stem) >= 3:
                    words.add(stem)
            # 中文 bigram
            zh_chars = re.findall(r'[\u4e00-\u9fff]', text)
            for i in range(len(zh_chars) - 1):
                words.add(zh_chars[i] + zh_chars[i + 1])
            # 中文连续词组（2-4 字滑动窗口，捕获专有名词片段）
            zh_text = "".join(zh_chars)
            for span in (2, 3):
                for i in range(len(zh_text) - span + 1):
                    words.add(zh_text[i:i + span])
            # 数字
            numbers = re.findall(r'\d+', text)
            words.update(numbers)
            return words

        kw_a = extract_keywords(text_a)
        kw_b = extract_keywords(text_b)

        if not kw_a or not kw_b:
            return 0.0

        intersection = kw_a & kw_b

        # 覆盖率：claim 的关键词在段落中出现的比例（权重 0.75）
        coverage = len(intersection) / len(kw_a) if kw_a else 0.0
        # Jaccard（权重 0.25）
        jaccard = len(intersection) / len(kw_a | kw_b)

        similarity = 0.75 * coverage + 0.25 * jaccard
        return min(similarity, 1.0)

    def _combine_signals(self, wd_result: Dict, wp_result: Dict, ac_result: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        综合 Wikidata / Wikipedia / Academic 三路信号

        设计原则（2026-09-01 重构）：
        - verified：至少一路强证据(>=0.7) + 另一路 partial 佐证；或两路强证据
        - partial：单路强证据但无佐证；或多路 partial
        - unverified：全路未命中
        - 数值断言命中提升合成置信度（上限 0.97）
        - 不因单路 unverified 惩罚过重（原实现 ×0.3/×0.85 导致普遍低置信）

        Returns:
            (status, confidence, evidence)
        """
        ac_result = ac_result or {}

        # 收集各路信号与置信度
        signals = [
            ("wikidata", wd_result.get("status", "unverified"), wd_result.get("confidence", 0.0), wd_result.get("evidence", "")),
            ("wikipedia", wp_result.get("status", "unverified"), wp_result.get("confidence", 0.0), wp_result.get("evidence", "")),
            ("academic", ac_result.get("status", "unverified"), ac_result.get("confidence", 0.0), ac_result.get("evidence", "")),
        ]
        verified_sigs = [s for s in signals if s[1] == "verified"]
        partial_sigs = [s for s in signals if s[1] == "partial"]
        # 强证据阈值与 verified 状态判定对齐（0.6）：状态 verified 但分数 0.62~0.7
        # 的百科证据同样是有效强证据（原 0.7 阈值导致状态与分数脱节，真实断言被误降级）
        strong_verified = [s for s in verified_sigs if s[2] >= 0.6]
        all_conf = [s[2] for s in signals]

        evidence_parts = []
        for name, status, conf, ev in signals:
            if ev:
                evidence_parts.append(ev[:150])
        evidence = " | ".join(evidence_parts)

        # --- 判定 ---
        # 0. 荒谬断言防护：Wd+Wp 全 unverified（连主题实体在百科都无任何支持）
        #    且唯一强证据来自 academic → 只给低置信 partial（防「月球由奶酪构成」翻盘）
        wd_wp_both_unverified = all(
            s[1] == "unverified" for s in signals if s[0] in ("wikidata", "wikipedia")
        )

        # 1. 两路及以上强证据 → verified 高置信
        if len(strong_verified) >= 2:
            conf = min(0.97, max(s[2] for s in strong_verified) + 0.05)
            return "verified", conf, evidence

        # 2. 一路强证据 + 至少一路 partial 佐证 → verified
        if strong_verified and partial_sigs:
            # 佐证必须确实命中（partial 且置信度 >= 0.3），避免空转的 partial 拉高结论
            real_partial = [s for s in partial_sigs if s[2] >= 0.3]
            if real_partial:
                conf = min(0.93, max(s[2] for s in strong_verified) + 0.05)
                return "verified", conf, evidence

        # 3. 一路强证据无有效佐证 → partial
        if strong_verified:
            # 单路 academic 且 wd/wp 均未命中 → 低置信 partial（防张冠李戴/荒谬断言）
            if strong_verified[0][0] == "academic" and wd_wp_both_unverified:
                return "partial", min(0.5, strong_verified[0][2]), evidence
            return "partial", min(0.75, strong_verified[0][2]), evidence

        # 4. 两路及以上 partial → partial
        if len(partial_sigs) >= 2:
            avg = sum(s[2] for s in partial_sigs) / len(partial_sigs)
            # wd/wp 全 unverified 时，两路弱 partial 也不该上浮（荒谬断言防护）
            if wd_wp_both_unverified:
                return "partial", min(0.55, avg + 0.05), evidence
            return "partial", min(0.65, avg + 0.05), evidence

        # 5. 单路 partial → partial 低置信
        if partial_sigs:
            return "partial", min(0.5, partial_sigs[0][2]), evidence

        # 6. 全 unverified
        max_conf = max(all_conf) if all_conf else 0.0
        return "unverified", max_conf * 0.4, evidence or "无外部证据支持"

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