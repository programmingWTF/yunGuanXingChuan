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

from config.settings import MAX_ITERATION_ROUNDS, PASS_THRESHOLD, ENABLE_AGENT_TOOLS
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

    def _report(self, step: str, status: str, message: str = "", round_num: int = 0, full_content: str = ""):
        """上报阶段进度"""
        if self.progress_callback:
            self.progress_callback(step, status, message, round_num, full_content)

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
                self._report("pipeline.strategy", "completed", f"生成{len(strategies.get('strategies', []))}条策略")

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
                self.evaluation_engine.log_experience(round_num, evaluation_scores, [], topic=topic)

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

    def run_with_motions(
        self,
        topic: str,
        motions: List,
        minority_opinions: List = None,
        debate_transcript: List = None,
        science_facts: Dict = None,
        context_analysis: Dict = None,
    ) -> Dict:
        """
        修复4: 议会接驳 Pipeline —— 跳过前3步，直接从校验开始

        Args:
            topic: 议题
            motions: 议会通过的动议列表 (Motion model_dump)
            minority_opinions: 少数派意见列表
            debate_transcript: 辩论记录
            science_facts: 可选科学事实
            context_analysis: 可选语境分析

        Returns:
            包含 verification/strategies/evaluation 的字典
        """
        logger.info(f"\n[Pipeline 接驳] 从议会动议开始校验+策略生成...")
        self._report("pipeline.search", "running", "Tavily + 百炼搜索中...")
        try:
            search_service = get_unified_search_service()
            search_sources = search_service.search_for_topic(topic)
        except Exception:
            search_sources = []
            self._report("pipeline.search", "completed", "搜索跳过")
        else:
            search_content = json.dumps([s.to_dict() for s in search_sources], ensure_ascii=False, indent=2)[:5000]
            self._report("pipeline.search", "completed", f"获取{len(search_sources)}条来源", full_content=search_content)

        science_facts = science_facts or {"topic": topic, "key_facts": []}
        context_analysis = context_analysis or {"topic": topic}
        minority_opinions = minority_opinions or []

        # 将动议转换为假设格式供校验层使用
        hypotheses_as_dict = {
            "topic": topic,
            "hypotheses": [
                {
                    "hypothesis_id": m.get("motion_id", f"M{i}"),
                    "statement": m.get("content", ""),
                    "evidence_chain": [{"source": "议会辩论", "quote": e, "relevance": 0.8}
                                       for e in m.get("supporting_evidence", [])],
                    "confidence": m.get("confidence", 0.7),
                    "verification_path": "议会投票通过",
                    "falsification_criteria": "少数派意见: " + "; ".join(
                        mo.get("objection", "") if isinstance(mo, dict) else str(mo)
                        for mo in minority_opinions[:3]
                    ) if minority_opinions else "无",
                }
                for i, m in enumerate(motions)
            ],
        }

        # 校验层
        self._report("pipeline.verification", "running", "RAG + KG + Wikidata 交叉验证中...")
        try:
            verification_results = self._run_verification(science_facts, hypotheses_as_dict)
        except Exception as e:
            logger.warning(f"校验层异常: {e}")
            verification_results = []
        verify_content = json.dumps([r.model_dump() for r in verification_results], ensure_ascii=False, indent=2)[:5000]
        self._report("pipeline.verification", "completed", f"校验{len(verification_results)}条断言", full_content=verify_content)

        # Step 5-7: 策略生成 + 评测 + 迭代
        strategies = {}
        evaluation_scores = None
        iteration_feedback = []

        for round_num in range(1, self.max_iterations + 1):
            self._report("pipeline.strategy:r{}".format(round_num), "running", f"第{round_num}轮策略生成中...")

            # 策略生成（注入少数派风险提示）
            strategy_input = {
                "topic": topic,
                "science_facts": science_facts,
                "context_analysis": context_analysis,
                "hypotheses": hypotheses_as_dict["hypotheses"],
                "verification_report": [r.model_dump() for r in verification_results[:5]],
                "minority_opinions": [
                    mo.model_dump() if hasattr(mo, 'model_dump') else mo
                    for mo in minority_opinions
                ],
            }
            if iteration_feedback:
                strategy_input["iteration_feedback"] = [fb.model_dump() for fb in iteration_feedback]

            try:
                strategies = self.strategy_agent.run_with_tools(strategy_input) if ENABLE_AGENT_TOOLS else self.strategy_agent.run(strategy_input)
            except Exception as e:
                logger.warning(f"策略生成失败: {e}")
                strategies = {"topic": topic, "strategies": []}

            strategy_content = json.dumps(strategies, ensure_ascii=False, indent=2)[:5000]
            self._report("pipeline.strategy:r{}".format(round_num), "completed",
                         f"生成{len(strategies.get('strategies', []))}条策略", full_content=strategy_content)

            # 评测（优化：不使用 Tool Use，直接 run()，避免多轮 LLM 调用）
            self._report("pipeline.evaluation:r{}".format(round_num), "running", f"第{round_num}轮五维评分中...")
            eval_input = {
                "topic": topic,
                "strategies": strategies.get("strategies", []),
                "science_facts": science_facts,
                "verification_report": [r.model_dump() for r in verification_results[:5]],
                "iteration_round": round_num,
                "previous_feedback": [fb.model_dump() for fb in iteration_feedback],
                "minority_opinions": [
                    mo.model_dump() if hasattr(mo, 'model_dump') else mo
                    for mo in minority_opinions
                ],
                "debate_transcript_summary": f"共{len(debate_transcript or [])}轮辩论",
            }
            try:
                eval_result = self.evaluator_agent.run(eval_input)
            except Exception as e:
                logger.warning(f"评测失败: {e}")
                eval_result = {"scores": {"factual_accuracy": 70, "strategic_actionability": 70, "audience_fit": 70, "cultural_sensitivity": 70, "narrative_fluency": 70}, "weighted_total": 70, "passed": False, "feedback": [], "experience_log": f"评测异常: {e}", "audience_simulation": []}

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
            eval_content = json.dumps(eval_result, ensure_ascii=False, indent=2)[:5000]
            self._report("pipeline.evaluation:r{}".format(round_num), "completed",
                         f"加权总分{weighted_total:.1f}({'通过' if passed else '未通过'})",
                         full_content=eval_content)

            if passed:
                break

            # 生成迭代反馈（从评测结果的 feedback 列表构造）
            eval_feedback = eval_result.get("feedback", [])
            for fb_item in eval_feedback:
                try:
                    fb = IterationFeedback(
                        dimension=fb_item.get("dimension", ""),
                        current_score=fb_item.get("current_score", float(weighted_total)),
                        issue=fb_item.get("issue", ""),
                        suggestion=fb_item.get("suggestion", ""),
                        target_agent=fb_item.get("target_agent", "strategy_agent"),
                    )
                    iteration_feedback.append(fb)
                except Exception:
                    pass
            self.evaluation_engine.log_experience(round_num, evaluation_scores, iteration_feedback, topic=topic)

        return {
            "verification_results": [r.model_dump() for r in verification_results],
            "strategies": strategies,
            "evaluation": evaluation_scores.model_dump() if evaluation_scores else {},
            "iteration_feedback": [fb.model_dump() for fb in iteration_feedback],
            "search_sources": [s.to_dict() for s in search_sources] if search_sources else [],
        }

    def _run_science_agent(self, topic: str, search_context: str = "") -> Dict:
        """运行科学理解 Agent"""
        try:
            input_data = {"topic": topic}
            if search_context:
                input_data["search_context"] = search_context
            if ENABLE_AGENT_TOOLS:
                result = self.science_agent.run_with_tools(input_data)
            else:
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
            if ENABLE_AGENT_TOOLS:
                result = self.context_agent.run_with_tools(input_data)
            else:
                result = self.context_agent.run(input_data)
            return result
        except Exception as e:
            logger.error(f"语境分析 Agent 失败: {e}")
            return {"topic": topic, "country_analysis": [], "framework_distribution": {}, "sentiment_summary": {}, "key_narratives": [], "cross_cultural_differences": []}

    def _run_hypothesis_agent(self, topic: str, science_facts: Dict, context_analysis: Dict) -> Dict:
        """运行假设生成 Agent"""
        try:
            input_data = {
                "topic": topic,
                "science_facts": science_facts,
                "context_analysis": context_analysis,
            }
            if ENABLE_AGENT_TOOLS:
                result = self.hypothesis_agent.run_with_tools(input_data)
            else:
                result = self.hypothesis_agent.run(input_data)
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

            # 生成报告（失败不影响结果返回）
            try:
                report = self.report_generator.generate_verification_report(
                    all_results, topic=science_facts.get("topic", "")
                )
                self.state["verification_report"] = report
            except Exception as e:
                logger.warning(f"校验报告生成失败（不影响结果）: {e}")

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

            result = self.strategy_agent.run_with_tools(input_data) if ENABLE_AGENT_TOOLS else self.strategy_agent.run(input_data)
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

            result = self.evaluator_agent.run_with_tools(input_data) if ENABLE_AGENT_TOOLS else self.evaluator_agent.run(input_data)
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


