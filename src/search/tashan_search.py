"""
云观星传 - 他山世界（TopicLab）学术搜索服务
作为统一搜索的核心引擎接入，提供：
  - AMiner 精确学术检索（需配置 TASHAN_TOKEN，1.15 亿论文 + 6200 万专利）
  - source-feed 信源文章（浏览式发现，多页抓取）
  - WorldWeave 近 30 天信源/信号召回（多 scene × 多查询词）

设计原则：
- **多多调用**：同一议题拆多个查询词（中英变体/关键词），每个查询 × 多 scene 并行召回
- 全部调用 try/except 降级：单路失败不影响其他
- AMiner 未配置 token 时自动跳过（日志说明），配置后启用
"""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import TASHAN_TOKEN

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.tavily_search import SearchSource

logger = logging.getLogger(__name__)

# 他山世界 API 基础地址
TASHAN_BASE_URL = "https://world.tashan.chat/api/v1"

# 来源标识（与 issue #42 约定一致，新增 literature/signals 两路）
SOURCE_AMINER = "TashanAminer"
SOURCE_SOURCE_FEED = "TashanSourceFeed"
SOURCE_WORLD_WEAVE = "TashanWorldWeave"
SOURCE_LITERATURE = "TashanLiterature"
SOURCE_WORLD_SIGNALS = "TashanWorldSignals"

# WorldWeave 多 scene（global=全球 / technology=科技，均已实测可用；可扩展）
WORLD_WEAVE_SCENES = ["global", "technology"]


