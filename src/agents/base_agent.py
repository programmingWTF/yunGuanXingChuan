"""
云观星传 - Agent 基类
提供：LLM 调用、JSON 解析、失败重试（最多3次）、错误处理、Tool Use 循环
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Type

from pydantic import BaseModel, ValidationError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import PROMPTS_DIR, QWEN_MODEL
from src.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


def sanitize_for_schema(data: Any, model: Type[BaseModel], max_list_len: int = 12) -> Dict[str, Any]:
    """按目标 Pydantic 模型递归清洗 LLM 输出（容错 salvage）：

    - List[BaseModel] 字段：丢弃非 dict 项（LLM 重复循环的空行/字符串），截断到 max_list_len
    - List[dict/str] 字段：同样丢弃非预期类型项并截断
    - 必填标量字段缺失/类型错误：保持原样交回校验（真缺失就让它失败）
    - 未知字段：丢弃
    """
    from typing import get_origin, get_args
    if not isinstance(data, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if name not in data:
            continue
        v = data[name]
        ann = field.annotation
        origin = get_origin(ann)
        args = get_args(ann)
        # 只对 List[...] 字段做容错（线上故障的爆炸点），其余字段原样交回校验
        if origin is list and isinstance(v, list):
            item_t = args[0] if args else None
            if isinstance(item_t, type) and issubclass(item_t, BaseModel):
                v = [sanitize_for_schema(i, item_t, max_list_len) for i in v if isinstance(i, dict)]
            elif item_t is str:
                v = [i for i in v if isinstance(i, str)]
            elif item_t is dict:
                v = [i for i in v if isinstance(i, dict)]
            v = v[:max_list_len]
        cleaned[name] = v
    return cleaned


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
    agent_tools: List[str] = []  # 绑定的工具名列表（用于 Function Calling）

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ):
        """
        Args:
            llm_client: LLM 客户端实例
            model: 使用的模型
            max_retries: 最大重试次数
            temperature: 温度参数
            max_tokens: 输出 token 上限（None 用 LLM 客户端默认）
        """
        self.llm_client = llm_client or get_llm_client()
        # 多租户：优先用用户配置（llm_client.model）的模型，其次显式 model，最后全局默认
        self.model = model or (getattr(self.llm_client, "model", None) or QWEN_MODEL)
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_tokens = max_tokens
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

        # 投票任务无需联网搜索（基于已有辩论内容判断，避免每轮 5 个 Agent 各触发一次搜索）
        use_search = self.enable_search and input_data.get("task_type") != "vote"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # 调用 LLM
                raw_output = self.llm_client.chat_json(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    model=self.model,
                    temperature=self.temperature,
                    enable_search=use_search,
                    max_tokens=self.max_tokens,
                )

                # 解析输出
                parsed = self._parse_output(raw_output)

                # 辩论/投票类 task_type 跳过固定 Schema 校验（输出格式由 prompt 控制）
                skip_schema = input_data.get("task_type", "") in (
                    "opening_report", "debate_speech", "vote"
                )

                # 校验 Schema
                if self.output_schema and not skip_schema:
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
        用 Pydantic Schema 校验输出；失败时先做一次容错清洗再重试。

        背景（2026-08-31 线上故障）：LLM 偶发退化输出（重复循环生成几百条
        "id: /statement:/hypothesis_type:" 空字段行），直接 model_validate
        抛出数百条 ValidationError 导致整个阶段失败。清洗策略可把这类输出
        salvage 成合法结构（丢弃非 dict 项 + 截断超长列表）。
        """
        if self.output_schema is None:
            return parsed
        try:
            validated = self.output_schema.model_validate(parsed)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning(
                f"[{self.agent_name}] 输出校验失败（{len(e.errors())} 条错误），尝试容错清洗后重试"
            )
            cleaned = sanitize_for_schema(parsed, self.output_schema)
            validated = self.output_schema.model_validate(cleaned)
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

    # ------------------------------------------------------------------
    # Tool Use 循环（P0-C）
    # ------------------------------------------------------------------

    def run_with_tools(self, input_data: Dict[str, Any], max_tool_rounds: int = 5,
                       context_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        带工具调用的 Agent 执行循环

        流程：
        1. 发送 user prompt + tools 定义 → LLM
        2. 如果 LLM 返回 tool_calls → 执行工具 → 把结果加入 messages → 再次调 LLM
        3. 重复直到 LLM 返回 final answer（无 tool_calls）或达到 max_tool_rounds
        4. 最终输出解析为 Schema

        Args:
            input_data: 输入数据字典
            max_tool_rounds: 最大工具调用轮次
            context_messages: 可选的历史辩论上下文（认知议会模式）

        Returns:
            输出数据字典（符合 output_schema）
        """
        from src.agents.tools import get_tools_for_agent, execute_tool

        # 如果没有绑定工具，回退到普通 run()
        if not self.agent_tools:
            return self.run(input_data)

        logger.info(f"[{self.agent_name}] 开始 Tool Use 执行 (tools={self.agent_tools})...")

        # 获取工具定义
        tools = get_tools_for_agent(self.agent_tools)
        if not tools:
            logger.warning(f"[{self.agent_name}] 无有效工具，回退到 run()")
            return self.run(input_data)

        # 构建初始 messages
        user_prompt = self._build_user_prompt(input_data)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
        ]
        # 注入历史辩论上下文（认知议会模式）
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_prompt})

        # Tool Use 循环
        for round_num in range(max_tool_rounds):
            try:
                response = self.llm_client.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=self.temperature,
                )

                choice = response.choices[0]
                message = choice.message

                # 检查是否有 tool_calls
                if message.tool_calls:
                    # 将 assistant 消息加入历史
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in message.tool_calls
                        ],
                    })

                    # 执行每个工具调用
                    for tc in message.tool_calls:
                        tool_name = tc.function.name
                        try:
                            arguments = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            # 尝试修复工具参数 JSON
                            try:
                                repaired_args = self.llm_client._repair_json_quotes(tc.function.arguments)
                                arguments = json.loads(repaired_args) if repaired_args else {}
                            except Exception:
                                arguments = {}

                        logger.info(
                            f"[{self.agent_name}] 调用工具: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:100]})"
                        )
                        tool_result = execute_tool(tool_name, arguments)

                        # 将工具结果加入 messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result,
                        })

                    logger.info(
                        f"[{self.agent_name}] Tool Use 第 {round_num + 1} 轮完成，"
                        f"调用了 {len(message.tool_calls)} 个工具"
                    )
                else:
                    # 无 tool_calls → 最终答案
                    final_content = message.content or ""
                    logger.info(f"[{self.agent_name}] Tool Use 完成 (第 {round_num + 1} 轮得到最终答案)")
                    return self._parse_tool_use_output(final_content)

            except Exception as e:
                logger.error(f"[{self.agent_name}] Tool Use 异常 (round {round_num + 1}): {e}")
                # 返回空字典让上层兜底（不递归调 run，避免二次 LLM 调用链失败）
                return {}

        # 达到最大轮次，强制要求输出
        logger.warning(f"[{self.agent_name}] 达到最大工具轮次 ({max_tool_rounds})，强制输出")
        messages.append({
            "role": "user",
            "content": "请不要再调用工具，直接输出最终的 JSON 结果。",
        })
        try:
            response = self.llm_client.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            final_content = response.choices[0].message.content or ""
            return self._parse_tool_use_output(final_content)
        except Exception as e:
            logger.error(f"[{self.agent_name}] 强制输出失败: {e}")
            # 兜底：返回含所有必填字段的默认值
            return self._get_fallback_result()

    def _get_fallback_result(self) -> Dict[str, Any]:
        """当所有解析都失败时，根据 output_schema 生成含所有必填字段的兜底结果"""
        fallback_map = {
            "EvaluationResult": {
                "scores": {"factual_accuracy": 70, "strategic_actionability": 70,
                           "audience_fit": 70, "cultural_sensitivity": 70, "narrative_fluency": 70},
                "weighted_total": 70, "passed": False, "feedback": [],
                "experience_log": "解析失败，使用默认评分", "audience_simulation": [],
            },
            "StrategySet": {
                "topic": "", "strategies": [], "audience_coverage": [], "cultural_notes": [],
            },
        }
        schema_name = self.output_schema.__name__ if self.output_schema else ""
        if schema_name in fallback_map:
            return fallback_map[schema_name]
        return {}

    def _parse_tool_use_output(self, content: str) -> Dict[str, Any]:
        """解析 Tool Use 最终输出"""
        # 尝试提取 JSON
        try:
            # 去除可能的 markdown 代码块标记
            text = content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)
    
            parsed = json.loads(text)
    
            # Schema 校验
            if self.output_schema:
                validated = self.output_schema.model_validate(parsed)
                return validated.model_dump()
            return parsed
    
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"[{self.agent_name}] Tool Use 输出解析失败: {e}")
    
            # 尝试 1: 修复未转义的内部引号
            try:
                repaired = self.llm_client._repair_json_quotes(content.strip())
                if repaired:
                    parsed = json.loads(repaired)
                    if self.output_schema:
                        validated = self.output_schema.model_validate(parsed)
                        return validated.model_dump()
                    return parsed
            except Exception:
                pass
    
            # 尝试 2: 用 _fix_truncated_json 修复截断的 JSON
            try:
                fixed = self.llm_client._fix_truncated_json(content)
                if fixed:
                    parsed = json.loads(fixed)
                    if self.output_schema:
                        validated = self.output_schema.model_validate(parsed)
                        return validated.model_dump()
                    return parsed
            except Exception:
                pass
    
            # 尝试 3: 组合修复（先修引号再补截断）
            try:
                repaired = self.llm_client._repair_json_quotes(content.strip())
                if repaired:
                    fixed = self.llm_client._fix_truncated_json(repaired)
                    if fixed:
                        parsed = json.loads(fixed)
                        if self.output_schema:
                            validated = self.output_schema.model_validate(parsed)
                            return validated.model_dump()
                        return parsed
            except Exception:
                pass
    
            # 尝试 4: 用正则提取 JSON 部分再解析
            import re
            try:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    extracted = json_match.group()
                    repaired = self.llm_client._repair_json_quotes(extracted)
                    parsed = json.loads(repaired or extracted)
                    if self.output_schema:
                        validated = self.output_schema.model_validate(parsed)
                        return validated.model_dump()
                    return parsed
            except Exception:
                pass

            # 尝试 5: 修复缺少逗号分隔符的 JSON（如 "key": "value" "key2"）
            import re as _re
            try:
                text = content.strip()
                json_match = _re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    raw = json_match.group()
                    # 在 }" 或 ]" 或 "\n" 之间缺少逗号的位置插入逗号
                    fixed = _re.sub(r'(["\]\}])\s*\n\s*"', r'\1,\n"', raw)
                    fixed = _re.sub(r'(["\]\}])\s+("[^"]+"\s*:)', r'\1, \2', fixed)
                    parsed = json.loads(fixed)
                    if self.output_schema:
                        validated = self.output_schema.model_validate(parsed)
                        return validated.model_dump()
                    return parsed
            except Exception:
                pass
    
            # 最终回退：返回兜底结果，避免无限递归 LLM 调用
            logger.warning(f"[{self.agent_name}] 所有解析尝试失败，返回兜底结果")
            return self._get_fallback_result()
