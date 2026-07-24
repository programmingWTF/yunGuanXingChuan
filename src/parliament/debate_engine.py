"""
云观星传 - 辩论引擎（DebateEngine）
状态机: opening → debate(loop) → closing
管理轮次、发言、投票、权重、少数派意见
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import PARLIAMENT_MAX_ROUNDS, PARLIAMENT_DEADLOCK_THRESHOLD, PARLIAMENT_PASS_THRESHOLD
from src.schemas import (
    Motion, MotionType, Speech, DebateRound, VoteResult,
    MinorityOpinion, DeliberationTranscript,
)
from src.parliament.speaker import SpeakerAgent, WEIGHT_TEMPLATES

logger = logging.getLogger(__name__)


def _text_similarity(a: str, b: str) -> float:
    """简单文本相似度（字符 bigram 重叠）"""
    if not a or not b:
        return 0.0
    a_set = set(a[i:i+2] for i in range(len(a) - 1))
    b_set = set(b[i:i+2] for i in range(len(b) - 1))
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


class DebateEngine:
    """
    认知议会辩论引擎

    状态机: opening → debate(loop) → closing
    管理：轮次、发言顺序、加权投票、僵局裁定、少数派意见记录
    """

    def __init__(
        self,
        speaker: SpeakerAgent,
        agents: Dict[str, Any],
        max_rounds: int = PARLIAMENT_MAX_ROUNDS,
        deadlock_threshold: float = PARLIAMENT_DEADLOCK_THRESHOLD,
    ):
        """
        Args:
            speaker: 议长 Agent
            agents: 参与者字典 {"scientist": Agent, "humanist": Agent, ...}
            max_rounds: 最大辩论轮次
            deadlock_threshold: 僵持判定阈值
        """
        self.speaker = speaker
        self.agents = agents
        self.max_rounds = max_rounds
        self.deadlock_threshold = deadlock_threshold
        self.progress_callback = None  # 外部注入，用于上报发言进度

        # 辩论状态
        self.topic: str = ""
        self.rounds: List[DebateRound] = []
        self.motions: List[Motion] = []
        self.votes: List[VoteResult] = []
        self.minority_opinions: List[MinorityOpinion] = []
        self.started_at: str = ""
        self._previous_speakers: List[str] = []
        self._motion_amend_count: Dict[str, int] = {}  # 动议修正次数
        self._consecutive_no_improvement: int = 0
        self._last_score: float = 0.0

    def open_parliament(self, topic: str, science_facts: Dict = None,
                        context_analysis: Dict = None) -> List[Motion]:
        """
        开幕：Scientist + Humanist 开场报告，生成首批动议

        Args:
            topic: 议题
            science_facts: 科学事实数据
            context_analysis: 语境分析数据

        Returns:
            首批动议列表
        """
        self.topic = topic
        self.started_at = datetime.now().isoformat()
        logger.info(f"[议会开幕] 议题: {topic}")

        motions: List[Motion] = []

        # Scientist 开场报告
        if "scientist" in self.agents:
            if self.progress_callback:
                self.progress_callback("opening.scientist_report", "running", "Scientist 科学事实扫描中...")
            try:
                sci_result = self.agents["scientist"].run({
                    "topic": topic,
                    "task_type": "opening_report",
                    "science_facts": science_facts or {},
                })
                sci_motions = sci_result.get("motions", [])
                for m in sci_motions[:3]:
                    motion = Motion(
                        motion_id=m.get("motion_id", f"M_S{len(motions)+1:03d}"),
                        motion_type=MotionType(m.get("motion_type", "fact_claim")),
                        proposer="scientist",
                        content=m.get("content", ""),
                        supporting_evidence=m.get("supporting_evidence", []),
                        confidence=m.get("confidence", 0.7),
                    )
                    motions.append(motion)
                logger.info(f"  [Scientist] 提出 {len(sci_motions[:3])} 条动议")
                if self.progress_callback:
                    import json as _json
                    self.progress_callback("opening.scientist_report", "completed",
                                           f"科学事实扫描完成，提出{len(sci_motions[:3])}条动议",
                                           _json.dumps(sci_result, ensure_ascii=False, indent=2)[:6000])
            except Exception as e:
                logger.warning(f"  [Scientist] 开场报告失败: {e}")
                if self.progress_callback:
                    self.progress_callback("opening.scientist_report", "completed", f"科学事实扫描完成（异常: {e}）")

        # Humanist 开场报告
        if "humanist" in self.agents:
            if self.progress_callback:
                self.progress_callback("opening.humanist_report", "running", "Humanist 文化敏感审查中...")
            try:
                hum_result = self.agents["humanist"].run({
                    "topic": topic,
                    "task_type": "opening_report",
                    "science_facts": science_facts or {},
                    "context_analysis": context_analysis or {},
                })
                hum_motions = hum_result.get("motions", [])
                for m in hum_motions[:2]:
                    motion = Motion(
                        motion_id=m.get("motion_id", f"M_H{len(motions)+1:03d}"),
                        motion_type=MotionType(m.get("motion_type", "hypothesis")),
                        proposer="humanist",
                        content=m.get("content", ""),
                        supporting_evidence=m.get("supporting_evidence", []),
                        confidence=m.get("confidence", 0.6),
                    )
                    motions.append(motion)
                logger.info(f"  [Humanist] 提出 {len(hum_motions[:2])} 条动议")
                if self.progress_callback:
                    import json as _json
                    self.progress_callback("opening.humanist_report", "completed",
                                           f"文化敏感审查完成，提出{len(hum_motions[:2])}条动议",
                                           _json.dumps(hum_result, ensure_ascii=False, indent=2)[:6000])
            except Exception as e:
                logger.warning(f"  [Humanist] 开场报告失败: {e}")
                if self.progress_callback:
                    self.progress_callback("opening.humanist_report", "completed", f"文化敏感审查完成（异常: {e}）")

        # 如果 Agent 没有生成动议，创建默认动议
        if self.progress_callback:
            self.progress_callback("opening.motions_generated", "running", "正在汇总动议...")
        if not motions:
            motions = [
                Motion(
                    motion_id="M001",
                    motion_type=MotionType.FACT_CLAIM,
                    proposer="scientist",
                    content=f"关于{topic}的核心科学事实准确性确认",
                    supporting_evidence=["基于已有科学知识"],
                    confidence=0.8,
                ),
                Motion(
                    motion_id="M002",
                    motion_type=MotionType.HYPOTHESIS,
                    proposer="humanist",
                    content=f"关于{topic}国际传播的文化适配策略假设",
                    supporting_evidence=["跨文化传播理论"],
                    confidence=0.6,
                ),
            ]

        self.motions = motions
        logger.info(f"  共生成 {len(motions)} 条动议待辩论")
        return motions

    def debate_round(self, round_num: int) -> Optional[DebateRound]:
        """
        执行一轮辩论

        流程：Speaker 规划 → 联网搜索 → 指定 Agent 发言 → 投票表决

        Args:
            round_num: 当前轮次号

        Returns:
            DebateRound 或 None（如果进入闭幕）
        """
        logger.info(f"\n[第 {round_num} 轮辩论]")

        # 1. Speaker 规划本轮
        pending_motions = [
            m for m in self.motions
            if not any(v.motion_id == m.motion_id and v.result in ("passed", "rejected")
                       for v in self.votes)
        ]
        if not pending_motions:
            logger.info("  所有动议已表决，进入闭幕")
            return None

        plan = self.speaker.plan_round(
            topic=self.topic,
            round_num=round_num,
            motions=[m.model_dump() for m in pending_motions],
            previous_speakers=self._previous_speakers,
            debate_history=[r.model_dump() for r in self.rounds],
            motion_results=[v.model_dump() for v in self.votes],
        )

        if plan.get("phase") == "closing":
            logger.info("  Speaker 宣布进入闭幕阶段")
            return None

        current_topic = plan.get("current_topic", f"第{round_num}轮讨论")
        next_speakers = plan.get("next_speakers", ["scientist", "humanist"])
        weights = plan.get("speaker_weights", WEIGHT_TEMPLATES["fact"])
        rationale = plan.get("weight_rationale", "")
        motion_to_vote_id = plan.get("motion_to_vote", pending_motions[0].motion_id)

        logger.info(f"  主题: {current_topic}")
        logger.info(f"  发言者: {next_speakers}")
        logger.info(f"  权重理由: {rationale}")

        # 1.5 联网搜索（Tavily + 百炼 WebSearch）—— 每轮一次，所有发言者共享
        search_context = ""
        try:
            from src.search.unified_search import get_unified_search_service
            search_service = get_unified_search_service()
            search_query = f"{self.topic} {current_topic}"
            search_sources = search_service.search_for_topic(search_query[:80])
            if search_sources:
                search_context = search_service.format_search_context(search_sources)
                logger.info(f"  联网搜索获取 {len(search_sources)} 条来源")
        except Exception as e:
            logger.warning(f"  联网搜索失败（不影响辩论）: {e}")

        # 2. 顺序发言
        speeches: List[Speech] = []
        motion_to_vote = next(
            (m for m in self.motions if m.motion_id == motion_to_vote_id),
            pending_motions[0]
        )

        for speaker_name in next_speakers:
            if speaker_name not in self.agents:
                logger.warning(f"  Agent '{speaker_name}' 不存在，跳过")
                continue

            agent = self.agents[speaker_name]
            # 上报发言进度
            if self.progress_callback:
                self.progress_callback(
                    f"debate.speaker:R{round_num}:{speaker_name}",
                    "running",
                    f"第{round_num}轮 {speaker_name} 发言中..."
                )
            # 修复3: 温度差异化
            original_temp = getattr(agent, 'temperature', 0.3)
            if speaker_name in ("skeptic", "humanist"):
                agent.temperature = 0.5
            try:
                speech_result = agent.run({
                    "topic": self.topic,
                    "task_type": "debate_speech",
                    "current_motion": motion_to_vote.model_dump(),
                    "previous_speeches": [s.model_dump() for s in speeches],
                    "round_num": round_num,
                    "search_context": search_context,  # 注入 Tavily+百炼 搜索结果
                })

                content = speech_result.get("content", "")
                stance = speech_result.get("stance", "clarify")

                # 相似度检查：与上一条发言过于相似则要求重述
                if speeches and _text_similarity(content, speeches[-1].content) > 0.8:
                    logger.info(f"  [{speaker_name}] 发言与上一条过于相似，标记为重述")
                    content = f"[重述] {content}"

                speech = Speech(
                    speaker=speaker_name,
                    round_num=round_num,
                    content=content,
                    stance=stance,
                    references=speech_result.get("references", []),
                )
                speeches.append(speech)
                logger.info(f"  [{speaker_name}] ({stance}): {content[:80]}...")
                # 发言完成，上报进度
                if self.progress_callback:
                    self.progress_callback(
                        f"debate.speaker:R{round_num}:{speaker_name}",
                        "completed",
                        f"第{round_num}轮 {speaker_name} 发言完成 · {stance}",
                        content,
                    )

            except Exception as e:
                logger.warning(f"  [{speaker_name}] 发言失败: {e}")
                speeches.append(Speech(
                    speaker=speaker_name,
                    round_num=round_num,
                    content=f"[发言失败: {e}]",
                    stance="clarify",
                ))
                # 发言失败也要更新进度状态，避免永远停在 running
                if self.progress_callback:
                    self.progress_callback(
                        f"debate.speaker:R{round_num}:{speaker_name}",
                        "completed",
                        f"第{round_num}轮 {speaker_name} 发言失败: {e}",
                    )
            finally:
                # 恢复默认温度
                agent.temperature = original_temp

        # 3. 投票表决
        vote_result = self.vote_on_motion(
            motion=motion_to_vote,
            weights=weights,
            debate_summary="; ".join(f"{s.speaker}({s.stance})" for s in speeches),
        )
        self.votes.append(vote_result)
        logger.info(f"  表决 {motion_to_vote.motion_id}: {vote_result.result} "
                    f"(yes={vote_result.weighted_yes:.2f}, no={vote_result.weighted_no:.2f})")

        # 4. 记录本轮
        debate_round = DebateRound(
            round_id=round_num,
            topic=current_topic,
            speeches=speeches,
            speaker_weights=weights,
            speaker_rationale=rationale,
        )
        self.rounds.append(debate_round)
        self._previous_speakers = next_speakers

        return debate_round

    def vote_on_motion(self, motion: Motion, weights: Dict[str, float],
                       debate_summary: str = "") -> VoteResult:
        """
        加权投票

        规则：
        - 加权赞成 ≥ 0.6 → passed
        - 僵持（差值 < threshold）→ Speaker 裁定
        - 否则 → rejected，记录少数派意见

        Args:
            motion: 待表决动议
            weights: 投票权重
            debate_summary: 辩论摘要

        Returns:
            VoteResult
        """
        votes: Dict[str, str] = {}
        vote_reasons: Dict[str, str] = {}

        # 每个 Agent 独立投票
        for agent_name, agent in self.agents.items():
            try:
                vote_result = agent.run({
                    "task_type": "vote",
                    "current_motion": motion.model_dump(),
                    "debate_summary": debate_summary,
                })
                vote_val = vote_result.get("vote", "abstain").lower().strip()
                if vote_val not in ("yes", "no", "abstain"):
                    vote_val = "abstain"
                votes[agent_name] = vote_val
                vote_reasons[agent_name] = vote_result.get("reason", "")
            except Exception as e:
                logger.warning(f"  [{agent_name}] 投票失败: {e}")
                votes[agent_name] = "abstain"
                vote_reasons[agent_name] = f"投票异常: {e}"

        # 计算加权票
        weighted_yes = sum(weights.get(name, 0.1) for name, v in votes.items() if v == "yes")
        weighted_no = sum(weights.get(name, 0.1) for name, v in votes.items() if v == "no")

        # 修复2: 先记录少数派意见（只要有 no 票就记录，不论结果）
        diff = weighted_yes - weighted_no
        minority_opinions_list: List[str] = []
        speaker_ruling = ""

        # 记录所有反对票为少数派意见
        for name, v in votes.items():
            if v == "no":
                reason = vote_reasons.get(name, "未说明理由")
                minority_opinions_list.append(f"{name}: {reason}")
                self.minority_opinions.append(MinorityOpinion(
                    agent=name,
                    motion_id=motion.motion_id,
                    objection=reason,
                    alternative_proposal="",
                    why_overruled="",  # 待结果判定后填充
                ))

        # 判定结果（门槛 0.65）
        if abs(diff) < self.deadlock_threshold:
            # 僵持 → Speaker 裁定
            ruling = self.speaker.rule_deadlock(
                motion=motion.model_dump(),
                votes=votes,
                weighted_yes=weighted_yes,
                weighted_no=weighted_no,
                debate_summary=debate_summary,
            )
            result = ruling.get("ruling", "amended")
            speaker_ruling = ruling.get("ruling_rationale", "")
            logger.info(f"  [议长裁定] {result}: {speaker_ruling[:100]}")
        elif weighted_yes >= PARLIAMENT_PASS_THRESHOLD:
            result = "passed"
        elif weighted_yes > weighted_no:
            result = "passed"
        else:
            result = "rejected"

        # 回填少数派意见的 why_overruled
        if result in ("passed", "amended"):
            for mo in self.minority_opinions:
                if mo.motion_id == motion.motion_id and not mo.why_overruled:
                    mo.why_overruled = speaker_ruling if speaker_ruling else "多数票决"
        elif result == "rejected":
            # 动议被否决，少数派是投 yes 的
            for name, v in votes.items():
                if v == "yes":
                    reason = vote_reasons.get(name, "未说明理由")
                    minority_opinions_list.append(f"{name}: {reason}")
                    self.minority_opinions.append(MinorityOpinion(
                        agent=name,
                        motion_id=motion.motion_id,
                        objection=reason,
                        alternative_proposal="",
                        why_overruled="动议被多数否决",
                    ))

        return VoteResult(
            motion_id=motion.motion_id,
            votes=votes,
            weighted_yes=weighted_yes,
            weighted_no=weighted_no,
            result=result,
            minority_opinions=minority_opinions_list,
            speaker_ruling=speaker_ruling,
        )

    def close_parliament(self, final_strategies: Dict = None) -> DeliberationTranscript:
        """
        闭幕：生成完整辩论记录

        Args:
            final_strategies: 最终策略推荐

        Returns:
            DeliberationTranscript
        """
        logger.info("\n[议会闭幕]")

        # Speaker 闭幕总结
        closing = self.speaker.close_parliament(
            topic=self.topic,
            motions=[m.model_dump() for m in self.motions],
            votes=[v.model_dump() for v in self.votes],
            minority_opinions=[m.model_dump() for m in self.minority_opinions],
            total_rounds=len(self.rounds),
        )

        transcript = DeliberationTranscript(
            topic=self.topic,
            total_rounds=len(self.rounds),
            rounds=self.rounds,
            motions=self.motions,
            votes=self.votes,
            minority_opinions=self.minority_opinions,
            final_strategies=final_strategies or closing,
            started_at=self.started_at,
            completed_at=datetime.now().isoformat(),
        )

        logger.info(f"  总轮次: {transcript.total_rounds}")
        logger.info(f"  动议数: {len(transcript.motions)}")
        logger.info(f"  投票数: {len(transcript.votes)}")
        logger.info(f"  少数派意见: {len(transcript.minority_opinions)}")

        return transcript

    def should_close(self) -> bool:
        """判断是否应该闭幕"""
        # 达到最大轮次
        if len(self.rounds) >= self.max_rounds:
            return True
        # 所有动议已表决
        pending = [
            m for m in self.motions
            if not any(v.motion_id == m.motion_id and v.result in ("passed", "rejected")
                       for v in self.votes)
        ]
        if not pending:
            return True
        # 连续2轮无提升
        if self._consecutive_no_improvement >= 2:
            return True
        return False


if __name__ == "__main__":
    print("DebateEngine 模块加载成功")
    print(f"  最大轮次: {PARLIAMENT_MAX_ROUNDS}")
    print(f"  僵持阈值: {PARLIAMENT_DEADLOCK_THRESHOLD}")
