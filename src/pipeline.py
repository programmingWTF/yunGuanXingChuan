"""
云观星传 - Pipeline 编排器
串联所有 Agent 和校验层，实现完整的迭代闭环：
科学理解 -> 语境分析 -> 假设生成 -> 校验 -> 策略转译 -> 评测 -> (迭代)
"""
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import MAX_ITERATION_ROUNDS, PASS_THRESHOLD
from src.schemas import (
    PipelineResult, EvaluationScores, IterationFeedback,
    Hypothesis, Strategy, VerificationResult
)
from src.agents.science_agent import ScienceAgent
from src.agents.context_agent import ContextAgent
from src.agents.hypothesis_agent import HypothesisAgent
from src.agents.strategy_agent import StrategyAgent
from src.agents.evaluator_agent import EvaluatorAgent
from src.verification.cross_validator import CrossValidator
from src.verification.report_generator import ReportGenerator
from src.evaluation import EvaluationEngine
from src.search import get_search_service
from src.search.unified_search import get_unified_search_service

logger = logging.getLogger(__name__)


class Pipeline:
    """
    完整 Pipeline 编排器

    流程：
    1. 科学理解 Agent -> ScienceFacts
    2. 语境分析 Agent -> ContextAnalysis
    3. 假设生成 Agent -> Hypotheses
    4. 校验层（RAG + KG + 交叉验证）
    5. 策略转译 Agent -> Strategies
    6. 评测迭代 Agent -> 五维评分
    7. 迭代闭环（最多3轮）
    """

    def __init__(
        self,
        max_iterations: int = MAX_ITERATION_ROUNDS,
        pass_threshold: float = PASS_THRESHOLD,
        progress_callback=None,
    ):
        """
        Args:
            max_iterations: 最大迭代轮数
            pass_threshold: 通过阈值
            progress_callback: 进度回调函数 callback(step, status, message)
        """
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self.progress_callback = progress_callback

        # 初始化 Agent
        self.science_agent = ScienceAgent()
        self.context_agent = ContextAgent()
        self.hypothesis_agent = HypothesisAgent()
        self.strategy_agent = StrategyAgent()
        self.evaluator_agent = EvaluatorAgent()

        # 初始化校验层
        self.cross_validator = CrossValidator()
        self.report_generator = ReportGenerator()

        # 初始化评测引擎
        self.evaluation_engine = EvaluationEngine(
            pass_threshold=pass_threshold,
            max_rounds=max_iterations,
        )

        # 状态存储
        self.state: Dict = {}

    def _report(self, step: str, status: str, message: str = "", round_num: int = 0):
        """上报阶段进度"""
        if self.progress_callback:
            self.progress_callback(step, status, message, round_num)

    def _ensure_science_data(self, topic: str):
        """检查本地是否有该议题的科学数据，没有则自动生成"""
        import json
        from pathlib import Path
        from src.knowledge.data_loader import get_data_loader

        data_loader = get_data_loader()
        existing = data_loader.load_science_facts(topic)
        if existing:
            logger.info(f"  本地已有「{topic}」的科学数据，跳过生成")
            return

        logger.info(f"\n[数据准备] 本地无「{topic}」数据，自动生成中...")
        self._report("science", "running", f"正在为「{topic}」生成基础科学数据...")

        try:
            from src.llm_client import LLMClient
            client = LLMClient()
            result = client.chat_json(
                system_prompt="你是航天科技领域数据标注专家。为给定议题生成结构化科学事实。必须输出标准 JSON，字符串值内如有双引号请用反斜杠转义为 \"。",
                user_prompt=f"""请为以下科技议题生成结构化科学事实数据：

议题：{topic}

输出格式（严格 JSON）：
{{"topic": "{topic}", "key_facts": ["事实1（来源）", "...至少8条"], "entities": [{{"name": "实体名", "type": "mission/body/technology/organization/person/event", "attributes": {{}}, "description": "描述"}}], "relations": [{{"subject": "主体", "predicate": "关系", "object": "客体", "confidence": 0.9, "source": "来源"}}], "timeline": [{{"date": "YYYY-MM-DD", "event": "事件"}}], "data_sources": ["来源1"]}}""",
                temperature=0.2,
                enable_search=True,
            )

            # 保存到 data/science/
            science_dir = Path(__file__).parent.parent / "data" / "science"
            science_dir.mkdir(parents=True, exist_ok=True)
            safe_name = topic.replace(" ", "_").replace("/", "_")[:20]
            file_path = science_dir / f"{safe_name}_facts.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"  ✓ 已生成并保存: {file_path}")
        except Exception as e:
            logger.warning(f"  自动生成数据失败（不影响主流程）: {e}")

    def run(self, topic: str) -> PipelineResult:
        """
        运行完整 Pipeline

        Args:
            topic: 科技议题名称（如"嫦娥六号"）

        Returns:
            PipelineResult
        """
        logger.info(f"=" * 60)
        logger.info(f"开始运行 Pipeline: {topic}")
        logger.info(f"=" * 60)

        self.state = {"topic": topic, "start_time": datetime.now().isoformat()}

        try:
            # Step -1: 自动补齐科学数据（如果本地没有该议题的数据）
            self._ensure_science_data(topic)

            # Step 0: 联网搜索（Tavily + 百炼 WebSearch 双引擎）
            logger.info("\n[Step 0] 联网搜索（Tavily + 百炼 WebSearch）...")
            self._report("science", "running", "正在联网搜索相关信息...")
            search_service = get_unified_search_service()
            search_sources = search_service.search_for_topic(topic)
            search_context = search_service.format_search_context(search_sources)
            self.state["search_sources"] = [s.to_dict() for s in search_sources]
            logger.info(f"  获取 {len(search_sources)} 条搜索来源")
            if search_sources:
                for s in search_sources[:3]:
                    logger.info(f"    - [{s.source}] {s.title} ({s.url})")

            # Step 1: 科学理解
            logger.info("\n[Step 1] 科学理解 Agent...")
            self._report("science", "running", "正在提取科学事实...")
            science_facts = self._run_science_agent(topic, search_context)
            self.state["science_facts"] = science_facts
            self._report("science", "completed", f"提取 {len(science_facts.get('key_facts', []))} 条事实")
            logger.info(f"  提取 {len(science_facts.get('key_facts', []))} 条事实")

            # Step 2: 语境分析
            logger.info("\n[Step 2] 语境分析 Agent...")
            self._report("context", "running", "正在分析国际媒体框架...")
            context_analysis = self._run_context_agent(topic, science_facts, search_context)
            self.state["context_analysis"] = context_analysis
            self._report("context", "completed", f"分析 {len(context_analysis.get('country_analysis', []))} 个国家")
            logger.info(f"  分析 {len(context_analysis.get('country_analysis', []))} 个国家")

            # Step 3: 假设生成
            logger.info("\n[Step 3] 假设生成 Agent...")
            self._report("hypothesis", "running", "正在生成传播假设...")
            hypotheses = self._run_hypothesis_agent(topic, science_facts, context_analysis)
            self.state["hypotheses"] = hypotheses
            self._report("hypothesis", "completed", f"生成 {len(hypotheses.get('hypotheses', []))} 条假设")
            logger.info(f"  生成 {len(hypotheses.get('hypotheses', []))} 条假设")

            # Step 4: 校验层
            logger.info("\n[Step 4] 校验层（RAG + KG + 交叉验证）...")
            self._report("verification", "running", "RAG + KG 交叉验证中...")
            verification_results = self._run_verification(science_facts, hypotheses)
            self.state["verification_results"] = verification_results
            self._report("verification", "completed", f"校验 {len(verification_results)} 条断言")
            logger.info(f"  校验 {len(verification_results)} 条断言")

            # Step 5-7: 策略生成 + 评测 + 迭代闭环
            strategies = []
            evaluation_scores = None
            iteration_feedback = []
            iteration_count = 0
            final_status = "completed"

            for round_num in range(1, self.max_iterations + 1):
                iteration_count = round_num
                logger.info(f"\n{'='*40}")
                logger.info(f"[迭代轮次 {round_num}/{self.max_iterations}]")
                logger.info(f"{'='*40}")

                # Step 5: 策略转译
                logger.info(f"\n[Step 5] 策略转译 Agent (轮次 {round_num})...")
                self._report("strategy", "running", f"第{round_num}轮策略生成中...", round_num)
                strategies = self._run_strategy_agent(
                    topic, science_facts, context_analysis,
                    hypotheses, verification_results, iteration_feedback
                )
                self.state["strategies"] = strategies
                self._report("strategy", "completed", f"生成 {len(strategies.get('strategies', []))} 条策略", round_num)

                # Step 6: 评测
                logger.info(f"\n[Step 6] 评测迭代 Agent (轮次 {round_num})...")
                self._report("evaluation", "running", f"第{round_num}轮五维评分中...", round_num)
                eval_result = self._run_evaluator_agent(
                    topic, strategies, science_facts,
                    verification_results, round_num, iteration_feedback
                )

                # 解析评分
                scores_data = eval_result.get("scores", {})
                evaluation_scores = EvaluationScores(
                    factual_accuracy=scores_data.get("factual_accuracy", 70),
                    strategic_actionability=scores_data.get("strategic_actionability", 70),
                    audience_fit=scores_data.get("audience_fit", 70),
                    cultural_sensitivity=scores_data.get("cultural_sensitivity", 70),
                    narrative_fluency=scores_data.get("narrative_fluency", 70),
                )

                weighted_total = self.evaluation_engine.calculate_weighted_total(evaluation_scores)
                passed = weighted_total >= self.pass_threshold

                logger.info(f"  五维评分: {scores_data}")
                logger.info(f"  加权总分: {weighted_total:.1f} (阈值: {self.pass_threshold})")
                logger.info(f"  结果: {'通过 ✓' if passed else '未通过 ✗'}")
                self._report("evaluation", "completed" if passed else "running",
                             f"第{round_num}轮评分: {weighted_total:.1f}分 {'✓通过' if passed else '✗未达标，继续迭代...'}", round_num)

                # 记录经验
                self.evaluation_engine.log_experience(round_num, evaluation_scores, [])

                # Step 7: 判断是否继续迭代
                if passed:
                    logger.info(f"\n✓ 第 {round_num} 轮通过，Pipeline 完成！")
                    final_status = "completed"
                    break

                if round_num >= self.max_iterations:
                    logger.info(f"\n✗ 已达最大迭代轮数，Pipeline 结束")
                    final_status = "max_iterations_reached"
                    break

                # 生成迭代反馈
                logger.info(f"\n[Step 7] 生成迭代反馈...")
                iteration_feedback = self.evaluation_engine.generate_feedback(
                    evaluation_scores, eval_result
                )
                for fb in iteration_feedback:
                    logger.info(f"  - {fb.dimension}: {fb.current_score} -> {fb.target_agent}")

            # 构建最终结果
            result = self._build_result(
                topic=topic,
                science_facts=science_facts,
                context_analysis=context_analysis,
                hypotheses=hypotheses.get("hypotheses", []),
                verification_results=verification_results,
                strategies=strategies.get("strategies", []),
                evaluation_scores=evaluation_scores,
                iteration_feedback=iteration_feedback,
                iteration_count=iteration_count,
                final_status=final_status,
                search_sources=self.state.get("search_sources", []),
            )

            logger.info(f"\n{'='*60}")
            logger.info(f"Pipeline 完成！状态: {final_status}")
            logger.info(f"{'='*60}")

            return result

        except Exception as e:
            logger.error(f"Pipeline 执行失败: {e}", exc_info=True)
            return self._build_error_result(topic, str(e))

    def _run_science_agent(self, topic: str, search_context: str = "") -> Dict:
        """运行科学理解 Agent"""
        try:
            input_data = {"topic": topic}
            if search_context:
                input_data["search_context"] = search_context
            result = self.science_agent.run(input_data)
            return result
        except Exception as e:
            logger.error(f"科学理解 Agent 失败: {e}")
            # 返回降级结果
            return {"topic": topic, "key_facts": [], "entities": [], "relations": [], "timeline": [], "data_sources": []}

    def _run_context_agent(self, topic: str, science_facts: Dict, search_context: str = "") -> Dict:
        """运行语境分析 Agent"""
        try:
            input_data = {
                "topic": topic,
                "science_facts": science_facts,
            }
            if search_context:
                input_data["search_context"] = search_context
            result = self.context_agent.run(input_data)
            return result
        except Exception as e:
            logger.error(f"语境分析 Agent 失败: {e}")
            return {"topic": topic, "country_analysis": [], "framework_distribution": {}, "sentiment_summary": {}, "key_narratives": [], "cross_cultural_differences": []}

    def _run_hypothesis_agent(self, topic: str, science_facts: Dict, context_analysis: Dict) -> Dict:
        """运行假设生成 Agent"""
        try:
            result = self.hypothesis_agent.run({
                "topic": topic,
                "science_facts": science_facts,
                "context_analysis": context_analysis,
            })
            return result
        except Exception as e:
            logger.error(f"假设生成 Agent 失败: {e}")
            return {"topic": topic, "hypotheses": [], "reasoning_chain": "", "hypothesis_count": 0}

    def _run_verification(self, science_facts: Dict, hypotheses: Dict) -> List[VerificationResult]:
        """运行校验层"""
        try:
            # 校验科学事实
            fact_results = self.cross_validator.validate_science_facts(science_facts)

            # 校验假设
            hyp_results = self.cross_validator.validate_hypotheses(
                hypotheses.get("hypotheses", [])
            )

            all_results = fact_results + hyp_results

            # 生成报告
            report = self.report_generator.generate_verification_report(
                all_results, topic=science_facts.get("topic", "")
            )
            self.state["verification_report"] = report

            return all_results
        except Exception as e:
            logger.error(f"校验层失败: {e}")
            return []

    def _run_strategy_agent(
        self,
        topic: str,
        science_facts: Dict,
        context_analysis: Dict,
        hypotheses: Dict,
        verification_results: List[VerificationResult],
        iteration_feedback: List[IterationFeedback],
    ) -> Dict:
        """运行策略转译 Agent"""
        try:
            input_data = {
                "topic": topic,
                "science_facts": science_facts,
                "context_analysis": context_analysis,
                "hypotheses": hypotheses.get("hypotheses", []),
                "verification_report": [r.model_dump() for r in verification_results[:5]],
            }

            # 如果有迭代反馈，加入输入
            if iteration_feedback:
                input_data["iteration_feedback"] = [fb.model_dump() for fb in iteration_feedback]

            result = self.strategy_agent.run(input_data)
            return result
        except Exception as e:
            logger.error(f"策略转译 Agent 失败: {e}")
            return {"topic": topic, "strategies": [], "audience_coverage": [], "cultural_notes": []}

    def _run_evaluator_agent(
        self,
        topic: str,
        strategies: Dict,
        science_facts: Dict,
        verification_results: List[VerificationResult],
        round_num: int,
        previous_feedback: List[IterationFeedback],
    ) -> Dict:
        """运行评测迭代 Agent"""
        try:
            input_data = {
                "topic": topic,
                "strategies": strategies.get("strategies", []),
                "science_facts": science_facts,
                "verification_report": [r.model_dump() for r in verification_results[:5]],
                "iteration_round": round_num,
                "previous_feedback": [fb.model_dump() for fb in previous_feedback] if previous_feedback else [],
            }

            result = self.evaluator_agent.run(input_data)
            return result
        except Exception as e:
            logger.error(f"评测迭代 Agent 失败: {e}")
            # 返回默认评分
            return {
                "scores": {
                    "factual_accuracy": 70,
                    "strategic_actionability": 70,
                    "audience_fit": 70,
                    "cultural_sensitivity": 70,
                    "narrative_fluency": 70,
                },
                "weighted_total": 70,
                "passed": False,
                "feedback": [],
                "experience_log": f"评测异常: {str(e)}",
                "audience_simulation": [],
            }

    def _build_result(
        self,
        topic: str,
        science_facts: Dict,
        context_analysis: Dict,
        hypotheses: List,
        verification_results: List[VerificationResult],
        strategies: List,
        evaluation_scores: Optional[EvaluationScores],
        iteration_feedback: List[IterationFeedback],
        iteration_count: int,
        final_status: str,
        search_sources: List[Dict] = None,
    ) -> PipelineResult:
        """构建最终结果"""
        # 解析假设
        parsed_hypotheses = []
        for h in hypotheses:
            if isinstance(h, dict):
                try:
                    parsed_hypotheses.append(Hypothesis(**h))
                except Exception as pe:
                    logger.warning(f"Hypothesis parse failed: {pe}")

        # 解析策略
        parsed_strategies = []
        for s in strategies:
            if isinstance(s, dict):
                try:
                    parsed_strategies.append(Strategy(**s))
                except Exception as pe:
                    logger.warning(f"Strategy parse failed: {pe}")

        return PipelineResult(
            topic=topic,
            timestamp=datetime.now().isoformat(),
            science_facts=science_facts,
            context_analysis=context_analysis,
            hypotheses=parsed_hypotheses,
            verification_report=verification_results,
            strategies=parsed_strategies,
            evaluation=evaluation_scores or EvaluationScores(
                factual_accuracy=0, strategic_actionability=0,
                audience_fit=0, cultural_sensitivity=0, narrative_fluency=0
            ),
            iteration_feedback=iteration_feedback,
            iteration_count=iteration_count,
            final_status=final_status,
            search_sources=search_sources or [],
        )

    def _build_error_result(self, topic: str, error_msg: str) -> PipelineResult:
        """构建错误结果"""
        return PipelineResult(
            topic=topic,
            timestamp=datetime.now().isoformat(),
            science_facts={},
            context_analysis={},
            hypotheses=[],
            verification_report=[],
            strategies=[],
            evaluation=EvaluationScores(
                factual_accuracy=0, strategic_actionability=0,
                audience_fit=0, cultural_sensitivity=0, narrative_fluency=0
            ),
            iteration_feedback=[],
            iteration_count=0,
            final_status=f"error: {error_msg}",
        )

    def get_state(self) -> Dict:
        """获取当前 Pipeline 状态"""
        return self.state

    def get_iteration_summary(self) -> Dict:
        """获取迭代总结"""
        return self.evaluation_engine.get_iteration_summary()
