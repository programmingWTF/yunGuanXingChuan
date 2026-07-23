"""
云观星传 - Tavily AI 搜索服务
提供带 URL 的结构化搜索结果，供 Agent 使用并在前端展示来源
直接调用 Tavily REST API（通过 httpx + 代理）
"""
import os
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import TAVILY_API_KEY

logger = logging.getLogger(__name__)

# 代理配置：仅当 .env 中明确设置 TAVILY_PROXY 时才使用，否则直连
PROXY_URL = os.getenv("TAVILY_PROXY", "")  # 空字符串 = 不走代理
TAVILY_API_URL = "https://api.tavily.com/search"


class SearchSource:
    """搜索来源条目"""

    def __init__(self, url: str, title: str, content: str = "", score: float = 0.0, source: str = "TavilySearch"):
        self.url = url
        self.title = title
        self.content = content
        self.score = score
        self.source = source  # 搜索引擎来源标识: "TavilySearch" 或 "QwenWebSearch"

    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content[:300] if self.content else "",
            "score": round(self.score, 3),
            "source": self.source,
        }


class TavilySearchService:
    """Tavily 搜索封装：直接调用 REST API，支持代理"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TAVILY_API_KEY
        self._http_client = None

    def _get_http_client(self):
        """延迟初始化 httpx 客户端（带代理）"""
        if self._http_client is None:
            if not self.api_key:
                logger.warning("TAVILY_API_KEY 未配置，搜索功能不可用")
                return None
            try:
                import httpx
                self._http_client = httpx.Client(
                    proxy=PROXY_URL if PROXY_URL else None,
                    timeout=60.0,
                )
                logger.info(f"Tavily httpx 客户端初始化成功，代理: {PROXY_URL or '无'}")
            except ImportError:
                logger.error("httpx 未安装，请执行: pip install httpx")
                return None
        return self._http_client

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
    ) -> List[SearchSource]:
        """
        执行 Tavily 搜索（直接调用 REST API）
        """
        client = self._get_http_client()
        if not client:
            return []

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "topic": topic,
                "include_raw_content": False,
            }
            response = client.post(TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(SearchSource(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                ))

            logger.info(f"Tavily 搜索 '{query[:30]}...' 返回 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"Tavily 搜索失败: {e}")
            return []

    def search_for_topic(self, topic: str) -> List[SearchSource]:
        """
        为科技议题执行多角度搜索（科学事实 + 国际报道）

        Args:
            topic: 科技议题名称

        Returns:
            合并去重后的 SearchSource 列表
        """
        queries = [
            f"{topic} 科学事实 技术参数 最新进展",
            f"{topic} international media coverage report",
            f"{topic} 国际舆论 报道框架",
        ]

        all_sources: Dict[str, SearchSource] = {}  # 用 URL 去重

        for query in queries:
            results = self.search(query, max_results=5)
            for source in results:
                if source.url and source.url not in all_sources:
                    all_sources[source.url] = source

        sources = list(all_sources.values())
        logger.info(f"议题 '{topic}' 共获取 {len(sources)} 条去重搜索来源")
        return sources

    def format_search_context(self, sources: List[SearchSource]) -> str:
        """
        将搜索结果格式化为可注入 LLM prompt 的上下文文本

        Args:
            sources: 搜索来源列表

        Returns:
            格式化的上下文字符串
        """
        if not sources:
            return ""

        lines = ["## 联网搜索内容（请基于以下真实信息分析）\n"]
        for i, s in enumerate(sources[:12], 1):
            source_tag = f"[{s.source}]" if s.source else ""
            lines.append(f"[{i}] {source_tag} {s.title}")
            if s.url:
                lines.append(f"    来源: {s.url}")
            if s.content:
                lines.append(f"    摘要: {s.content[:200]}")
            lines.append("")

        return "\n".join(lines)


# 全局单例
_search_service: Optional[TavilySearchService] = None


def get_search_service() -> TavilySearchService:
    """获取全局搜索服务单例"""
    global _search_service
    if _search_service is None:
        _search_service = TavilySearchService()
    return _search_service


def get_unified_search_service():
    """获取统一搜索服务（Tavily + 百炼 WebSearch）"""
    from src.search.unified_search import UnifiedSearchService
    return UnifiedSearchService()