# ==========================================================================
# 认知议会 (Cognitive Parliament) 编排器
# ==========================================================================


class CognitiveParliament:
    """
    认知议会编排器（与 Pipeline 并列）

    将五个 Agent 从流水线工人变成学术研讨会参与者：
    Speaker（议长）主持辩论，Scientist 提案，Skeptic 挑漏洞，
    Humanist 审文化风险，Strategist 做可行性评估。

    输出：完整的议会记录 (DeliberationTranscript)
    """

    def __init__(self, max_rounds: int = None, max_pipeline_rounds: int = None, progress_callback=None):
        """
        Args:
            max_rounds: 最大辩论轮次（默认从配置读取）
            max_pipeline_rounds: Pipeline 评测最大轮次（默认从配置读取）
            progress_callback: 进度回调
        """
        from config.settings import PARLIAMENT_MAX_ROUNDS, MAX_ITERATION_ROUNDS
        from src.parliament.speaker import SpeakerAgent
        from src.parliament.debate_engine import DebateEngine
        from src.agents.humanist_agent import HumanistAgent

        self.max_rounds = max_rounds or PARLIAMENT_MAX_ROUNDS
        self.max_pipeline_rounds = max_pipeline_rounds or MAX_ITERATION_ROUNDS
        self.progress_callback = progress_callback

        # 议长
        self.speaker = SpeakerAgent()

        # 复用现有 Agent + 新增 Humanist
        self.scientist = ScienceAgent()
        self.context_agent = ContextAgent()
        self.hypothesis_agent = HypothesisAgent()
        self.strategy_agent = StrategyAgent()
        self.evaluator_agent = EvaluatorAgent()
        self.humanist = HumanistAgent()

        # 参与者字典（辩论引擎用）
        self.agents = {
            "scientist": self.scientist,
            "skeptic": self.hypothesis_agent,   # 假设Agent充当质疑者
            "humanist": self.humanist,
            "strategist": self.strategy_agent,
            "evaluator": self.evaluator_agent,
        }

        # 辩论引擎
        self.debate_engine = DebateEngine(
            speaker=self.speaker,
            agents=self.agents,
            max_rounds=self.max_rounds,
        )
        self.debate_engine.progress_callback = self.progress_callback

    def _report(self, step: str, status: str, message: str, full_content: str = ""):
        """上报进度"""
        if self.progress_callback:
            self.progress_callback(step, status, message, 0, full_content)

    def convene(self, topic: str, science_facts: Dict = None,
                context_analysis: Dict = None) -> "DeliberationTranscript":
        """
        召集议会：返回完整辩论记录

        Args:
            topic: 议题
            science_facts: 可选的科学事实数据
            context_analysis: 可选的语境分析数据

        Returns:
            DeliberationTranscript
        """
        from src.schemas import DeliberationTranscript

        logger.info(f"\n{'='*60}")
        logger.info(f"AI Scientist 工作流启动: {topic}")
        logger.info(f"{'='*60}")
        self._report("parliament", "running", f"AI Scientist 工作流启动: {topic}")

        # 1. 开幕（debate_engine 内部已上报 scientist/humanist 进度）
        logger.info("\n[开幕] 生成初始动议...")
        motions = self.debate_engine.open_parliament(
            topic=topic,
            science_facts=science_facts,
            context_analysis=context_analysis,
        )
        self._report("opening.motions_generated", "completed", f"生成 {len(motions)} 条动议",
                     json.dumps([m.model_dump() for m in motions], ensure_ascii=False, indent=2)[:6000])
        self._report("opening", "completed", f"生成 {len(motions)} 条初始动议")

        # 2. 辩论循环
        round_num = 0
        while not self.debate_engine.should_close():
            round_num += 1
            logger.info(f"\n[辩论轮次 {round_num}/{self.max_rounds}]")
            self._report("debate", "running", f"第{round_num}轮辩论中...")

            debate_round = self.debate_engine.debate_round(round_num)
            if debate_round is None:
                break

            # 每轮完成后不标记整个 debate phase 为 completed，仅更新 message
            self._report("debate", "running",
                         f"第{round_num}轮完成，表决 {debate_round.topic}")

        # 所有辩论轮次结束后才标记完成
        self._report("debate", "completed", f"辩论结束，共{round_num}轮")

        # 3. 接驳 Pipeline：校验 + 策略生成 + 评测
        logger.info("\n[Pipeline 接驳] 议会动议进入校验+策略生成...")
        self._report("pipeline", "running", "议会动议进入 Pipeline 校验...")

        passed_motions = [
            m for m in self.debate_engine.motions
            if any(v.motion_id == m.motion_id and v.result == "passed"
                   for v in self.debate_engine.votes)
        ]
        pipeline_result = {}
        if passed_motions:
            try:
                pipeline = Pipeline(progress_callback=self.progress_callback, max_iterations=self.max_pipeline_rounds)
                pipeline_result = pipeline.run_with_motions(
                    topic=topic,
                    motions=[m.model_dump() for m in passed_motions],
                    minority_opinions=self.debate_engine.minority_opinions,
                    debate_transcript=[r.model_dump() for r in self.debate_engine.rounds],
                    science_facts=science_facts,
                    context_analysis=context_analysis,
                )
                self._report("pipeline", "completed", "Pipeline 校验+策略完成")
            except Exception as e:
                logger.warning(f"Pipeline 接驳失败: {e}")
                self._report("pipeline", "error", f"Pipeline 接驳异常: {e}")

        # 4. 生成最终策略（融合 Pipeline 结果）
        logger.info("\n[策略整合] 融合议会辩论 + Pipeline 结果...")
        self._report("pipeline.strategy", "running", "最终策略整合中...")
        final_strategies = self._generate_final_strategies(topic)
        if pipeline_result:
            final_strategies["pipeline_verification"] = pipeline_result.get("verification_results", [])
            final_strategies["pipeline_strategies"] = pipeline_result.get("strategies", {})
            final_strategies["pipeline_evaluation"] = pipeline_result.get("evaluation", {})
            final_strategies["search_sources"] = pipeline_result.get("search_sources", [])
        self._report("pipeline.strategy", "completed", "策略整合完成")
        self._report("pipeline", "completed", "校验+策略+评测全部完成")

        # 5. 闭幕
        transcript = self.debate_engine.close_parliament(
            final_strategies=final_strategies
        )

        # 6. 生成最终总结报告（结构化：核心结论/TOP3策略/风险/受众建议）
        logger.info("\n[最终总结] 生成结构化总结报告...")
        self._report("summary.report", "running", "总结报告生成中...")
        final_report = self._generate_final_report(topic, transcript)
        transcript.final_report = final_report
        self._report("summary.report", "completed", "总结报告生成完成",
                     json.dumps(final_report, ensure_ascii=False, indent=2))
        self._report("summary", "completed", "最终总结报告完成")

        self._report("parliament", "completed",
                     f"议会闭幕: {transcript.total_rounds}轮, "
                     f"{len(transcript.votes)}次表决, "
                     f"{len(transcript.minority_opinions)}条少数派意见")

        return transcript

    def _generate_final_report(self, topic: str, transcript) -> Dict:
        """生成结构化最终总结报告（LLM 失败时用规则式兑底）"""
        fs = transcript.final_strategies or {}
        passed = [m.content for m in transcript.motions
                  if any(v.motion_id == m.motion_id and v.result == "passed"
                         for v in transcript.votes)]
        minority = [f"{mo.agent}: {mo.objection}" for mo in transcript.minority_opinions]
        strategies = (fs.get("pipeline_strategies") or {}).get("strategies") or fs.get("strategies") or []
        evaluation = fs.get("pipeline_evaluation") or {}

        user_prompt = f"""请基于以下 AI Scientist 工作流完整结果，撰写一份面向决策者的最终总结报告。

## 议题
{topic}

## 辩论情况
共 {transcript.total_rounds} 轮辩论，{len(transcript.votes)} 次表决

## 已通过的动议
{json.dumps(passed, ensure_ascii=False, indent=2)[:1500]}

## 少数派意见（风险信号）
{json.dumps(minority, ensure_ascii=False, indent=2)[:1000]}

## 传播策略
{json.dumps(strategies, ensure_ascii=False, indent=2)[:2500]}

## 五维评分
{json.dumps(evaluation, ensure_ascii=False)[:500]}

## 输出要求（严格 JSON）
{{
  "one_line_takeaway": "一句话核心结论（30字以内）",
  "core_conclusion": "核心结论（150-250字，回答：这个议题最终应该怎么传播）",
  "top_strategies": [
    {{"rank": 1, "title": "策略标题", "audience": "目标受众", "action": "具体执行建议（50字内）"}}
  ],
  "risk_warnings": ["风险提示1", "风险提示2"],
  "audience_recommendations": [
    {{"audience": "受众名称", "suggestion": "适配建议（50字内）"}}
  ]
}}

注意：top_strategies 最多3条（按优先级排序），risk_warnings 2-4条（必须吸收少数派意见），audience_recommendations 覆盖策略中出现的所有受众。"""

        try:
            report = self.speaker.llm_client.chat_json(
                system_prompt=(
                    "你是 AI Scientist 工作流的总结报告撰写人，擅长把多Agent辩论+策略+评分结果提炼成"
                    "决策者能直接使用的结构化报告。只输出 JSON。"
                ),
                user_prompt=user_prompt,
                temperature=0.3,
            )
            # 基本字段兑底补齐
            if not isinstance(report, dict) or not report.get("core_conclusion"):
                raise ValueError("总结报告缺少核心字段")
            report.setdefault("one_line_takeaway", "")
            report.setdefault("top_strategies", [])
            report.setdefault("risk_warnings", [])
            report.setdefault("audience_recommendations", [])
            report["top_strategies"] = report["top_strategies"][:3]
            return report
        except Exception as e:
            logger.warning(f"最终总结报告生成失败，使用规则式兑底: {e}")
            return build_fallback_final_report(
                topic=topic,
                passed_motions=passed,
                minority_opinions=minority,
                strategies=strategies if isinstance(strategies, list) else [],
                evaluation=evaluation if isinstance(evaluation, dict) else {},
                total_rounds=transcript.total_rounds,
            )

    def _generate_final_strategies(self, topic: str) -> Dict:
        """基于已通过动议生成最终策略"""
        passed_motions = [
            m for m in self.debate_engine.motions
            if any(v.motion_id == m.motion_id and v.result == "passed"
                   for v in self.debate_engine.votes)
        ]

        try:
            strategy_result = self.strategy_agent.run({
                "topic": topic,
                "science_facts": {},
                "context_analysis": {},
                "hypotheses": [m.model_dump() for m in passed_motions],
                "verification_report": [],
            })
            return strategy_result
        except Exception as e:
            logger.warning(f"策略生成失败: {e}")
            return {
                "topic": topic,
                "strategies": [],
                "note": f"策略生成异常: {e}",
                "passed_motions": [m.content for m in passed_motions],
            }


