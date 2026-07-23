"""
云观星传 - 阿里云百炼 WebSearch MCP 联网搜索服务
通过 Streamable HTTP 协议调用百炼 WebSearch MCP，获取联网搜索结果
"""
import json
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_MCP_URL

logger = logging.getLogger(__name__)


class QwenWebSearchService:
    """阿里云百炼 WebSearch MCP 搜索封装"""

    def __init__(self, api_key: Optional[str] = None, mcp_url: Optional[str] = None):
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.mcp_url = mcp_url or DASHSCOPE_MCP_URL
        self._http_client = None
        self._session_id: Optional[str] = None

    def _get_http_client(self):
        """延迟初始化 httpx 客户端"""
        if self._http_client is None:
            if not self.api_key:
                logger.warning("DASHSCOPE_API_KEY 未配置，百炼联网搜索不可用")
                return None
            try:
                import httpx
                self._http_client = httpx.Client(timeout=60.0)
                logger.info("百炼 WebSearch MCP httpx 客户端初始化成功")
            except ImportError:
                logger.error("httpx 未安装，请执行: pip install httpx")
                return None
        return self._http_client

    def _make_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _parse_sse_response(self, text: str) -> Optional[Dict]:
        """解析 SSE 格式的响应，提取 JSON-RPC result"""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    try:
                        parsed = json.loads(data_str)
                        if "result" in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        continue
        return None

    def _jsonrpc_call(self, method: str, params: Optional[Dict] = None, req_id: int = 1) -> Optional[Dict]:
        """发送 JSON-RPC 2.0 请求到 MCP 端点"""
        client = self._get_http_client()
        if not client:
            return None

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
        }
        if params is not None:
            payload["params"] = params

        try:
            response = client.post(
                self.mcp_url,
                json=payload,
                headers=self._make_headers(),
            )
            response.raise_for_status()

            # 保存 session ID
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                self._session_id = session_id

            content_type = response.headers.get("content-type", "")

            if "text/event-stream" in content_type:
                # SSE 格式响应
                parsed = self._parse_sse_response(response.text)
                return parsed
            else:
                # 普通 JSON 响应
                return response.json()

        except Exception as e:
            logger.error(f"百炼 MCP JSON-RPC 调用失败 ({method}): {e}")
            return None

    def _initialize(self) -> bool:
        """初始化 MCP 会话"""
        result = self._jsonrpc_call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "yunGuanXingChuan", "version": "1.0.0"},
        }, req_id=0)

        if result and "result" in result:
            logger.info("百炼 WebSearch MCP 会话初始化成功")
            # 发送 initialized 通知
            try:
                client = self._get_http_client()
                if client:
                    client.post(
                        self.mcp_url,
                        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                        headers=self._make_headers(),
                    )
            except Exception:
                pass
            return True
        else:
            logger.warning(f"百炼 WebSearch MCP 初始化失败: {result}")
            return False

    def search(self, query: str, count: int = 10) -> List[Dict]:
        """
        调用百炼 WebSearch MCP 执行联网搜索

        Args:
            query: 搜索关键词
            count: 返回结果数量

        Returns:
            搜索结果列表，每条包含 title, url, snippet 等字段
        """
        client = self._get_http_client()
        if not client:
            return []

        # 确保会话已初始化
        if not self._session_id:
            if not self._initialize():
                return []

        # 调用 bailian_web_search 工具
        result = self._jsonrpc_call("tools/call", {
            "name": "bailian_web_search",
            "arguments": {"query": query, "count": count},
        }, req_id=1)

        if not result:
            return []

        # 解析结果
        try:
            tool_result = result.get("result", {})
            content_blocks = tool_result.get("content", [])

            # 从 content blocks 中提取文本并解析 JSON
            for block in content_blocks:
                if block.get("type") == "text":
                    text_data = block.get("text", "")
                    try:
                        data = json.loads(text_data)
                        pages = data.get("pages", [])
                        if pages:
                            logger.info(f"百炼 WebSearch '{query[:30]}...' 返回 {len(pages)} 条结果")
                            return pages
                    except json.JSONDecodeError:
                        # 如果不是 JSON，尝试作为纯文本处理
                        if text_data.strip():
                            logger.info(f"百炼 WebSearch 返回非结构化文本结果")
                            return [{"title": "搜索结果", "snippet": text_data[:500], "url": ""}]

            logger.warning(f"百炼 WebSearch 未返回有效内容: {str(result)[:200]}")
            return []

        except Exception as e:
            logger.error(f"百炼 WebSearch 结果解析失败: {e}")
            return []

    def search_for_topic(self, topic: str) -> List[Dict]:
        """
        为科技议题执行多角度搜索

        Args:
            topic: 科技议题名称

        Returns:
            合并去重后的搜索结果列表
        """
        queries = [
            f"{topic} 科学事实 技术参数 最新进展",
            f"{topic} international media coverage report",
            f"{topic} 国际舆论 报道分析",
        ]

        all_results: Dict[str, Dict] = {}  # 用 URL 去重

        for query in queries:
            pages = self.search(query, count=5)
            for page in pages:
                url = page.get("url", "") or page.get("link", "")
                key = url if url else page.get("title", "") + str(len(all_results))
                if key and key not in all_results:
                    all_results[key] = page

        results = list(all_results.values())
        logger.info(f"百炼 WebSearch 议题 '{topic}' 共获取 {len(results)} 条去重结果")
        return results
