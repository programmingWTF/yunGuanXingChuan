"""
云观星传 - Agent 基类
提供：LLM 调用、JSON 解析、失败重试（最多3次）、错误处理
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Any, Type

from pydantic import BaseModel, ValidationError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import PROMPTS_DIR, QWEN_MODEL
from src.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 继承此类，实现：
    - system prompt 加载
    - LLM 调用（JSON 模式）
    - 输出解析为 Pydantic Schema
    - 失败重试（最多 3 次）
    - 错误处理与日志
    """

    # 子类需要覆盖的属性
    agent_name: str = "base_agent"
    prompt_file: str = ""  # config/prompts/ 下的文件名
    output_schema: Optional[Type[BaseModel]] = None  # 输出的 Pydantic 模型
    enable_search: bool = False  # 是否启用联网搜索（百炼平台原生支持）

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.3,
    ):
        """
        Args:
            llm_client: LLM 客户端实例
            model: 使用的模型
            max_retries: 最大重试次数
            temperature: 温度参数
        """
        self.llm_client = llm_client or get_llm_client()
        self.model = model or QWEN_MODEL
        self.max_retries = max_retries
        self.temperature = temperature
        self._system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        """加载并缓存 system prompt"""
        if self._system_prompt is None:
            self._system_prompt = self._load_prompt()
        return self._system_prompt

    def _load_prompt(self) -> str:
        """从 config/prompts/ 加载 system prompt"""
        if not self.prompt_file:
            return self._get_default_prompt()

        prompt_path = PROMPTS_DIR / self.prompt_file
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        else:
            logger.warning(f"Prompt 文件不存在: {prompt_path}，使用默认 prompt")
            return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """默认 system prompt（子类应覆盖）"""
        return "你是一个专业的 AI 助手。请严格按照 JSON 格式输出结果。"

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 Agent 任务（带重试）

        Args:
            input_data: 输入数据字典

        Returns:
            输出数据字典（符合 output_schema）
        """
        logger.info(f"[{self.agent_name}] 开始执行...")

        # 构建 user prompt
        user_prompt = self._build_user_prompt(input_data)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # 调用 LLM
                raw_output = self.llm_client.chat_json(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    enable_search=self.enable_search,
                )

                # 解析输出
                parsed = self._parse_output(raw_output)

                # 校验 Schema
                if self.output_schema:
                    validated = self._validate_output(parsed)
                    logger.info(f"[{self.agent_name}] 执行成功 (尝试 {attempt + 1})")
                    return validated

                logger.info(f"[{self.agent_name}] 执行成功 (尝试 {attempt + 1})")
                return parsed

            except ValidationError as e:
                last_error = e
                logger.warning(
                    f"[{self.agent_name}] Schema 校验失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                # 将错误信息加入下次 prompt，帮助模型修正
                user_prompt = self._build_retry_prompt(user_prompt, raw_output, str(e))

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    f"[{self.agent_name}] JSON 解析失败 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                user_prompt = self._build_retry_prompt(
                    user_prompt, "", f"JSON 解析错误: {e}"
                )

            except Exception as e:
                last_error = e
                logger.error(
                    f"[{self.agent_name}] 执行异常 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 * (attempt + 1))

        # 所有重试都失败
        logger.error(f"[{self.agent_name}] 所有重试均失败: {last_error}")
        raise RuntimeError(
            f"[{self.agent_name}] 执行失败（已重试 {self.max_retries} 次）: {last_error}"
        )

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """
        构建 user prompt（子类应覆盖）

        Args:
            input_data: 输入数据

        Returns:
            格式化的 user prompt
        """
        return json.dumps(input_data, ensure_ascii=False, indent=2)

    def _parse_output(self, raw_output: Dict) -> Dict:
        """
        解析 LLM 输出（子类可覆盖以做额外处理）

        Args:
            raw_output: LLM 返回的 JSON 字典

        Returns:
            处理后的字典
        """
        return raw_output

    def _validate_output(self, parsed: Dict) -> Dict:
        """
        用 Pydantic Schema 校验输出

        Args:
            parsed: 解析后的字典

        Returns:
            校验通过的字典
        """
        if self.output_schema is None:
            return parsed

        # 尝试用 Pydantic 模型校验
        validated = self.output_schema.model_validate(parsed)
        return validated.model_dump()

    def _build_retry_prompt(
        self, original_prompt: str, failed_output: str, error_msg: str
    ) -> str:
        """
        构建重试 prompt，包含错误信息帮助模型修正

        Args:
            original_prompt: 原始 prompt
            failed_output: 上次失败的输出
            error_msg: 错误信息

        Returns:
            带错误提示的新 prompt
        """
        retry_instruction = f"""

---
【重要】你上一次的输出有以下问题，请修正后重新输出：

错误信息：{error_msg}

"""
        if failed_output:
            retry_instruction += f"上次的输出（有错误）：\n{json.dumps(failed_output, ensure_ascii=False)[:500]}\n"

        if self.output_schema:
            retry_instruction += f"\n请严格按照以下 JSON Schema 输出：\n{self._get_schema_description()}\n"

        retry_instruction += f"\n---\n原始任务：\n{original_prompt[:4000]}\n\n请只输出 JSON，不要包含解释文字，确保字符串值内双引号用反斜杠转义。"

        return retry_instruction

    def _get_schema_description(self) -> str:
        """获取输出 Schema 的描述（用于提示模型）"""
        if self.output_schema is None:
            return ""

        schema = self.output_schema.model_json_schema()
        return json.dumps(schema, ensure_ascii=False, indent=2)

    @abstractmethod
    def get_agent_info(self) -> Dict:
        """获取 Agent 信息（子类实现）"""
        pass
