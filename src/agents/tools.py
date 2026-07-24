"""
云观星传 - Agent 工具集
定义 OpenAI Function Calling 格式的工具及其执行逻辑。
每个工具都有超时处理（5秒）、错误兜底和日志记录。

工具列表：
- query_knowledge_graph: 查询知识图谱
- search_rag_knowledge: RAG 知识库检索
- search_wikipedia: Wikipedia 百科搜索
- search_news: 国际媒体实时报道搜索
- verify_claim_external: 外部独立校验
"""
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 工具定义（OpenAI Function Calling 格式）
# ------------------------------------------------------------------

AGENT_TOOLS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_graph",
            "description": "查询知识图谱中与给定实体相关的实体和关系。用于验证事实准确性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "实体名称，如'嫦娥六号'"},
                    "depth": {"type": "integer", "description": "搜索深度，1-3", "default": 2},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_rag_knowledge",
            "description": "在科学知识库中检索与查询相关的文档片段。用于核实科学事实。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询"},
                    "top_k": {"type": "integer", "description": "返回结果数", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "搜索 Wikipedia 获取实体或议题的权威百科信息。用于补充背景知识。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "lang": {"type": "string", "description": "语言代码: zh/en/fr/pt", "default": "zh"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "搜索国际媒体关于科技议题的实时报道（同时调用 Tavily AI Search 和百炼 WebSearch 双引擎）。用于获取最新舆论动态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "country": {"type": "string", "description": "目标国家", "default": ""},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索（Tavily + 百炼 WebSearch 双引擎并行）。获取科技议题的最新事实、国际报道和舆论动态。新闻时效性强，优先使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "每个引擎返回的最大结果数", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_claim_external",
            "description": "通过 Wikidata 三元组和 Wikipedia 检索独立校验一条事实断言。返回验证状态和置信度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "待验证的断言"},
                    "entities": {"type": "array", "items": {"type": "string"}, "description": "断言涉及的核心实体"},
                },
                "required": ["claim"],
            },
        },
    },
]

# 工具名 → 定义的映射
TOOL_REGISTRY: Dict[str, Dict] = {t["function"]["name"]: t for t in AGENT_TOOLS}


def get_tools_for_agent(tool_names: List[str]) -> List[Dict]:
    """
    根据工具名列表获取对应的工具定义

    Args:
        tool_names: 工具名列表

    Returns:
        OpenAI Function Calling 格式的工具定义列表
    """
    tools = []
    for name in tool_names:
        if name in TOOL_REGISTRY:
            tools.append(TOOL_REGISTRY[name])
        else:
            logger.warning(f"[Tools] 未知工具: {name}")
    return tools


