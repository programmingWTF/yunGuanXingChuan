"""
云观星传 - LLM 客户端封装
基于阿里云百炼平台 Qwen API（OpenAI 兼容接口）
支持：JSON 结构化输出、自动重试、Embedding 向量化
"""
import json
import time
import logging
from typing import Optional, List, Dict, Any

from openai import OpenAI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL,
    QWEN_MODEL_FAST, QWEN_EMBEDDING_MODEL,
    QWEN_EMBEDDING_BASE_URL, QWEN_EMBEDDING_API_KEY
)

logger = logging.getLogger(__name__)


class LLMClient:
    """Qwen LLM 客户端，封装 OpenAI 兼容接口"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.api_key = api_key or QWEN_API_KEY
        self.base_url = base_url or QWEN_BASE_URL
        self.model = model or QWEN_MODEL
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        # Embedding 用单独的客户端（独立端点和 Key）
        self._embedding_client = OpenAI(
            api_key=QWEN_EMBEDDING_API_KEY,
            base_url=QWEN_EMBEDDING_BASE_URL,
        )

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        json_mode: bool = True,
        enable_search: bool = False,
        max_tokens: int = 16384,
    ) -> str:
        """
        发送聊天请求，返回文本响应

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            model: 使用的模型（默认用主模型）
            temperature: 温度参数
            json_mode: 是否要求 JSON 输出
            enable_search: 是否启用联网搜索（百炼平台原生支持，同一API Key）

        Returns:
            模型响应文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # 启用联网搜索
        # qwen3.8-max-preview 仅支持 Responses API 联网搜索
        # 其他模型用 Chat Completions API 的 enable_search
        if enable_search:
            return self._chat_with_search(system_prompt, user_prompt, model, json_mode)

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content:
                    return content
                raise ValueError("模型返回空内容")
            except Exception as e:
                logger.warning(
                    f"LLM 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

        return ""

    def _chat_with_search(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """
        使用 Responses API 进行联网搜索调用
        qwen3.8-max-preview 等模型仅支持此方式联网
        如果 SDK 不支持 Responses API，回退到 Chat Completions + enable_search
        """
        use_model = model or self.model

        # 构建 input：system + user 合并为 input 字符串
        input_text = f"[System]\n{system_prompt}\n\n[User]\n{user_prompt}"
        if json_mode:
            input_text += "\n\n[重要] 请严格以 JSON 格式输出，不要包含其他内容。"

        # 尝试 Responses API
        if hasattr(self.client, 'responses'):
            for attempt in range(self.max_retries):
                try:
                    response = self.client.responses.create(
                        model=use_model,
                        input=input_text,
                        tools=[{"type": "web_search"}],
                        max_output_tokens=16384,
                    )
                    # Responses API 返回格式：response.output_text
                    content = getattr(response, 'output_text', None)
                    if not content:
                        # 兼容：尝试从 output 列表提取文本
                        parts = []
                        for item in getattr(response, 'output', []):
                            if hasattr(item, 'content'):
                                for c in item.content:
                                    if hasattr(c, 'text'):
                                        parts.append(c.text)
                            elif hasattr(item, 'text'):
                                parts.append(item.text)
                        content = '\n'.join(parts)
                    if content:
                        return content
                    raise ValueError("Responses API 返回空内容")
                except Exception as e:
                    logger.warning(
                        f"LLM 联网搜索调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
        else:
            # 回退：Chat Completions API + enable_search（适用于 qwen-plus 等模型）
            logger.info("SDK 不支持 Responses API，回退到 Chat Completions + enable_search")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            kwargs: Dict[str, Any] = {
                "model": use_model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 16384,
                "extra_body": {"enable_search": True},
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            for attempt in range(self.max_retries):
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content
                    if content:
                        return content
                    raise ValueError("模型返回空内容")
                except Exception as e:
                    logger.warning(
                        f"LLM 联网搜索回退调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise

        return ""

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        enable_search: bool = False,
    ) -> dict:
        """
        发送聊天请求，返回解析后的 JSON 字典

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            model: 使用的模型
            temperature: 温度参数
            enable_search: 是否启用联网搜索

        Returns:
            解析后的 JSON 字典
        """
        content = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            json_mode=True,
            enable_search=enable_search,
        )

        # 尝试解析 JSON
        try:
            # 处理可能的 markdown 代码块包裹
            cleaned = content.strip()
            # Pre-process Chinese/smart quotes
            for q in ["\u201c", "\u201d", "\u2018", "\u2019"]:
                cleaned = cleaned.replace(q, "'")
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}，尝试修复...")
            # 尝试修复未转义的引号
            import re
            repaired = self._repair_json_quotes(cleaned)
            if repaired:
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    pass
            # 尝试提取 JSON 部分
            # Last resort: global quote replacement
            try:
                return json.loads(cleaned.replace('"', "'"))
            except json.JSONDecodeError:
                pass
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    # 对提取的部分也尝试修复
                    extracted = json_match.group()
                    repaired2 = self._repair_json_quotes(extracted)
                    if repaired2:
                        try:
                            return json.loads(repaired2)
                        except json.JSONDecodeError:
                            pass
            # 最后尝试：修复截断的 JSON（补全未闭合的括号）
            truncated_fix = self._fix_truncated_json(cleaned)
            if truncated_fix:
                try:
                    return json.loads(truncated_fix)
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"无法解析 LLM 输出为 JSON: {content[:200]}")

    @staticmethod
    def _fix_truncated_json(text: str) -> Optional[str]:
        """
        修复被截断的 JSON：补全未闭合的括号和引号
        当 LLM 输出超过 max_tokens 被截断时，尝试 salvage 已有部分
        """
        if not text or not text.strip().startswith('{'):
            return None

        # 统计未闭合的括号
        stack = []
        in_string = False
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]
            if in_string:
                if ch == '\\':
                    i += 2
                    continue
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch in '{[':
                    stack.append(ch)
                elif ch == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                elif ch == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
            i += 1

        if not stack and not in_string:
            return None  # JSON 完整，不需要修复

        # 截断修复：移除末尾不完整的键值对，然后补全括号
        result = text.rstrip()

        # 如果在字符串内部截断，先关闭字符串
        if in_string:
            result += '"'

        # 移除末尾不完整的部分（如 "key": "val 或 "key":）
        # 找到最后一个完整的值结束位置
        import re
        # 尝试截断到最后一个完整的 , 或 { 或 [ 之后
        last_good = max(
            result.rfind(','),
            result.rfind('{'),
            result.rfind('['),
        )
        if last_good > 0:
            # 如果最后是逗号，去掉它
            candidate = result[:last_good]
            if candidate.rstrip().endswith(','):
                candidate = candidate.rstrip()[:-1]
            result = candidate

        # 重新计算需要补全的括号
        stack2 = []
        in_str2 = False
        for ch in result:
            if in_str2:
                if ch == '\\':
                    continue
                elif ch == '"':
                    in_str2 = False
            else:
                if ch == '"':
                    in_str2 = True
                elif ch in '{[':
                    stack2.append(ch)
                elif ch == '}':
                    if stack2 and stack2[-1] == '{':
                        stack2.pop()
                elif ch == ']':
                    if stack2 and stack2[-1] == '[':
                        stack2.pop()

        # 补全未闭合的括号
        for bracket in reversed(stack2):
            result += '}' if bracket == '{' else ']'

        return result

    @staticmethod
    def _repair_json_quotes(text: str) -> Optional[str]:
        """
        修复 JSON 中未转义的内部引号
        例如: "曾用名"郑和号"）" -> "曾用名\"郑和号\"）"
        """
        result = []
        in_string = False
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            if not in_string:
                result.append(ch)
                if ch == '"':
                    in_string = True
                i += 1
            else:
                # 在字符串内部
                if ch == '\\':
                    # 转义字符，跳过下一个
                    result.append(ch)
                    if i + 1 < n:
                        result.append(text[i + 1])
                        i += 2
                    else:
                        i += 1
                elif ch == '"':
                    # 判断这个引号是字符串结束符还是内部引号
                    # 向后看：如果后面是 JSON 结构字符，则是结束符
                    rest = text[i + 1:].lstrip()
                    if not rest or rest[0] in ':,]}\n':
                        # 是字符串结束符
                        result.append(ch)
                        in_string = False
                        i += 1
                    else:
                        # 是内部引号，转义它
                        result.append('\\"')
                        i += 1
                else:
                    result.append(ch)
                    i += 1

        return ''.join(result)

    def chat_multi_turn(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        json_mode: bool = True,
    ) -> str:
        """
        多轮对话

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            model: 使用的模型
            temperature: 温度参数
            json_mode: 是否要求 JSON 输出

        Returns:
            模型响应文本
        """
        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content:
                    return content
                raise ValueError("模型返回空内容")
            except Exception as e:
                logger.warning(
                    f"LLM 多轮调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

        return ""

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        for attempt in range(self.max_retries):
            try:
                response = self._embedding_client.embeddings.create(
                    model=QWEN_EMBEDDING_MODEL,
                    input=text,
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(
                    f"Embedding 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

        return []

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本向量

        Args:
            texts: 文本列表

        Returns:
            向量列表的列表
        """
        for attempt in range(self.max_retries):
            try:
                response = self._embedding_client.embeddings.create(
                    model=QWEN_EMBEDDING_MODEL,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                logger.warning(
                    f"批量 Embedding 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

        return []


# 全局单例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