def build_fallback_final_report(topic: str, passed_motions: List[str],
                                minority_opinions: List[str],
                                strategies: List[Dict], evaluation: Dict,
                                total_rounds: int = 0) -> Dict:
    """
    规则式最终总结报告兑底（LLM 不可用时从已有结果拼装）

    Args:
        topic: 议题
        passed_motions: 已通过动议内容列表
        minority_opinions: 少数派意见文本列表
        strategies: 策略字典列表
        evaluation: 五维评分字典
        total_rounds: 辩论轮次

    Returns:
        结构化最终报告字典（与 LLM 版同构）
    """
    top_strategies = []
    audience_recs = []
    seen_audiences = set()
    for i, s in enumerate(strategies[:3], 1):
        if not isinstance(s, dict):
            continue
        audience = s.get("target_audience", "") or "通用受众"
        top_strategies.append({
            "rank": i,
            "title": s.get("narrative_angle") or s.get("narrative_persona") or f"策略{i}",
            "audience": audience,
            "action": "; ".join((s.get("key_messages") or [])[:2])[:80] or "按策略要点执行",
        })
        if audience not in seen_audiences:
            seen_audiences.add(audience)
            audience_recs.append({
                "audience": audience,
                "suggestion": (s.get("channel_recommendations") or ["多渠道传播"])[0]
                if isinstance(s.get("channel_recommendations"), list) else "多渠道传播",
            })

    risk_warnings = [m[:100] for m in minority_opinions[:4]]
    if not risk_warnings:
        risk_warnings = ["暂无显著风险信号，建议持续监测舆情变化"]

    scores = [v for v in evaluation.values() if isinstance(v, (int, float))]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    conclusion_parts = [f"议题「{topic}」经 {total_rounds} 轮 AI Scientist 工作流辩论，"]
    if passed_motions:
        conclusion_parts.append(f"共通过 {len(passed_motions)} 条动议，核心共识：{passed_motions[0][:80]}。")
    else:
        conclusion_parts.append("未形成通过动议，建议补充证据后重新审议。")
    if avg is not None:
        conclusion_parts.append(f"策略方案五维评分均分 {avg}。")
    if strategies:
        conclusion_parts.append(f"已产出 {len(strategies)} 条可执行传播策略。")

    return {
        "one_line_takeaway": f"{topic}：{len(passed_motions)}条共识动议，{len(strategies)}条传播策略"[:30],
        "core_conclusion": "".join(conclusion_parts),
        "top_strategies": top_strategies,
        "risk_warnings": risk_warnings,
        "audience_recommendations": audience_recs,
        "generated_by": "fallback",
    }