# ------------------------------------------------------------------
# 工具执行器
# ------------------------------------------------------------------

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    执行指定工具并返回结果字符串

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        JSON 格式的结果字符串
    """
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    try:
        result = executor(**arguments)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[Tools] 执行 {tool_name} 失败: {e}")
        return json.dumps(
            {"error": f"工具执行失败: {str(e)}", "tool": tool_name},
            ensure_ascii=False,
        )


def _exec_query_knowledge_graph(entity_name: str, depth: int = 2) -> Dict:
    """查询知识图谱"""
    from src.knowledge.kg_builder import get_knowledge_graph

    kg = get_knowledge_graph()
    related = kg.find_related_entities(entity_name, depth=min(depth, 3))

    if not related:
        return {"entity": entity_name, "found": False, "related": [], "message": "未找到相关实体"}

    return {
        "entity": entity_name,
        "found": True,
        "related": related[:10],  # 限制返回数量
        "count": len(related),
    }


def _exec_search_rag_knowledge(query: str, top_k: int = 5) -> Dict:
    """RAG 知识库检索"""
    from src.knowledge.vector_store import get_vector_store

    vector_store = get_vector_store()
    if vector_store.index is None or vector_store.index.ntotal == 0:
        return {"query": query, "results": [], "message": "向量库为空"}

    results = vector_store.search(query, top_k=min(top_k, 10))
    return {
        "query": query,
        "results": [{"text": r["text"][:300], "score": r.get("score", 0)} for r in results],
        "count": len(results),
    }


def _exec_search_wikipedia(query: str, lang: str = "zh") -> Dict:
    """搜索 Wikipedia"""
    import httpx

    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            # 搜索
            resp = client.get(api_url, params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 3,
                "format": "json",
            })
            resp.raise_for_status()
            data = resp.json()
            titles = [r["title"] for r in data.get("query", {}).get("search", [])]

            if not titles:
                return {"query": query, "results": [], "message": "未找到相关页面"}

            # 获取第一个结果的摘要
            resp2 = client.get(api_url, params={
                "action": "query",
                "titles": titles[0],
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "format": "json",
            })
            resp2.raise_for_status()
            pages = resp2.json().get("query", {}).get("pages", {})
            extract = ""
            for page in pages.values():
                extract = page.get("extract", "")[:800]
                break

            return {
                "query": query,
                "title": titles[0],
                "extract": extract,
                "other_titles": titles[1:],
            }
    except Exception as e:
        return {"query": query, "results": [], "error": f"Wikipedia 查询失败: {str(e)}"}


def _exec_search_news(query: str, country: str = "") -> Dict:
    """搜索新闻（使用 Tavily + 百炼 WebSearch 双引擎）"""
    try:
        from src.search.tavily_search import get_search_service
        from src.search.qwen_websearch import QwenWebSearchService

        full_query = f"{query} {country}".strip() if country else query
        results = []

        # Tavily 搜索
        try:
            tavily = get_search_service()
            tavily_results = tavily.search(full_query, max_results=5)
            for r in tavily_results:
                results.append({"title": r.title, "content": r.content[:200], "url": r.url, "source": "TavilySearch"})
        except Exception as e:
            logger.warning(f"[Tools] Tavily 搜索失败: {e}")

        # 百炼 WebSearch
        try:
            qwen = QwenWebSearchService()
            qwen_pages = qwen.search(full_query, count=5)
            for p in qwen_pages:
                results.append({
                    "title": p.get("title", ""),
                    "content": (p.get("snippet", "") or p.get("description", "") or p.get("content", ""))[:200],
                    "url": p.get("url", "") or p.get("link", ""),
                    "source": "QwenWebSearch",
                })
        except Exception as e:
            logger.warning(f"[Tools] 百炼 WebSearch 失败: {e}")

        return {
            "query": full_query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        return {"query": query, "results": [], "error": f"新闻搜索失败: {str(e)}"}


def _exec_verify_claim_external(claim: str, entities: Optional[List[str]] = None) -> Dict:
    """外部独立校验"""
    from src.verification.external_validator import get_external_validator

    validator = get_external_validator()
    result = validator.validate(claim, entities=entities or [])
    return result


def _exec_search_web(query: str, max_results: int = 5) -> Dict:
    """联网搜索（Tavily + 百炼 WebSearch 双引擎并行）"""
    from concurrent.futures import ThreadPoolExecutor

    results = []

    def _tavily():
        try:
            from src.search.tavily_search import get_search_service
            tavily = get_search_service()
            return tavily.search(query, max_results=max_results)
        except Exception as e:
            logger.warning(f"[Tools] search_web Tavily 失败: {e}")
            return []

    def _qwen():
        try:
            from src.search.qwen_websearch import QwenWebSearchService
            qwen = QwenWebSearchService()
            return qwen.search(query, count=max_results)
        except Exception as e:
            logger.warning(f"[Tools] search_web 百炼 失败: {e}")
            return []

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_tavily = executor.submit(_tavily)
        f_qwen = executor.submit(_qwen)
        tavily_sources = f_tavily.result()
        qwen_pages = f_qwen.result()

    for r in tavily_sources:
        results.append({"title": r.title, "content": r.content[:250], "url": r.url, "source": "TavilySearch"})
    for p in qwen_pages:
        results.append({
            "title": p.get("title", ""),
            "content": (p.get("snippet", "") or p.get("description", "") or p.get("content", ""))[:250],
            "url": p.get("url", "") or p.get("link", ""),
            "source": "QwenWebSearch",
        })

    return {"query": query, "results": results, "count": len(results),
            "engines": {"tavily": len(tavily_sources), "qwen": len(qwen_pages)}}


# 工具名 → 执行函数映射
TOOL_EXECUTORS: Dict[str, Callable] = {
    "query_knowledge_graph": _exec_query_knowledge_graph,
    "search_rag_knowledge": _exec_search_rag_knowledge,
    "search_wikipedia": _exec_search_wikipedia,
    "search_news": _exec_search_news,
    "search_web": _exec_search_web,
    "verify_claim_external": _exec_verify_claim_external,
}
