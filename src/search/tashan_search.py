"""
云观星传 - 他山世界（TopicLab）学术搜索服务
作为统一搜索的第三引擎接入，提供 Tavily/百炼给不了的学术能力：
  - AMiner 精确学术检索（约 1.15 亿论文 + 6200 万专利）
  - source-feed 信源文章（浏览式发现）
  - WorldWeave 近 30 天信源/信号召回

除 AMiner（部分场景需鉴权 token）外，其余入口匿名即可调用。
全部调用均 try/except 降级：他山不可达时返回空列表，不影响主流程。
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.tavily_search import SearchSource

logger = logging.getLogger(__name__)

# 他山世界 API 基础地址
TASHAN_BASE_URL = "https://world.tashan.chat/api/v1"

# 三个来源的标识（与 issue #42 约定一致）
SOURCE_AMINER = "TashanAminer"
SOURCE_SOURCE_FEED = "TashanSourceFeed"
SOURCE_WORLD_WEAVE = "TashanWorldWeave"


class TashanSearchService:
    """他山世界搜索封装：AMiner + 信源 + WorldWeave"""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._http_client = None

    def _get_http_client(self):
        """延迟初始化 httpx 客户端"""
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.Client(timeout=self.timeout)
                logger.info("他山世界 httpx 客户端初始化成功")
            except ImportError:
                logger.error("httpx 未安装，请执行: pip install httpx")
                return None
        return self._http_client

    def _safe_get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """带 try/except 的 GET 请求，任何异常返回 None（降级）"""
        client = self._get_http_client()
        if not client:
            return None
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            # 兼容他山某些接口把错误包在 detail/json 字符串里
            if isinstance(data, dict) and data.get("detail") and not _has_results(data):
                return None
            return data
        except Exception as e:
            logger.warning(f"他山 API 请求失败 ({url}): {e}")
            return None

    def _search_aminer(self, topic: str) -> List[SearchSource]:
        """
        AMiner 精确学术检索（最核心）
        GET /api/v1/aminer/paper/search?title=<topic>
        """
        url = f"{TASHAN_BASE_URL}/aminer/paper/search"
        # 该接口使用 title 作为查询参数（实测匿名调用返回 Token Parse Error，
        # 属于可预期的鉴权降级场景；若配置了有效 token 则正常返回）
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
                url=url,
                title=title,
                content=snippet,
                score=float(p.get("score") or p.get("relevance", 0.0) or 0.0),
                source=SOURCE_AMINER,
            ))

        logger.info(f"他山 AMiner 搜索 '{topic[:30]}...' 返回 {len(results)} 条论文结果")
        return results

    def _search_source_feed(self, topic: str) -> List[SearchSource]:
        """
        信源文章浏览式发现
        GET /api/v1/source-feed/articles
        """
        url = f"{TASHAN_BASE_URL}/source-feed/articles"
        data = self._safe_get(url)
        if not data:
            return []

        articles = data.get("list") or data.get("data", {}).get("list") or []
        if not articles:
            return []

        results: List[SearchSource] = []
        for a in articles:
            if not isinstance(a, dict):
                continue
            title = a.get("title") or ""
            url = a.get("url") or ""
            # 简单按关键词做浏览式过滤，提高相关性
            if topic and title:
                lowered = (title + " " + (a.get("description") or "")).lower()
                if topic.lower() not in lowered:
                    continue
            content = a.get("description") or ""
            feed = a.get("source_feed_name") or ""
            if feed:
                content = f"信源: {feed}；" + content if content else f"信源: {feed}"
            results.append(SearchSource(
                url=url,
                title=title,
                content=content,
                score=0.0,
                source=SOURCE_SOURCE_FEED,
            ))

        logger.info(f"他山信源搜索 '{topic[:30]}...' 返回 {len(results)} 条文章结果")
        return results

    def _search_world_weave(self, topic: str) -> List[SearchSource]:
        """
        WorldWeave 近 30 天信源/信号召回
        GET /api/v1/world/source-knowledge/recall?scene=global&query=<topic>&limit=8
        """
        url = f"{TASHAN_BASE_URL}/world/source-knowledge/recall"
        data = self._safe_get(url, params={"scene": "global", "query": topic, "limit": 8})
        if not data:
            return []

        signals = data.get("signals") or data.get("data", {}).get("signals") or []
        results: List[SearchSource] = []
        for s in signals:
            if not isinstance(s, dict):
                continue
            title = s.get("title") or ""
            url = s.get("url") or ""
            content = s.get("summary") or ""
            region = s.get("region_label") or ""
            published = s.get("published_at") or ""
            if region:
                content = f"[{region}] " + content
            if published:
                content = content + f"（发布于 {published[:10]}）" if content else f"发布于 {published[:10]}"
            results.append(SearchSource(
                url=url,
                title=title,
                content=content,
                score=float(s.get("recall_score") or 0.0),
                source=SOURCE_WORLD_WEAVE,
            ))

        logger.info(f"他山 WorldWeave 搜索 '{topic[:30]}...' 返回 {len(results)} 条信号结果")
        return results

    def search_for_topic(self, topic: str) -> List[SearchSource]:
        """
        为科技议题执行他山三路搜索（AMiner + 信源 + WorldWeave），合并去重

        Args:
            topic: 科技议题名称

        Returns:
            合并去重后的 SearchSource 列表，每条标注 source 字段
        """
        all_sources: Dict[str, SearchSource] = {}

        # 三路都走降级，单路失败不影响其他
        a = self._safe_call(self._search_aminer, topic)
        s = self._safe_call(self._search_source_feed, topic)
        w = self._safe_call(self._search_world_weave, topic)

        for source in a + s + w:
            # 用 (source, url) 组合去重；无 url 时保留全部
            key = (source.source, source.url) if source.url else id(source)
            if key not in all_sources:
                all_sources[key] = source

        results = list(all_sources.values())
        logger.info(f"他山议题 '{topic[:30]}...' 共获取 {len(results)} 条去重结果")
        return results

    @staticmethod
    def _safe_call(fn, *args, **kwargs) -> List[SearchSource]:
        """单路降级包装：任何异常返回空列表"""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"他山搜索子模块失败（不影响整体）: {e}")
            return []


def _has_results(data: Dict) -> bool:
    """判断响应里是否含有效结果（用于识别包在 detail 里的错误）"""
    if not isinstance(data, dict):
        return False
    for key in ("list", "signals", "papers", "data"):
        val = data.get(key)
        if val:
            return True
    return False


# 全局单例
_tashan_service: Optional[TashanSearchService] = None


def get_tashan_search_service() -> TashanSearchService:
    """获取他山搜索服务全局单例"""
    global _tashan_service
    if _tashan_service is None:
        _tashan_service = TashanSearchService()
    return _tashan_service
