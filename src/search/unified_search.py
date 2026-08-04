"""
云观星传 - 统一搜索服务
同时调用 Tavily AI Search、阿里云百炼 WebSearch MCP 与他山世界搜索，
合并结果并标注每条来源引擎
"""
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.tavily_search import TavilySearchService, SearchSource, get_search_service
from src.search.qwen_websearch import QwenWebSearchService
from src.search.tashan_search import TashanSearchService, get_tashan_search_service

logger = logging.getLogger(__name__)


class UnifiedSearchService:
    """统一搜索服务：合并 Tavily + 百炼 WebSearch + 他山世界"""

    def __init__(self, with_tashan: bool = True):
        self.tavily = get_search_service()
        self.qwen = QwenWebSearchService()
        self.tashan = get_tashan_search_service() if with_tashan else None

    def search_for_topic(self, topic: str) -> List[SearchSource]:
        """
        为科技议题执行三引擎并行搜索，合并去重

        Args:
            topic: 科技议题名称

        Returns:
            合并后的 SearchSource 列表，每条标注 source 字段
        """
        all_sources: List[SearchSource] = []
        seen_urls: set = set()

        # 并行执行三个搜索引擎（Tavily + 百炼 + 他山）
        tavily_sources: List[SearchSource] = []
        qwen_pages: List[Dict] = []
        tashan_sources: List[SearchSource] = []

        def _run_tavily():
            try:
                return self.tavily.search_for_topic(topic)
            except Exception as e:
                logger.warning(f"Tavily 搜索失败（不影响整体）: {e}")
                return []

        def _run_qwen():
            try:
                return self.qwen.search_for_topic(topic)
            except Exception as e:
                logger.warning(f"百炼 WebSearch 搜索失败（不影响整体）: {e}")
                return []

        def _run_tashan():
            if not self.tashan:
                return []
            try:
                return self.tashan.search_for_topic(topic)
            except Exception as e:
                logger.warning(f"他山搜索失败（不影响整体）: {e}")
                return []

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_tavily = executor.submit(_run_tavily)
            future_qwen = executor.submit(_run_qwen)
            future_tashan = executor.submit(_run_tashan)

            tavily_sources = future_tavily.result()
            qwen_pages = future_qwen.result()
            tashan_sources = future_tashan.result()

        # 1. 处理 Tavily 结果
        for s in tavily_sources:
            s.source = "TavilySearch"
            if s.url and s.url not in seen_urls:
                seen_urls.add(s.url)
                all_sources.append(s)
            elif not s.url:
                all_sources.append(s)
        logger.info(f"Tavily 搜索获取 {len(tavily_sources)} 条结果")

        # 2. 处理百炼 WebSearch 结果
        for page in qwen_pages:
            url = page.get("url", "") or page.get("link", "")
            title = page.get("title", "") or page.get("name", "")
            snippet = page.get("snippet", "") or page.get("description", "") or page.get("content", "")
            # 兼容百炼返回的不同字段名
            if not snippet and "text" in page:
                snippet = page["text"]

            # 去重
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            source = SearchSource(
                url=url,
                title=title,
                content=snippet,
                score=0.0,
                source="QwenWebSearch",
            )
            all_sources.append(source)
        logger.info(f"百炼 WebSearch 获取 {len(qwen_pages)} 条结果")

        # 3. 处理他山世界结果（第三个引擎）
        for s in tashan_sources:
            if s.url and s.url in seen_urls:
                continue
            if s.url:
                seen_urls.add(s.url)
            if not s.source:
                s.source = "TashanSearch"
            all_sources.append(s)
        logger.info(f"他山世界获取 {len(tashan_sources)} 条结果")

        tashan_count = sum(1 for s in all_sources if s.source in ("TashanAminer", "TashanSourceFeed", "TashanWorldWeave", "TashanSearch"))
        logger.info(f"统一搜索共获取 {len(all_sources)} 条去重结果 "
                    f"(Tavily: {sum(1 for s in all_sources if s.source == 'TavilySearch')}, "
                    f"Qwen: {sum(1 for s in all_sources if s.source == 'QwenWebSearch')}, "
                    f"Tashan: {tashan_count})")
        return all_sources

    def format_search_context(self, sources: List[SearchSource]) -> str:
        """
        将搜索结果格式化为可注入 LLM prompt 的上下文文本
        每条结果标注来源引擎

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
_unified_service: Optional[UnifiedSearchService] = None


def get_unified_search_service() -> UnifiedSearchService:
    """获取统一搜索服务全局单例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedSearchService()
    return _unified_service
