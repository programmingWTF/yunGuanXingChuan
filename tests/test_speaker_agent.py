"""
云观星传 - 议长 SpeakerAgent 单元测试
覆盖 prompt 路由、辩论规划、僵持裁定、闭幕总结、异常降级与回退模板
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def speaker():
    """创建带 mock LLM 的 SpeakerAgent"""
    with patch('src.llm_client.OpenAI'), \
         patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.parliament.speaker import SpeakerAgent
        agent = SpeakerAgent(llm_client=mock_client)
        agent.llm_client = mock_client
        return agent


class TestSystemPrompt:
    """系统提示词测试"""

    def test_has_system_prompt(self, speaker):
        from src.parliament.speaker import SPEAKER_SYSTEM_PROMPT
        assert speaker._get_default_prompt() == SPEAKER_SYSTEM_PROMPT
        assert len(SPEAKER_SYSTEM_PROMPT) > 100  # 不应为空壳

    def test_prompt_file_empty_uses_default(self, speaker):
        """prompt_file 为空串时 _load_prompt 走内置默认"""
        from src.parliament.speaker import SPEAKER_SYSTEM_PROMPT
        assert speaker.prompt_file == ""
        assert speaker.system_prompt == SPEAKER_SYSTEM_PROMPT


class TestPromptRouting:
    """_build_user_prompt 路由测试"""

    def test_default_is_plan_round(self, speaker):
        """无 task 默认 plan_round"""
        prompt = speaker._build_user_prompt({"topic": "嫦娥六号", "round_num": 1, "motions": []})
        assert "规划第 1 轮辩论" in prompt

    def test_plan_round_route(self, speaker):
        prompt = speaker._build_user_prompt({
            "task": "plan_round", "topic": "天问三号", "round_num": 2, "motions": [{"motion_id": "M1"}]})
        assert "规划第 2 轮辩论" in prompt
        assert "天问三号" in prompt
        assert "M1" in prompt

    def test_rule_deadlock_route(self, speaker):
        prompt = speaker._build_user_prompt({
            "task": "rule_deadlock", "motion": {"motion_id": "M2"},
            "weighted_yes": 0.5, "weighted_no": 0.5, "votes": {"scientist": "yes"}})
        assert "僵持" in prompt
        assert "加权赞成: 0.500" in prompt

    def test_closing_route(self, speaker):
        prompt = speaker._build_user_prompt({
            "task": "closing", "topic": "嫦娥六号", "motions": [],
            "votes": [], "total_rounds": 3})
        assert "闭幕总结" in prompt
        assert "共 3 轮" in prompt

    def test_unknown_task_dumps_input(self, speaker):
        prompt = speaker._build_user_prompt({"task": "other", "topic": "x"})
        # 未知任务原样 JSON 序列化
        assert json.loads(prompt)["topic"] == "x"


class TestPlanRoundPromptContent:
    """辩论规划 prompt 内容测试"""

    def test_plan_round_contains_weights_contract(self, speaker):
        prompt = speaker._build_plan_round_prompt({
            "topic": "嫦娥六号", "round_num": 1, "motions": [],
            "previous_speakers": ["scientist"], "debate_history": [], "motion_results": []})
        assert "speaker_weights" in prompt
        assert "五项之和必须为 1.0" in prompt
        assert "next_speakers" in prompt
        # 首轮应显示"尚无表决"占位
        assert "尚无表决" in prompt

    def test_debate_history_formatted(self, speaker):
        prompt = speaker._build_plan_round_prompt({
            "topic": "T", "round_num": 2,
            "motions": [], "previous_speakers": [],
            "debate_history": [{"round_id": 1, "topic": "嫦娥六号",
                                "speeches": [{"speaker": "scientist", "stance": "yes"}]}],
            "motion_results": [{"motion_id": "M1", "result": "passed", "weighted_yes": 0.8}]})
        assert "第1轮" in prompt
        assert "scientist(yes)" in prompt
        assert "M1: passed (yes=0.80)" in prompt


class TestDeadlockAndClosingPrompt:
    """僵持与闭幕 prompt 测试"""

    def test_deadlock_prompt_contains_ruling_format(self, speaker):
        prompt = speaker._build_deadlock_prompt({
            "motion": {"motion_id": "M1", "content": "应发布联合声明"},
            "votes": {"scientist": "yes", "skeptic": "no"},
            "weighted_yes": 0.48, "weighted_no": 0.52, "debate_summary": "僵持中"})
        assert '"ruling"' in prompt
        assert '"passed/rejected/amended"' in prompt
        assert "应发布联合声明" in prompt

    def test_closing_prompt_contains_summary_request(self, speaker):
        prompt = speaker._build_closing_prompt({
            "topic": "嫦娥六号", "motions": [{"motion_id": "M1"}],
            "votes": [], "minority_opinions": [], "total_rounds": 5})
        assert "嫦娥六号" in prompt
        assert "共 5 轮" in prompt


class TestPlanRoundLogic:
    """plan_round 决策逻辑测试"""

    def test_success_keeps_valid_weights(self, speaker):
        """run 返回合法权重时应保留 LLM 结果"""
        with patch.object(speaker, 'run', return_value={
            "phase": "debate", "round_num": 1,
            "speaker_weights": {"scientist": 0.4, "skeptic": 0.3, "humanist": 0.3},
            "weight_rationale": "均衡",
        }):
            result = speaker.plan_round("嫦娥六号", 1, [], [], [], [])
        assert result["speaker_weights"]["scientist"] == 0.4
        assert result["weight_rationale"] == "均衡"

    def test_invalid_weights_fallback_to_template(self, speaker):
        """权重非法（和不等于1）应回退事实模板"""
        with patch.object(speaker, 'run', return_value={
            "speaker_weights": {"scientist": 0.9, "skeptic": 0.9},  # 和=1.8
            "weight_rationale": "异常",
        }):
            result = speaker.plan_round("嫦娥六号", 1, [], [], [], [])
        total = sum(result["speaker_weights"].values())
        assert abs(total - 1.0) < 0.001
        assert "回退" in result["weight_rationale"]

    def test_empty_weights_fallback(self, speaker):
        """空权重应回退模板"""
        with patch.object(speaker, 'run', return_value={"speaker_weights": {}}):
            result = speaker.plan_round("嫦娥六号", 1, [], [], [], [])
        assert abs(sum(result["speaker_weights"].values()) - 1.0) < 0.001

    def test_exception_falls_back(self, speaker):
        """LLM 异常应使用 _fallback_plan"""
        from src.parliament.speaker import SpeakerAgent
        with patch.object(speaker, 'run', side_effect=RuntimeError("LLM down")):
            result = speaker.plan_round("嫦娥六号", 1, [{"motion_id": "M1"}], [], [], [])
        assert result["phase"] == "debate"
        assert result["motion_to_vote"] == "M1"
        assert "回退方案" in result["weight_rationale"]


class TestFallbackPlan:
    """回退规划测试"""

    def test_round_rotation_uses_different_templates(self, speaker):
        """不同轮次应轮换模板（speaker 组合不同）"""
        from src.parliament.speaker import SpeakerAgent
        p1 = speaker._fallback_plan(1, [{"motion_id": "M1"}])  # fact → scientist, skeptic
        p2 = speaker._fallback_plan(2, [{"motion_id": "M1"}])  # culture → humanist, strategist
        assert p1["next_speakers"] == ["scientist", "skeptic"]
        assert p2["next_speakers"] == ["humanist", "strategist"]

    def test_empty_motions_default_id(self, speaker):
        p = speaker._fallback_plan(1, [])
        assert p["motion_to_vote"] == "M001"

    def test_weights_sum_to_one(self, speaker):
        for r in range(1, 5):
            p = speaker._fallback_plan(r, [{"motion_id": "M"}])
            assert abs(sum(p["speaker_weights"].values()) - 1.0) < 0.001


class TestDeadlockRuling:
    """僵持裁定测试"""

    def test_success_returns_ruling(self, speaker):
        with patch.object(speaker, 'run', return_value={
            "ruling": "passed", "ruling_rationale": "补强证据后通过",
            "conditions": [], "minority_acknowledgment": ""}):
            result = speaker.rule_deadlock({"motion_id": "M1"}, {}, 0.5, 0.5, "")
        assert result["ruling"] == "passed"

    def test_exception_defaults_amended(self, speaker):
        """LLM 异常时僵持应默认附条件通过"""
        with patch.object(speaker, 'run', side_effect=RuntimeError("down")):
            result = speaker.rule_deadlock({"motion_id": "M1"}, {"a": "yes"}, 0.5, 0.5, "僵持")
        assert result["ruling"] == "amended"
        assert len(result["conditions"]) >= 1


class TestClosingParliament:
    """闭幕总结测试"""

    def test_success_returns_summary(self, speaker):
        with patch.object(speaker, 'run', return_value={
            "phase": "closing", "summary": "议会顺利结束",
            "passed_motions": ["M1"], "key_insights": []}):
            result = speaker.close_parliament("嫦娥六号", [], [], [], 3)
        assert result["summary"] == "议会顺利结束"

    def test_exception_defaults_fallback_summary(self, speaker):
        """LLM 异常时应基于投票结果生成降级总结"""
        votes = [
            {"motion_id": "M1", "result": "passed"},
            {"motion_id": "M2", "result": "rejected"},
        ]
        with patch.object(speaker, 'run', side_effect=RuntimeError("down")):
            result = speaker.close_parliament("嫦娥六号", [], votes, [], 3)
        assert "3 轮辩论" in result["summary"]
        assert result["passed_motions"] == ["M1"]
        assert result["rejected_motions"] == ["M2"]


class TestAgentInfo:
    """agent_info 测试"""

    def test_get_agent_info(self, speaker):
        info = speaker.get_agent_info()
        assert info["name"] == "speaker"
        assert "议长" in info["description"]
