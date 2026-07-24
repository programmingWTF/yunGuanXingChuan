"""
云观星传 - 评测模块
五维评分矩阵 + 四步自迭代闭环 + SQLite 经验池持久化
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PASS_THRESHOLD, MAX_ITERATION_ROUNDS, EVALUATION_WEIGHTS
from src.schemas import EvaluationScores, IterationFeedback, EvaluationResult
from src.knowledge.experience_store import get_experience_store

logger = logging.getLogger(__name__)


class EvaluationEngine:
    """评测引擎：五维评分 + 四步自迭代闭环"""

    def __init__(
        self,
        pass_threshold: float = PASS_THRESHOLD,
        max_rounds: int = MAX_ITERATION_ROUNDS,
    ):
        """
        Args:
            pass_threshold: 通过阈值（加权总分）
            max_rounds: 最大迭代轮数
        """
        self.pass_threshold = pass_threshold
        self.max_rounds = max_rounds
        self.weights = EVALUATION_WEIGHTS
        self.experience_pool: List[Dict] = []  # 经验池
        self.iteration_history: List[Dict] = []  # 迭代历史

    def calculate_weighted_total(self, scores: EvaluationScores) -> float:
        """Calculate weighted total using centralized weights from config."""
        return scores.weighted_total

    def check_passed(self, scores: EvaluationScores) -> bool:
        """
        检查是否通过

        Args:
            scores: 五维评分

        Returns:
            是否通过
        """
        weighted_total = self.calculate_weighted_total(scores)
        return weighted_total >= self.pass_threshold

    def identify_weak_dimensions(self, scores: EvaluationScores, threshold: float = 60) -> List[str]:
        """
        识别低分维度

        Args:
            scores: 五维评分
            threshold: 低分阈值

        Returns:
            低分维度列表
        """
        weak_dims = []
        score_dict = {
            "factual_accuracy": scores.factual_accuracy,
            "strategic_actionability": scores.strategic_actionability,
            "audience_fit": scores.audience_fit,
            "cultural_sensitivity": scores.cultural_sensitivity,
            "narrative_fluency": scores.narrative_fluency,
        }

        for dim, score in score_dict.items():
            if score < threshold:
                weak_dims.append(dim)

        # 按分数排序，最弱的在前
        weak_dims.sort(key=lambda d: score_dict[d])
        return weak_dims

    def generate_feedback(
        self,
        scores: EvaluationScores,
        evaluation_result: Optional[Dict] = None,
    ) -> List[IterationFeedback]:
        """
        生成迭代反馈（四步自迭代闭环的第3、4步）

        Args:
            scores: 五维评分
            evaluation_result: 评测 Agent 的原始输出

        Returns:
            迭代反馈列表
        """
        feedback_list = []

        # 识别最弱的 1-2 个维度
        weak_dims = self.identify_weak_dimensions(scores)

        # 如果没有低于 60 分的维度，取最低分的维度
        if not weak_dims:
            score_dict = {
                "factual_accuracy": scores.factual_accuracy,
                "strategic_actionability": scores.strategic_actionability,
                "audience_fit": scores.audience_fit,
                "cultural_sensitivity": scores.cultural_sensitivity,
                "narrative_fluency": scores.narrative_fluency,
            }
            sorted_dims = sorted(score_dict.items(), key=lambda x: x[1])
            weak_dims = [sorted_dims[0][0]]  # 只取最弱的 1 个

        # 限制最多改 2 个维度
        weak_dims = weak_dims[:2]

        # 维度到 Agent 的映射
        dim_to_agent = {
            "factual_accuracy": "science_agent",
            "strategic_actionability": "strategy_agent",
            "audience_fit": "strategy_agent",
            "cultural_sensitivity": "strategy_agent",
            "narrative_fluency": "strategy_agent",
        }

        # 从评测结果中提取反馈
        eval_feedback = evaluation_result.get("feedback", []) if evaluation_result else []

        for dim in weak_dims:
            score_dict = {
                "factual_accuracy": scores.factual_accuracy,
                "strategic_actionability": scores.strategic_actionability,
                "audience_fit": scores.audience_fit,
                "cultural_sensitivity": scores.cultural_sensitivity,
                "narrative_fluency": scores.narrative_fluency,
            }

            # 查找对应的评测反馈
            matching_feedback = next(
                (f for f in eval_feedback if f.get("dimension") == dim),
                None
            )

            feedback = IterationFeedback(
                dimension=dim,
                current_score=score_dict[dim],
                issue=matching_feedback.get("issue", f"{dim} 维度得分较低") if matching_feedback else f"{dim} 维度得分较低",
                suggestion=matching_feedback.get("suggestion", f"请改进 {dim} 维度") if matching_feedback else f"请改进 {dim} 维度",
                target_agent=dim_to_agent.get(dim, "strategy_agent"),
            )
            feedback_list.append(feedback)

        return feedback_list

    def log_experience(self, round_num: int, scores: EvaluationScores, feedback: List[IterationFeedback], topic: str = ""):
        """
        记录经验到经验池（四步自迭代闭环的第2步）
        同时写入内存池和 SQLite 持久化存储

        Args:
            round_num: 迭代轮次
            scores: 五维评分
            feedback: 迭代反馈
            topic: 议题名称（用于持久化）
        """
        experience = {
            "round": round_num,
            "scores": {
                "factual_accuracy": scores.factual_accuracy,
                "strategic_actionability": scores.strategic_actionability,
                "audience_fit": scores.audience_fit,
                "cultural_sensitivity": scores.cultural_sensitivity,
                "narrative_fluency": scores.narrative_fluency,
            },
            "weighted_total": self.calculate_weighted_total(scores),
            "passed": self.check_passed(scores),
            "weak_dimensions": self.identify_weak_dimensions(scores),
            "feedback_count": len(feedback),
        }

        self.experience_pool.append(experience)
        self.iteration_history.append(experience)

        # SQLite 持久化
        if topic:
            try:
                store = get_experience_store()
                store.log_experience(
                    topic=topic,
                    round_num=round_num,
                    scores=experience["scores"],
                    feedback=[fb.model_dump() if hasattr(fb, 'model_dump') else fb for fb in feedback],
                    passed=experience["passed"],
                    weak_dims=experience["weak_dimensions"],
                )
            except Exception as e:
                logger.warning(f"[经验池] SQLite 持久化失败（不影响主流程）: {e}")

        logger.info(
            f"[经验池] 第 {round_num} 轮: 加权总分 {experience['weighted_total']:.1f}, "
            f"{'通过' if experience['passed'] else '未通过'}"
        )

    def should_continue_iteration(self, scores: EvaluationScores, current_round: int) -> bool:
        """
        判断是否应该继续迭代

        Args:
            scores: 当前评分
            current_round: 当前轮次

        Returns:
            是否继续迭代
        """
        # 已达到最大轮数
        if current_round >= self.max_rounds:
            logger.info(f"已达到最大迭代轮数 ({self.max_rounds})")
            return False

        # 已通过
        if self.check_passed(scores):
            logger.info(f"已通过阈值 ({self.pass_threshold})")
            return False

        # 有维度低于 60 分，必须继续
        weak_dims = self.identify_weak_dimensions(scores, threshold=60)
        if weak_dims:
            logger.info(f"存在低分维度 {weak_dims}，继续迭代")
            return True

        # 未通过但无低分维度，也继续
        return True

    def get_iteration_summary(self) -> Dict:
        """
        获取迭代总结

        Returns:
            总结字典
        """
        if not self.iteration_history:
            return {"message": "没有迭代记录"}

        first = self.iteration_history[0]
        last = self.iteration_history[-1]

        improvement = {}
        for dim in first["scores"]:
            improvement[dim] = last["scores"][dim] - first["scores"][dim]

        return {
            "total_rounds": len(self.iteration_history),
            "initial_score": first["weighted_total"],
            "final_score": last["weighted_total"],
            "improvement": last["weighted_total"] - first["weighted_total"],
            "dimension_improvement": improvement,
            "final_passed": last["passed"],
            "history": self.iteration_history,
        }

    def load_past_experience(self, topic: str) -> Dict:
        """
        从 SQLite 加载历史经验（相似议题的最佳实践）

        Args:
            topic: 当前议题

        Returns:
            {similar_topics, common_weaknesses, global_insights}
        """
        try:
            store = get_experience_store()
            similar = store.find_similar_topics(topic, top_k=3)
            weaknesses = store.get_common_weaknesses(limit=3)
            insights = store.get_improvement_trend()

            if similar:
                logger.info(f"[经验池] 找到 {len(similar)} 个相似议题: {[s['topic'] for s in similar]}")

            return {
                "similar_topics": similar,
                "common_weaknesses": weaknesses,
                "global_insights": insights,
            }
        except Exception as e:
            logger.warning(f"[经验池] 加载历史经验失败: {e}")
            return {"similar_topics": [], "common_weaknesses": [], "global_insights": {}}

    def get_global_insights(self) -> Dict:
        """
        获取跨议题全局统计

        Returns:
            全局统计信息
        """
        try:
            store = get_experience_store()
            return {
                "trend": store.get_improvement_trend(),
                "weaknesses": store.get_common_weaknesses(),
            }
        except Exception as e:
            logger.warning(f"[经验池] 获取全局统计失败: {e}")
            return {"trend": {}, "weaknesses": []}