class TashanSearchService:
    """他山世界搜索封装：AMiner + 信源 + WorldWeave（多查询 × 多 scene）"""

    def __init__(self, timeout: float = 30.0, token: Optional[str] = None):
        self.timeout = timeout
        self.token = token if token is not None else TASHAN_TOKEN
        self._http_client = None

    def _get_http_client(self):
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.Client(timeout=self.timeout)
            except ImportError:
                logger.error("httpx 未安装，请执行: pip install httpx")
                return None
        return self._http_client

    def _safe_get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        """带 try/except 的 GET 请求；配置 token 时自动附加（query + Bearer header）"""
        client = self._get_http_client()
        if not client:
            return None
        params = dict(params or {})
        if self.token:
            params.setdefault("token", self.token)
            headers = dict(headers or {})
            headers.setdefault("Authorization", f"Bearer {self.token}")
        try:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("detail") and not _has_results(data):
                return None
            return data
        except Exception as e:
            logger.warning(f"他山 API 请求失败 ({url}): {e}")
            return None

    # ------------------------------------------------------------------
    # AMiner（需 token）
    # ------------------------------------------------------------------
    def _search_aminer(self, topic: str) -> List[SearchSource]:
        """AMiner 精确学术检索（最核心；未配置 token 时跳过并说明）"""
        if not self.token:
            logger.info("未配置 TASHAN_TOKEN，跳过 AMiner 学术检索（配置后自动启用）")
            return []
        url = f"{TASHAN_BASE_URL}/aminer/paper/search"
        data = self._safe_get(url, params={"title": topic})
        if not data:
            return []

        papers = data.get("data", {}).get("list") or data.get("papers") or data.get("list") or []
        if isinstance(data, dict) and "data" in data and isinstance(data.get("data"), list):
            papers = data["data"]

        results: List[SearchSource] = []
        for p in papers or []:
            if not isinstance(p, dict):
                continue
            title = p.get("title") or p.get("name") or ""
            url = p.get("url") or p.get("link") or ""
            authors = p.get("authors") or p.get("author") or ""
            venue = p.get("venue") or p.get("journal") or ""
            year = p.get("year") or p.get("publish_year") or ""
            content = p.get("abstract") or p.get("summary") or p.get("description") or ""
            snippet = content
            if authors:
                snippet = f"作者: {authors}；" + snippet
            if venue:
                snippet = f"期刊: {venue}；" + snippet
            if year:
                snippet = f"年份: {year}；" + snippet
            results.append(SearchSource(
                url=url, title=title, content=snippet,
                score=float(p.get("score") or p.get("relevance", 0.0) or 0.0),
                source=SOURCE_AMINER,
            ))
        logger.info(f"他山 AMiner '{topic[:30]}...' 返回 {len(results)} 条")
        return results

    # ------------------------------------------------------------------
    # source-feed（多页抓取）
    # ------------------------------------------------------------------
    def _search_source_feed(self, topic: str, page: int = 1) -> List[SearchSource]:
        """信源文章浏览式发现（支持分页）"""
        url = f"{TASHAN_BASE_URL}/source-feed/articles"
        data = self._safe_get(url, params={"page": page, "page_size": 20})
        if not data:
            return []

        articles = data.get("list") or data.get("data", {}).get("list") or []
        results: List[SearchSource] = []
        for a in articles:
            if not isinstance(a, dict):
                continue
            title = a.get("title") or ""
            url = a.get("url") or ""
            if topic and title:
                lowered = (title + " " + (a.get("description") or "")).lower()
                if topic.lower() not in lowered:
                    continue
            content = a.get("description") or ""
            feed = a.get("source_feed_name") or ""
            if feed:
                content = f"信源: {feed}；" + content if content else f"信源: {feed}"
            results.append(SearchSource(
                url=url, title=title, content=content, score=0.0, source=SOURCE_SOURCE_FEED,
            ))
        logger.info(f"他山信源 '{topic[:30]}...' page={page} 返回 {len(results)} 条")
        return results

    # ------------------------------------------------------------------
    # WorldWeave（多 scene × 多查询）
    # ------------------------------------------------------------------
    def _search_world_weave(self, topic: str, scene: str = "global", query_terms: Optional[List[str]] = None) -> List[SearchSource]:
        """WorldWeave 近 30 天信源/信号召回（scene 维度：global/technology...）

        注意：该接口为"热点信号流"，query 仅作弱约束（fallback 时返回场景热点），
        因此按 query_terms 做相关性过滤，不相关信号不混入上下文（避免污染 LLM）。
        """
        url = f"{TASHAN_BASE_URL}/world/source-knowledge/recall"
        data = self._safe_get(url, params={"scene": scene, "query": topic, "limit": 10})
        if not data:
            return []

        terms = [t for t in (query_terms or [topic]) if t]
        signals = data.get("signals") or data.get("data", {}).get("signals") or []
        results: List[SearchSource] = []
        for s in signals:
            if not isinstance(s, dict):
                continue
            title = s.get("title") or ""
            url = s.get("url") or ""
            content = s.get("summary") or ""
            # 相关性过滤：任一查询词出现在标题/摘要才保留（主题弱约束 → 过滤热点噪声）
            if terms:
                haystack = (title + " " + content).lower()
                if not any(t.lower() in haystack for t in terms):
                    continue
            region = s.get("region_label") or ""
            published = s.get("published_at") or ""
            if region:
                content = f"[{region}] " + content
            if published:
                content = content + f"（发布于 {published[:10]}）" if content else f"发布于 {published[:10]}"
            results.append(SearchSource(
                url=url, title=title, content=content,
                score=float(s.get("recall_score") or 0.0),
                source=SOURCE_WORLD_WEAVE,
            ))
        logger.info(f"他山 WorldWeave '{topic[:30]}...' scene={scene} 召回 {len(signals)} 过滤后 {len(results)} 条")
        return results

    # ------------------------------------------------------------------
    # 近期学术（literature/recent，免鉴权）+ WorldWeave 最近信号（world/signals）
    # ------------------------------------------------------------------
    def _search_literature_recent(self, query_terms: Optional[List[str]] = None) -> List[SearchSource]:
        """近期学术论文扫描（GET /api/v1/literature/recent），按主题词过滤"""
        url = f"{TASHAN_BASE_URL}/literature/recent"
        data = self._safe_get(url, params={"limit": 30})
        if not data:
            return []

        terms = [t for t in (query_terms or []) if t]
        papers = data.get("list") or []
        results: List[SearchSource] = []
        for p in papers:
            if not isinstance(p, dict):
                continue
            title = p.get("title") or ""
            url = p.get("url") or ""
            if terms:
                haystack = (title + " " + " ".join(p.get("authors") or [])).lower()
                if not any(t.lower() in haystack for t in terms):
                    continue
            authors = "、".join(p.get("authors") or [])
            category = p.get("compact_category") or p.get("category") or ""
            published = str(p.get("published_day") or "")
            content = f"作者: {authors}" if authors else ""
            if category:
                content = (content + "；" if content else "") + f"分类: {category}"
            if published:
                content = (content + "；" if content else "") + f"发布于: {published}"
            results.append(SearchSource(
                url=url, title=title, content=content, score=0.0, source=SOURCE_LITERATURE,
            ))
        logger.info(f"他山近期学术 召回 {len(papers)} 过滤后 {len(results)} 条")
        return results

    def _search_world_signals(self, query_terms: Optional[List[str]] = None) -> List[SearchSource]:
        """WorldWeave 最近信号流（GET /api/v1/world/signals），按主题词过滤"""
        url = f"{TASHAN_BASE_URL}/world/signals"
        data = self._safe_get(url, params={"scene": "global", "limit": 20})
        if not data:
            return []

        terms = [t for t in (query_terms or []) if t]
        signals = data.get("signals") or []
        results: List[SearchSource] = []
        for s in signals:
            if not isinstance(s, dict):
                continue
            title = s.get("title") or ""
            url = s.get("url") or ""
            content = s.get("summary") or ""
            if terms:
                haystack = (title + " " + content).lower()
                if not any(t.lower() in haystack for t in terms):
                    continue
            region = s.get("region_label") or s.get("region") or ""
            if region:
                content = f"[{region}] " + content
            results.append(SearchSource(
                url=url, title=title, content=content,
                score=float(s.get("recall_score") or 0.0),
                source=SOURCE_WORLD_SIGNALS,
            ))
        logger.info(f"他山最近信号 召回 {len(signals)} 过滤后 {len(results)} 条")
        return results

    # ------------------------------------------------------------------
    # 主入口：多查询 × 多 scene 全量召回
    # ------------------------------------------------------------------
    @staticmethod
    def expand_queries(topic: str, extra_queries: Optional[List[str]] = None) -> List[str]:
        """扩展查询词：议题原词 + 变体（去空/去重，最多 4 个），提升他山召回覆盖面"""
        queries = [topic]
        # 中文议题补常见检索变体
        t = topic.strip()
        for kw in (extra_queries or []):
            kw = str(kw).strip()
            if kw and kw != t:
                queries.append(kw)
        # 通用航天/科技变体（他山信源覆盖广）
        if "嫦娥" in t or "月球" in t:
            queries.append("月球探测 国际合作")
        elif "火箭" in t or "航天" in t or "卫星" in t:
            queries.append("商业航天 国际报道")
        # 去重去空，上限 4 个
        seen, out = set(), []
        for q in queries:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        return out[:4]

    def search_for_topic(self, topic: str, extra_queries: Optional[List[str]] = None) -> List[SearchSource]:
        """
        为科技议题执行他山全量召回：AMiner（有 token）+ 信源多页 + WorldWeave 多 scene × 多查询词
        """
        queries = self.expand_queries(topic, extra_queries)
        all_sources: Dict[str, SearchSource] = {}

        def _merge(sources: List[SearchSource]):
            for s in sources:
                key = (s.source, s.url) if s.url else id(s)
                if key not in all_sources:
                    all_sources[key] = s

        # WorldWeave：每个 scene × 每个查询词（最多 4×2=8 次调用），按全部查询词过滤相关性
        for scene in WORLD_WEAVE_SCENES:
            for q in queries:
                _merge(self._safe_call(self._search_world_weave, q, scene=scene, query_terms=queries))

        # 近期学术扫描（literature/recent）+ 最近信号流（world/signals）：免鉴权，多多调用
        _merge(self._safe_call(self._search_literature_recent, queries))
        _merge(self._safe_call(self._search_world_signals, queries))

        # source-feed：前 2 页 × 主题过滤
        for page in (1, 2):
            _merge(self._safe_call(self._search_source_feed, topic, page=page))

        # AMiner（配置 token 后启用）：每个查询词
        if self.token:
            for q in queries:
                _merge(self._safe_call(self._search_aminer, q))

        results = list(all_sources.values())
        logger.info(f"他山议题 '{topic[:30]}...' 共 {len(queries)} 查询词 × {len(WORLD_WEAVE_SCENES)} scene，去重后 {len(results)} 条")
        return results

    @staticmethod
    def _safe_call(fn, *args, **kwargs) -> List[SearchSource]:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"他山搜索子模块失败（不影响整体）: {e}")
            return []


def _has_results(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("list", "signals", "papers", "data"):
        if data.get(key):
            return True
    return False


# 全局单例
_tashan_service: Optional[TashanSearchService] = None


def get_tashan_search_service() -> TashanSearchService:
    global _tashan_service
    if _tashan_service is None:
        _tashan_service = TashanSearchService()
    return _tashan_service
