"""
云观星传 - 工作流引擎自动迭代闭环单元测试
覆盖规则诊断（_diagnose）、LLM 诊断及降级、指标提取、建议生成、
增量补丁合并、按问题路由修订与 auto_iterate 集成主链路
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from src.schemas import IterationRecord, StageStatus
from src.workflow.stages import WorkflowStage
from src.workflow.project import ProjectStore
from src.workflow.engine import WorkflowEngine


def make_mock_agent(output: dict):
    """构造返回固定输出的 mock Agent"""
    agent = MagicMock()
    agent.run.return_value = output
    return agent


@pytest.fixture
def store(tmp_path):
    return ProjectStore(base_dir=tmp_path / "projects")


@pytest.fixture
def engine(store, tmp_path):
    """带 mock Agent 的引擎（不触发 LLM / 搜索 / 向量库 / KG）"""
    agents = {
        WorkflowStage.INSPIRATION: make_mock_agent({"topic": "t", "directions": [{"title": "方向A", "research_value": 90}]}),
        WorkflowStage.LITERATURE: make_mock_agent({"topic": "t", "sections": [], "research_gap": {}}),
        WorkflowStage.DESIGN: make_mock_agent({"topic": "t", "research_questions": []}),
        WorkflowStage.METHOD: make_mock_agent({"topic": "t", "methods": []}),
        WorkflowStage.DATA_ANALYSIS: make_mock_agent({"topic": "t", "findings": ["发现1", "发现2", "发现3"]}),
        WorkflowStage.WRITING: make_mock_agent({"topic": "t", "sections": []}),
        WorkflowStage.REVIEW: make_mock_agent({"topic": "t", "reviewers": []}),
    }
    with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError("no net")), \
         patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError("no vs")), \
         patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError("no kg")):
        eng = WorkflowEngine(store=store, agents=agents)
        yield eng


def _verify_summary(total=10, verified=9, partial=1, avg_conf=0.8):
    """构造校验报告 summary"""
    return {"total": total, "verified": verified, "partial": partial,
            "unverified": total - verified - partial, "avg_confidence": avg_conf}


def _output(verify=None, coding=None, findings=None, sentiment=None):
    """构造数据分析产出物"""
    out = {}
    if verify is not None:
        out["verification"] = {"summary": verify}
    if coding is not None:
        out["coding_table"] = coding
    if findings is not None:
        out["findings"] = findings
    if sentiment is not None:
        out["sentiment"] = sentiment
    return out


class TestDiagnose:
    """规则式三层诊断测试"""

    def test_high_quality_conclusion(self, engine):
        """高覆盖率+高置信+足量发现 → 可进入写作"""
        out = _output(verify=_verify_summary(), coding=["a"] * 6,
                      findings=["f1", "f2", "f3"], sentiment={"positive": 3})
        conclusion, confidence, problems = engine._diagnose(out)
        assert confidence >= 0.85
        assert "进入写作" in conclusion
        assert problems == []

    def test_low_coverage_problem_routes_to_design(self, engine):
        """低覆盖率问题应路由到研究设计（stage 3）"""
        out = _output(verify=_verify_summary(verified=3, partial=1, total=10),
                      coding=["a"] * 6, findings=["f1", "f2", "f3"], sentiment={})
        _, confidence, problems = engine._diagnose(out)
        assert any(p["target_stage"] == 3 and "覆盖率" in p["text"] for p in problems)
        assert confidence < 0.7

    def test_low_confidence_problem_routes_to_literature(self, engine):
        """低置信度问题应路由到文献综述（stage 2）"""
        out = _output(verify=_verify_summary(avg_conf=0.4),
                      coding=["a"] * 6, findings=["f1", "f2", "f3"], sentiment={})
        _, _, problems = engine._diagnose(out)
        assert any(p["target_stage"] == 2 and "置信度" in p["text"] for p in problems)

    def test_coarse_coding_problem(self, engine):
        """编码类目过少应提示颗粒度"""
        out = _output(verify=_verify_summary(), coding=["a", "b"],
                      findings=["f1", "f2", "f3"], sentiment={})
        _, _, problems = engine._diagnose(out)
        assert any("编码类目仅 2 个" in p["text"] for p in problems)

    def test_missing_sentiment_problem(self, engine):
        out = _output(verify=_verify_summary(), coding=["a"] * 6,
                      findings=["f1", "f2", "f3"])
        _, _, problems = engine._diagnose(out)
        assert any("情绪" in p["text"] for p in problems)

    def test_no_verification_report(self, engine):
        """无校验报告时保守给 0 分并提示"""
        out = _output(coding=["a"] * 6, findings=["f1", "f2", "f3"], sentiment={})
        conclusion, confidence, problems = engine._diagnose(out)
        assert confidence == 0.0
        assert any("未附校验报告" in p["text"] for p in problems)
        assert "可靠性不足" in conclusion

    def test_medium_confidence_conclusion(self, engine):
        """0.7≤conf<0.85 → 部分支持"""
        out = _output(verify=_verify_summary(verified=6, partial=2, total=10, avg_conf=0.7),
                      coding=["a"] * 6, findings=["f1", "f2", "f3"], sentiment={})
        conclusion, confidence, _ = engine._diagnose(out)
        # coverage=0.8 avg=0.7 → conf=0.75
        assert 0.7 <= confidence < 0.85
        assert "部分支持" in conclusion


class TestLLMDiagnose:
    """LLM 方法学诊断测试"""

    def _make_engine(self):
        """构造仅需 store 的引擎（复用 engine fixture 简化：直接构建新实例）"""
        from src.workflow.project import ProjectStore
        return WorkflowEngine(store=ProjectStore(base_dir=Path("/tmp/__never__")))

    def test_no_llm_config_falls_back_to_rules(self, engine):
        """无用户 LLM 配置应降级规则诊断"""
        out = _output(verify=_verify_summary(), coding=["a"] * 6,
                      findings=["f1", "f2", "f3"], sentiment={})
        with patch.object(engine, '_diagnose') as mock_rules:
            mock_rules.return_value = ("规则结论", 0.5, [])
            conclusion, confidence, problems = engine._llm_diagnose(None, out, None)
        mock_rules.assert_called_once_with(out)
        assert conclusion == "规则结论"

    def test_llm_success_parses(self, engine, tmp_path):
        """LLM 返回合法 JSON 时应解析并 clamp 置信度"""
        from src.workflow.project import ProjectStore
        eng = WorkflowEngine(store=ProjectStore(base_dir=tmp_path / "p"))
        eng.store = MagicMock()
        project = MagicMock()
        project.stages.get.return_value = None
        project.iterations = []
        project.title, project.interest = "议题", "嫦娥六号"
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "conclusion": "方法适配，但样本代表性不足",
            "confidence": 1.5,  # 越界应 clamp 到 1.0
            "problems": [{"text": "编码类目过粗", "target_stage": 3},
                         {"text": "证据不足", "target_stage": 2},
                         {"text": ""},  # 空 text 应过滤
                         "不是字典"],  # 非 dict 应过滤
        }
        with patch("src.llm_client.get_llm_client", return_value=mock_client):
            conclusion, confidence, problems = eng._llm_diagnose(project, _output(findings=["a"]), {"api_key": "k"})
        assert confidence == 1.0  # clamp
        assert "样本代表性不足" in conclusion
        assert len(problems) == 2
        assert all(p["target_stage"] in (2, 3) for p in problems)

    def test_llm_incomplete_output_falls_back(self, engine, tmp_path):
        """LLM 输出缺 conclusion/confidence=0 应降级"""
        from src.workflow.project import ProjectStore
        eng = WorkflowEngine(store=ProjectStore(base_dir=tmp_path / "p"))
        eng.store = MagicMock()
        project = MagicMock()
        project.stages.get.return_value = None
        project.iterations = []
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {"problems": []}  # 不完整
        with patch("src.llm_client.get_llm_client", return_value=mock_client), \
             patch.object(eng, '_diagnose') as mock_rules:
            mock_rules.return_value = ("规则", 0.3, [{"text": "x", "target_stage": 3}])
            eng._llm_diagnose(project, {}, {"api_key": "k"})
        mock_rules.assert_called_once()

    def test_llm_exception_falls_back(self, engine, tmp_path):
        """LLM 调用异常应降级规则诊断"""
        from src.workflow.project import ProjectStore
        eng = WorkflowEngine(store=ProjectStore(base_dir=tmp_path / "p"))
        eng.store = MagicMock()
        project = MagicMock()
        project.stages.get.return_value = None
        project.iterations = []
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = RuntimeError("LLM down")
        with patch("src.llm_client.get_llm_client", return_value=mock_client), \
             patch.object(eng, '_diagnose') as mock_rules:
            mock_rules.return_value = ("规则", 0.0, [])
            eng._llm_diagnose(project, {}, {"api_key": "k"})
        mock_rules.assert_called_once()


class TestExtractIterationMetrics:
    """迭代指标提取测试"""

    def test_full_metrics(self, engine):
        out = _output(verify=_verify_summary(total=4, verified=2, partial=1, avg_conf=0.75),
                      coding=["a", "b", "c", "d", "e"], findings=["1", "2", "3"],
                      sentiment={"positive": 5, "neutral": 3, "negative": 2})
        m = engine._extract_iteration_metrics(out)
        assert m["证据覆盖率"] == 0.75  # (2+1)/4
        assert m["平均置信度"] == 0.75
        assert m["编码类目数"] == 5
        assert m["研究发现数"] == 3
        assert m["情绪样本量"] == 10

    def test_no_verification(self, engine):
        m = engine._extract_iteration_metrics(_output(findings=["1"]))
        assert "证据覆盖率" not in m
        assert m.get("研究发现数") == 1.0

    def test_sentiment_non_dict_ignored(self, engine):
        out = _output(sentiment="happy")
        assert engine._extract_iteration_metrics(out) == {}


class TestBuildIterationSuggestion:
    """迭代建议生成测试"""

    def test_low_coverage_hint(self, engine):
        out = _output(verify=_verify_summary(verified=1, partial=0, total=10))
        hint = engine._build_iteration_suggestion(out)
        assert "覆盖率仅 10%" in hint

    def test_high_coverage_hint(self, engine):
        out = _output(verify=_verify_summary(verified=9, partial=0, total=10))
        hint = engine._build_iteration_suggestion(out)
        assert "覆盖率高达 90%" in hint

    def test_missing_sentiment_hint(self, engine):
        out = _output(verify=_verify_summary(), coding=["a"] * 6, findings=["f1", "f2", "f3"])
        hint = engine._build_iteration_suggestion(out)
        assert "情绪" in hint

    def test_all_good_hint(self, engine):
        # 覆盖率 70%（不触发低/高分支），其余维度健康 → 质量良好
        out = _output(verify=_verify_summary(verified=6, partial=1, total=10),
                      coding=["a"] * 6, findings=["f1", "f2", "f3"], sentiment={"positive": 1})
        hint = engine._build_iteration_suggestion(out)
        assert "质量良好" in hint


class TestMergeStagePatch:
    """增量补丁合并测试"""

    def test_list_merge_by_key(self, engine):
        """同 key 条目应被 patch 替换，未提及的保留"""
        base = {
            "research_questions": [{"id": "RQ1", "text": "旧RQ1"}, {"id": "RQ2", "text": "旧RQ2"}],
            "sections": [{"heading": "方法", "content": "旧"}],
        }
        patch_data = {"research_questions": [{"id": "RQ2", "text": "新RQ2"}], "topic": "新主题"}
        merged = engine._merge_stage_patch(base, patch_data)
        texts = [q["text"] for q in merged["research_questions"]]
        assert "旧RQ1" in texts   # 未提及保留
        assert "新RQ2" in texts   # patch 替换
        assert merged["research_questions"][0]["id"] == "RQ1"  # 顺序稳定
        assert merged["topic"] == "新主题"

    def test_list_append_new_and_extras(self, engine):
        base = {"sections": [{"heading": "A", "content": "x"}]}
        patch_data = {"sections": [{"heading": "B", "content": "y"}, "纯文本额外项"]}
        merged = engine._merge_stage_patch(base, patch_data)
        headings = [s["heading"] for s in merged["sections"] if isinstance(s, dict)]
        assert headings == ["A", "B"]
        assert "纯文本额外项" in merged["sections"]

    def test_references_dedup(self, engine):
        base = {"references": ["ref1", "ref2"]}
        patch_data = {"references": ["ref2", "ref3"]}
        merged = engine._merge_stage_patch(base, patch_data)
        assert merged["references"] == ["ref1", "ref2", "ref3"]

    def test_scalar_override(self, engine):
        merged = engine._merge_stage_patch({"conclusion": "旧", "gap": "保留"},
                                           {"conclusion": "新"})
        assert merged["conclusion"] == "新"
        assert merged["gap"] == "保留"


class TestReviseStageByProblems:
    """按问题路由修订测试"""

    def test_routes_to_design_and_literature(self, engine):
        """target_stage 3/2 应分别路由修订并返回 touched"""
        it = IterationRecord(iteration=1, problems=[{"text": "编码粗", "target_stage": 3},
                                                    {"text": "证据少", "target_stage": 2}])
        project = MagicMock()
        project.id = "p1"
        with patch.object(engine, '_revise_design_with_llm', return_value={"rq": 1}) as md, \
             patch.object(engine, '_revise_literature_with_llm', return_value={"lit": 1}) as ml, \
             patch.object(engine, '_overwrite_stage_output', return_value=True), \
             patch.object(engine.store, 'bump_design_version') as mbump:
            touched = engine._revise_stage_by_problems(project, it, None)
        assert touched == [2, 3]  # 按 stage 升序
        md.assert_called_once()
        ml.assert_called_once()
        mbump.assert_called_once()  # 仅设计修订触发版本 +1

    def test_failed_revision_skipped(self, engine):
        """单阶段修订失败应跳过不中断"""
        it = IterationRecord(iteration=1, problems=[{"text": "x", "target_stage": 3},
                                                    {"text": "y", "target_stage": 4}])
        project = MagicMock()
        project.id = "p1"
        with patch.object(engine, '_revise_design_with_llm', side_effect=RuntimeError("LLM down")), \
             patch.object(engine, '_revise_method_with_llm', return_value={"m": 1}), \
             patch.object(engine, '_overwrite_stage_output', return_value=True):
            touched = engine._revise_stage_by_problems(project, it, None)
        assert touched == [4]  # stage 3 失败被跳过

    def test_stage5_no_revision_needed(self, engine):
        """target_stage=5 无需修订（数据分析本轮已重跑）"""
        it = IterationRecord(iteration=1, problems=[{"text": "x", "target_stage": 5}])
        project = MagicMock()
        project.id = "p1"
        touched = engine._revise_stage_by_problems(project, it, None)
        assert touched == []


# ---------------------------------------------------------------------------
# auto_iterate 集成（真实 ProjectStore + mock agents）
# ---------------------------------------------------------------------------


def advance_project(engine, interest="朱雀2号火箭"):
    """把项目推进并批准 1~6 阶段（解锁第 7 阶段）"""
    p = engine.create_project(title="迭代项目", interest=interest)
    for s in range(1, 7):
        engine.run_stage(p.id, s, {})
        engine.approve_stage(p.id, s)
    return p


class TestAutoIterate:
    """自动迭代闭环集成测试"""

    def test_first_round_pass_stops(self, engine):
        """首轮可信度达标应立即停止并完成收尾评审"""
        p = advance_project(engine)
        # stage 5 尚未跑过，当前无迭代记录
        with patch.object(engine, '_llm_diagnose', return_value=("质量达标", 0.92, [])), \
             patch.object(engine, '_revise_stage_by_problems', return_value=[]) as mock_revise:
            rounds = engine.auto_iterate(p.id, max_rounds=3, target_confidence=0.85)
        assert len(rounds) == 1
        assert rounds[0]["confidence"] == 0.92
        assert rounds[0]["revised_stages"] == []
        mock_revise.assert_not_called()  # 达标不再修订
        project = engine.store.get(p.id)
        assert project.status == "completed"
        # 收尾评审已跑并确认
        assert project.stages["7"].status == StageStatus.COMPLETED

    def test_iterates_until_confidence_met(self, engine):
        """未达标应连续迭代（修订 → 重跑 → 再诊断）直到达标"""
        p = advance_project(engine)
        diagnoses = [
            ("证据不足", 0.5, [{"text": "编码粗", "target_stage": 3}]),
            ("证据不足", 0.7, [{"text": "编码粗", "target_stage": 3}]),
            ("质量达标", 0.9, []),
        ]
        with patch.object(engine, '_llm_diagnose', side_effect=diagnoses), \
             patch.object(engine, '_revise_stage_by_problems', return_value=[3]):
            rounds = engine.auto_iterate(p.id, max_rounds=5, target_confidence=0.85)
        assert len(rounds) == 3
        assert [r["confidence"] for r in rounds] == [0.5, 0.7, 0.9]
        assert rounds[-1]["revised_stages"] == []  # 末轮达标不修订
        project = engine.store.get(p.id)
        assert project.status == "completed"
        # 迭代记录已按轮次落盘
        assert len(project.iterations) >= 3

    def test_revision_failure_stops_early(self, engine):
        """所有阶段修订失败应提前终止"""
        p = advance_project(engine)
        with patch.object(engine, '_llm_diagnose',
                          return_value=("有缺陷", 0.4, [{"text": "x", "target_stage": 3}])), \
             patch.object(engine, '_revise_stage_by_problems', return_value=[]):
            rounds = engine.auto_iterate(p.id, max_rounds=3, target_confidence=0.85)
        assert len(rounds) == 1  # 无修订成功 → 只跑 1 轮即终止
        assert engine.store.get(p.id).status == "completed"

    def test_stage5_auto_approves_each_round(self, engine):
        """每轮数据分析产出应自动确认（全自动闭环）"""
        p = advance_project(engine)
        with patch.object(engine, '_llm_diagnose',
                          return_value=("好", 0.95, [])):
            engine.auto_iterate(p.id, max_rounds=2, target_confidence=0.85)
        project = engine.store.get(p.id)
        # 数据分析阶段最终为 completed（自动确认），非 awaiting_review
        assert project.stages["5"].status == StageStatus.COMPLETED

    def test_rerun_review_fails_restores_backup(self, engine):
        """收尾重评两次失败应恢复旧评审产出并保持 completed"""
        p = advance_project(engine)
        # 先把评审阶段跑出旧产出（若尚未）
        engine.run_stage(p.id, 7, {})
        engine.approve_stage(p.id, 7)
        old_review = dict(engine.store.get(p.id).stages["7"].output or {})

        def fail_stage7(project_id, stage, *a, **k):
            if stage == 7:
                raise RuntimeError("评审超时")
            return engine.store.get(project_id)

        with patch.object(engine, '_llm_diagnose', return_value=("好", 0.95, [])), \
             patch.object(engine, 'run_stage', side_effect=fail_stage7):
            rounds = engine.auto_iterate(p.id, max_rounds=2, target_confidence=0.85)
        project = engine.store.get(p.id)
        assert project.status == "completed"
        # 旧评审产出被恢复（未丢失）
        assert project.stages["7"].output == old_review
        assert len(rounds) >= 1


class TestReviseWithLLM:
    """各阶段 LLM 修订函数测试（mock LLM 客户端）"""

    def _project_with_stage(self, stage, output):
        """构造含指定阶段产物的项目 mock"""
        project = MagicMock()
        project.title = "测试研究"
        record = MagicMock()
        record.output = output
        project.stages.get.return_value = record
        return project

    def _iter(self, target_stage=2, text="问题描述"):
        return IterationRecord(iteration=1, problems=[{"text": text, "target_stage": target_stage}])

    @pytest.mark.parametrize("func_name,stage,output_key,problem_stage", [
        ("_revise_literature_with_llm", "2", "sections", 2),
        ("_revise_method_with_llm", "4", "methods", 4),
        ("_revise_writing_with_llm", "6", "sections", 6),
    ])
    def test_revise_success(self, func_name, stage, output_key, problem_stage, tmp_path):
        """LLM 返回有效数据时应返回增量补丁"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        output = {output_key: [{("theme" if output_key == "sections" else "name"): "原条目",
                                "content": "x", "method_type": "qualitative"}]}
        project = self._project_with_stage(stage, output)
        it = self._iter(problem_stage)
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            output_key: [{("theme" if output_key == "sections" else "name"): "新条目",
                          "content": "新内容"}],
            "revision_note": "按诊断修订",
        }
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            result = getattr(eng, func_name)(project, it, {"api_key": "k"})
        assert result is not None
        assert result[output_key]
        assert "revision_note" in result

    @pytest.mark.parametrize("func_name,stage", [
        ("_revise_literature_with_llm", "2"),
        ("_revise_method_with_llm", "4"),
        ("_revise_writing_with_llm", "6"),
    ])
    def test_revise_no_client_returns_none(self, func_name, stage, tmp_path):
        """无 LLM 配置应返回 None 不调用"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._project_with_stage(stage, {"sections": [{"theme": "A"}]})
        it = self._iter()
        with patch('src.llm_client.get_llm_client') as mock_get:
            result = getattr(eng, func_name)(project, it, None)
        assert result is None
        mock_get.assert_not_called()

    @pytest.mark.parametrize("func_name,stage,problem_stage", [
        ("_revise_literature_with_llm", "2", 3),  # 问题不指向文献
        ("_revise_method_with_llm", "4", 2),      # 问题不指向方法
    ])
    def test_revise_unrelated_problem_returns_none(self, func_name, stage, problem_stage, tmp_path):
        """诊断问题与阶段无关时应返回 None"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._project_with_stage(stage, {"sections": [{"theme": "A"}], "methods": [{"name": "M"}]})
        it = self._iter(problem_stage)
        mock_client = MagicMock()
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            result = getattr(eng, func_name)(project, it, {"api_key": "k"})
        assert result is None
        mock_client.chat_json.assert_not_called()

    def test_revise_empty_output_returns_none(self, tmp_path):
        """无前置产出应返回 None"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._project_with_stage("2", {})  # 无 sections
        it = self._iter(2)
        with patch('src.llm_client.get_llm_client') as mock_get:
            assert eng._revise_literature_with_llm(project, it, {"api_key": "k"}) is None
        mock_get.return_value.chat_json.assert_not_called()

    def test_revise_llm_exception_returns_none(self, tmp_path):
        """LLM 调用异常应降级 None"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._project_with_stage("2", {"sections": [{"theme": "A", "content": "x"}]})
        it = self._iter(2)
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = RuntimeError("LLM down")
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert eng._revise_literature_with_llm(project, it, {"api_key": "k"}) is None

    def test_revise_empty_result_returns_none(self, tmp_path):
        """LLM 返回空列表应返回 None"""
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._project_with_stage("2", {"sections": [{"theme": "A", "content": "x"}]})
        it = self._iter(2)
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {"sections": []}
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert eng._revise_literature_with_llm(project, it, {"api_key": "k"}) is None


class TestReviseDesignWithLLM:
    """研究设计 LLM 修订测试"""

    def _proj(self, rq="default"):
        project = MagicMock()
        project.title, project.interest = "题目", "议题"
        rec = MagicMock()
        rec.output = {
            "research_questions": rq if rq != "default" else [{"id": "RQ1", "text": "旧问题"}],
            "hypotheses": [{"id": "H1", "statement": "旧假设"}]}
        project.stages.get.return_value = rec
        return project

    def test_success_returns_patch(self, tmp_path):
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        it = IterationRecord(iteration=1, problems=[{"text": "细化RQ", "target_stage": 3}])
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "research_questions": [{"id": "RQ1", "text": "新问题"}],
            "hypotheses": [{"id": "H2", "statement": "新增假设", "hypothesis_type": "quantitative"}],
        }
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            patch_out = eng._revise_design_with_llm(self._proj(), it, {"api_key": "k"})
        assert patch_out["research_questions"][0]["text"] == "新问题"
        assert patch_out["hypotheses"][0]["id"] == "H2"

    def test_no_client_returns_none(self):
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        assert eng._revise_design_with_llm(self._proj(), IterationRecord(iteration=1), None) is None

    def test_no_rq_returns_none(self, tmp_path):
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        project = self._proj(rq=[])
        mock_client = MagicMock()
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert eng._revise_design_with_llm(project, IterationRecord(iteration=1), {"k": 1}) is None
        mock_client.chat_json.assert_not_called()

    def test_empty_result_returns_none(self, tmp_path):
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {"research_questions": []}
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert eng._revise_design_with_llm(self._proj(), IterationRecord(iteration=1), {"k": 1}) is None

    def test_exception_returns_none(self, tmp_path):
        from src.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(store=MagicMock())
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = RuntimeError("down")
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert eng._revise_design_with_llm(self._proj(), IterationRecord(iteration=1), {"k": 1}) is None


class TestRunStageEdgeCases:
    """run_stage 边界与降级测试"""

    def test_stage_locked_raises(self, engine):
        """未解锁阶段应拒绝"""
        p = engine.create_project(interest="朱雀2号火箭")
        with pytest.raises(ValueError, match="未解锁"):
            engine.run_stage(p.id, 3, {})  # 当前在阶段 1

    def test_invalid_stage_raises(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        with pytest.raises(ValueError, match="非法阶段"):
            engine.run_stage(p.id, 9, {})

    def test_project_missing_raises(self, engine):
        with pytest.raises(ValueError, match="不存在"):
            engine.run_stage("proj_不存在", 1, {})

    def test_agent_failure_marks_failed(self, engine):
        """智能体异常时应标记 FAILED 并抛出"""
        p = engine.create_project(interest="朱雀2号火箭")
        failing = make_mock_agent({"topic": "t"})
        failing.run.side_effect = RuntimeError("LLM 崩了")
        engine._agents[WorkflowStage.INSPIRATION] = failing
        with pytest.raises(RuntimeError):
            engine.run_stage(p.id, 1, {})
        project = engine.store.get(p.id)
        assert project.stages["1"].status.value == "failed"

    def test_science_data_autogen_success(self, engine, tmp_path, monkeypatch):
        """本地无语料时应自动生成并入库（全链路 mock，成功后清理文件）"""
        from src.pipeline import _safe_name
        topic = "coverage临时议题XYZ"
        loader = MagicMock()
        loader.load_science_facts.return_value = []
        vs = MagicMock()
        vs.index = MagicMock()
        vs.documents = []
        kg = MagicMock()
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "topic": topic, "key_facts": ["事实1"], "entities": [],
            "relations": [], "timeline": [], "data_sources": []}
        with patch('src.knowledge.data_loader.get_data_loader', return_value=loader), \
             patch('src.llm_client.get_llm_client', return_value=mock_client), \
             patch('src.knowledge.vector_store.get_vector_store', return_value=vs), \
             patch('src.knowledge.kg_builder.get_knowledge_graph', return_value=kg):
            p = engine.create_project(title="t", interest=topic)
            record = engine.run_stage(p.id, 1, {})
        assert record.status == StageStatus.AWAITING_REVIEW
        # 清理生成的文件
        f = Path(__file__).parent.parent / "data" / "science" / f"{_safe_name(topic)}_facts.json"
        if f.exists():
            f.unlink()

    def test_science_data_autogen_degrades(self, engine, monkeypatch, tmp_path):
        """自动生成失败（外部服务不可达）不应影响阶段主流程"""
        loader = MagicMock()
        loader.load_science_facts.return_value = []
        with patch('src.knowledge.data_loader.get_data_loader', return_value=loader), \
             patch('src.llm_client.get_llm_client', side_effect=RuntimeError("LLM down")):
            p = engine.create_project(title="t", interest="coverage降级议题XYZ")
            record = engine.run_stage(p.id, 1, {})
        assert record.status == StageStatus.AWAITING_REVIEW  # 降级成功


class TestExportProjectExtra:
    """导出与多租户细节测试"""

    def test_export_all_formats(self, engine):
        """md/json/word/pdf 均应返回内容"""
        p = engine.create_project(title="导出测试", interest="嫦娥六号")
        engine.run_stage(p.id, 1, {})
        engine.approve_stage(p.id, 1)
        for fmt in ("md", "json"):
            r = engine.export_project(p.id, fmt)
            assert r["format"] == fmt
            assert len(r["content"]) > 0
        for fmt in ("word", "pdf"):
            r = engine.export_project(p.id, fmt)
            assert r["format"] == fmt
            assert len(r["content_bytes"]) > 0

    def test_export_unknown_project_raises(self, engine):
        with pytest.raises(ValueError, match="不存在"):
            engine.export_project("proj_no", "md")

    def test_export_unknown_format_falls_back_md(self, engine):
        """未知 fmt 回退 markdown 渲染"""
        p = engine.create_project(title="t", interest="议题")
        r = engine.export_project(p.id, "not_a_fmt")
        assert r["format"] == "not_a_fmt"
        assert "# t" in r["content"]

    def test_to_markdown_structure(self, engine):
        """Markdown 渲染包含标题/阶段/产出"""
        p = engine.create_project(title="结构测试", interest="议题")
        engine.run_stage(p.id, 1, {})
        project = engine.store.get(p.id)
        data = {
            "id": project.id, "title": project.title, "interest": project.interest,
            "current_stage": project.current_stage, "status": project.status,
            "created_at": project.created_at, "updated_at": project.updated_at,
            "stages": [{"stage": s, "name": n, "icon": "🔬", "status": "completed",
                        "output": {"topic": "嫦娥六号", "key": "值"}}
                       for s, n in [(1, "选题孵化"), (2, "文献综述")]],
            "history": [],
        }
        md = engine._to_markdown(data)
        assert "# 结构测试" in md
        assert "选题孵化" in md
        assert "嫦娥六号" in md  # 产出物 JSON 内嵌
        assert "```json" in md

    def test_get_agent_rebuilds_for_other_tenant(self, engine):
        """不同用户 client 触发时 agent 应整体重建（防串号）"""
        # fixture 预填了 agents；先模拟缓存已绑定用户 A 的 client
        engine._agents_client = "client-A"
        a1 = engine._get_agent(1, llm_client="client-A")
        assert a1 is engine._agents[1]  # 同 client 复用
        a2 = engine._get_agent(1, llm_client="client-B")
        assert a2 is not a1  # 不同 client → 整体重建
        assert engine._agents_client == "client-B"

    def test_save_design_without_stage3_raises(self, engine):
        p = engine.create_project(title="t", interest="议题")
        with pytest.raises(ValueError, match="尚无产出物"):
            engine.save_design(p.id, [{"id": "RQ1", "text": "x"}], [])

    def test_get_stage_result_none(self, engine):
        p = engine.create_project(title="t", interest="议题")
        assert engine.get_stage_result(p.id, 1) is None  # 未运行


class TestRunWithTimeout:
    """限时执行工具测试"""

    def test_returns_result(self, engine):
        assert engine._run_with_timeout(lambda: 42, 2.0, -1, "t") == 42

    def test_timeout_returns_default(self, engine):
        import time
        result = engine._run_with_timeout(lambda: time.sleep(3) or "late", 0.1, "DEFAULT", "慢任务")
        assert result == "DEFAULT"

    def test_exception_swallowed(self, engine):
        def boom():
            raise RuntimeError("x")
        assert engine._run_with_timeout(boom, 1.0, "FALLBACK", "任务", swallow_exc=True) == "FALLBACK"

    def test_exception_raised(self, engine):
        def boom():
            raise RuntimeError("x")
        with pytest.raises(RuntimeError):
            engine._run_with_timeout(boom, 1.0, None, "任务", swallow_exc=False)


class TestStageContextAndKeywords:
    """阶段上下文与关键词提取测试"""

    def test_keywords_from_direction_and_rqs(self, engine):
        inputs = {"direction": "国际传播研究", "research_questions": [{"text": "东盟如何报道"}],
                  "research_questions_extra": []}
        kws = engine._extract_keywords(inputs)
        assert "国际传播研究" in kws
        assert any("东盟" in k for k in kws)
        assert len(kws) <= 5

    def test_stage_search_query_different_by_stage(self, engine):
        """不同阶段查询词应有差异（Issue #98）"""
        inputs = {"topic": "嫦娥六号", "direction": "叙事框架"}
        q1 = engine._stage_search_query(1, inputs)
        q3 = engine._stage_search_query(3, inputs)
        assert q1 and q3
        assert "嫦娥六号" in q1

    def test_build_context_degrades_gracefully(self, engine):
        """外部服务不可用时上下文应降级为空结构"""
        p = engine.create_project(title="t", interest="嫦娥六号")
        ctx = engine._build_stage_context(WorkflowStage.LITERATURE, {"topic": "嫦娥六号"})
        assert ctx.get("search_context") == []
        assert ctx.get("knowledge_hits") == []
        # INSPIRATION 阶段应有 kg_entities 键
        ctx2 = engine._build_stage_context(WorkflowStage.INSPIRATION, {"topic": "嫦娥六号"})
        assert ctx2.get("kg_entities") == []

    def test_inject_previous_outputs(self, engine):
        """前序已完成阶段产出应注入下游输入"""
        p = engine.create_project(title="t", interest="朱雀2号火箭")
        for s in (1, 2):
            engine.run_stage(p.id, s, {})
            engine.approve_stage(p.id, s)
        project = engine.store.get(p.id)
        inputs = {"topic": "朱雀2号火箭"}
        engine._inject_previous_outputs(project, 3, inputs)
        assert "inspiration_result" in inputs
        assert "literature_review" in inputs
        # 用户显式传入的 key 不被覆盖
        inputs2 = {"topic": "t", "inspiration_result": "自定义"}
        engine._inject_previous_outputs(project, 3, inputs2)
        assert inputs2["inspiration_result"] == "自定义"


class TestExtractClaims:
    """阶段断言抽取测试"""

    def test_non_dict_output(self, engine):
        assert engine._extract_claims(WorkflowStage.DATA_ANALYSIS, "not-dict") == []

    def test_data_analysis_findings(self, engine):
        out = {"findings": [
            {"finding": "媒体以合作框架为主呈现嫦娥六号任务（较客观）"},
            {"finding": "短"},  # 长度不足跳过
            {"finding": "存在过度推断需要留意"},
        ]}
        claims = engine._extract_claims(WorkflowStage.DATA_ANALYSIS, out)
        assert len(claims) == 2
        assert all(len(c) > 8 for c in claims)

    def test_subjective_phrases_filtered(self, engine):
        """主观评价性措辞不应作为事实断言"""
        out = {"findings": [{"finding": "本研究具有重要意义且值得关注，需进一步验证模型适配"}]}
        claims = engine._extract_claims(WorkflowStage.DATA_ANALYSIS, out)
        assert claims == []

    def test_design_checks_hypotheses_only(self, engine):
        out = {"research_questions": [{"text": "这是一个研究问题无需校验" * 2}],
               "hypotheses": [{"statement": "假设成立需验证的断言内容较长"}]}
        claims = engine._extract_claims(WorkflowStage.DESIGN, out)
        assert len(claims) == 1  # 只抽 hypothesis

    def test_writing_first_sentence(self, engine):
        out = {"sections": [{"content": "本节提出三大发现并展开论证过程。"}]}
        claims = engine._extract_claims(WorkflowStage.WRITING, out)
        assert len(claims) == 1

    def test_literature_gap_and_themes(self, engine):
        out = {"research_gap": {"description": "现有研究缺少东盟视角需要补充的空白领域"},
               "sections": [{"theme": "框架理论在传播研究的应用综述"}]}
        claims = engine._extract_claims(WorkflowStage.LITERATURE, out)
        assert len(claims) == 2

    def test_inspiration_and_review_skip(self, engine):
        """选题与评审阶段不抽断言"""
        assert engine._extract_claims(WorkflowStage.INSPIRATION, {"directions": [{"title": "方向很长值得校验吗"}]}) == []
        assert engine._extract_claims(WorkflowStage.REVIEW, {"reviewers": [{"suggestions": "修改建议很长但不是事实"}]}) == []


class TestExtractEntities:
    """实体提取测试"""

    def test_topic_and_kg_match(self, engine):
        """产出物文本应匹配 KG 真实实体（嫦娥六号在图库中）"""
        out = {"topic": "嫦娥六号", "findings": [{"finding": "嫦娥六号实现了月背采样"}]}
        entities = engine._extract_entities(out, "嫦娥六号")
        assert "嫦娥六号" in entities
        assert len(entities) <= 6

    def test_directions_keywords(self, engine):
        out = {"directions": [{"keywords": ["国际月球科研站"]}]}
        entities = engine._extract_entities(out, "议题")
        assert len(entities) >= 1

    def test_short_topic_ignored(self, engine):
        entities = engine._extract_entities({}, "短")  # 长度 <2
        assert entities == []

    def test_non_dict_output(self, engine):
        entities = engine._extract_entities("str", "议题")
        assert "议题" in entities


class TestAttachSearchSources:
    """搜索来源附加测试"""

    def test_attaches_sources_and_query(self, engine):
        out = {}
        engine._attach_search_sources(out, [
            {"url": "https://a.com", "title": "标题A", "content": "摘要", "source": "TavilySearch"},
            "非法条目",  # 非 dict 跳过
        ], "嫦娥六号 最新进展")
        assert out["search_sources"][0]["url"] == "https://a.com"
        assert out["search_query"] == "嫦娥六号 最新进展"

    def test_no_sources_no_pollution(self, engine):
        out = {"topic": "t"}
        engine._attach_search_sources(out, [], "")
        assert "search_sources" not in out
        assert "search_query" not in out


class TestInjectUserStyle:
    """用户论文库风格注入测试"""

    def test_non_writing_stage_skip(self, engine):
        inputs = {}
        engine._inject_user_style(WorkflowStage.DESIGN, inputs, "user1")
        assert "style_sample" not in inputs

    def test_no_owner_skip(self, engine):
        inputs = {}
        engine._inject_user_style(WorkflowStage.WRITING, inputs, None)
        assert "style_sample" not in inputs

    def test_user_disabled_skip(self, engine):
        inputs = {}
        engine._inject_user_style(WorkflowStage.WRITING, inputs, "u", use_user_style=False)
        assert "style_sample" not in inputs

    def test_explicit_style_sample_priority(self, engine):
        inputs = {"style_sample": "用户自己提供"}
        engine._inject_user_style(WorkflowStage.WRITING, inputs, "u")
        assert inputs["style_sample"] == "用户自己提供"

    def test_injects_library_style(self, engine):
        lib = MagicMock()
        lib.global_style.return_value = {
            "few_shot": ["示例段落一", "示例段落二"],
            "terms": ["框架理论", "议程设置"],
        }
        with patch('src.knowledge.user_library.get_user_library', return_value=lib):
            inputs = {}
            engine._inject_user_style(WorkflowStage.WRITING, inputs, "user1")
        assert "示例段落一" in inputs["style_sample"]
        assert "框架理论" in inputs["style_sample"]

    def test_empty_style_skip(self, engine):
        lib = MagicMock()
        lib.global_style.return_value = {}
        with patch('src.knowledge.user_library.get_user_library', return_value=lib):
            inputs = {}
            engine._inject_user_style(WorkflowStage.WRITING, inputs, "user1")
        assert "style_sample" not in inputs

    def test_library_exception_degrades(self, engine):
        with patch('src.knowledge.user_library.get_user_library', side_effect=RuntimeError("db down")):
            inputs = {}
            engine._inject_user_style(WorkflowStage.WRITING, inputs, "user1")
        assert "style_sample" not in inputs


class TestAttachVerificationExtra:
    """校验结果附加测试"""

    def _out(self):
        return {"topic": "嫦娥六号", "findings": [
            {"finding": "嫦娥六号于2024年实现月背采样返回的客观记录描述"}]}

    def test_success_attaches_verification(self, engine):
        from src.schemas import VerificationResult, VerificationStatus
        vr = VerificationResult(claim="c", status=VerificationStatus.VERIFIED,
                                confidence=0.85, rag_evidence="ev", notes="n")
        validator = MagicMock()
        validator.cross_validate_claim.return_value = vr
        with patch('src.verification.cross_validator.CrossValidator', return_value=validator):
            out = self._out()
            engine._attach_verification(WorkflowStage.DATA_ANALYSIS, out, "嫦娥六号")
        assert out["verification"]["summary"]["total"] == 1
        assert out["verification"]["summary"]["verified"] == 1
        assert out["verification"]["items"][0]["confidence"] == 0.85

    def test_validation_timeout_degrades(self, engine):
        validator = MagicMock()
        with patch('src.verification.cross_validator.CrossValidator', return_value=validator), \
             patch.object(engine, '_run_with_timeout', return_value=None):
            out = self._out()
            engine._attach_verification(WorkflowStage.DATA_ANALYSIS, out, "嫦娥六号")
        assert out["verification"]["items"][0]["notes"] == "校验超时（已降级）"
        assert out["verification"]["summary"]["unverified"] == 1

    def test_validator_init_failure_skips(self, engine):
        with patch('src.verification.cross_validator.CrossValidator', side_effect=RuntimeError("cv down")):
            out = self._out()
            engine._attach_verification(WorkflowStage.DATA_ANALYSIS, out, "嫦娥六号")
        assert "verification" not in out

    def test_no_claims_skips(self, engine):
        out = {"topic": "嫦娥六号"}  # 无 findings → 无断言
        engine._attach_verification(WorkflowStage.DATA_ANALYSIS, out, "嫦娥六号")
        assert "verification" not in out


class TestPolishSection:
    """论文章节润色测试"""

    def test_success_returns_polished(self, engine):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "  润色后的内容  "
        with patch('src.llm_client.get_llm_client', return_value=mock_llm):
            out = engine.polish_section("引言", "原文内容", "更简洁", {"api_key": "k"})
        assert out == "润色后的内容"
        kwargs = mock_llm.chat.call_args.kwargs
        assert kwargs["json_mode"] is False
        assert kwargs["max_tokens"] == 4000

    def test_timeout_raises(self, engine):
        mock_llm = MagicMock()
        with patch('src.llm_client.get_llm_client', return_value=mock_llm), \
             patch.object(engine, '_run_with_timeout', return_value=None):
            with pytest.raises(TimeoutError, match="超时"):
                engine.polish_section("引言", "内容")


class TestHotTopics:
    """今日热点获取测试"""

    def _source(self, title, url, content="内容"):
        return type("S", (), {"title": title, "url": url, "content": content, "source": "T"})

    def test_returns_filtered_topics(self, engine):
        engine._hot_cache = {"at": 0, "items": []}
        engine._hot_seen_urls = []
        svc = MagicMock()
        svc.search_for_topic.return_value = [
            self._source("科技日报", "u1"),                     # junk 标题
            self._source("中国航天今日取得新突破性进展", "https://a.com/x", "报道内容"),
            self._source("短标题", "https://b.com"),            # 过短
            self._source("人工智能大模型发布最新成果详情", "https://c.com"),
        ]
        with patch('src.search.unified_search.get_unified_search_service', return_value=svc):
            items = engine.get_hot_topics(limit=6)
        titles = [i["title"] for i in items]
        assert "科技日报" not in titles
        assert any("航天" in t for t in titles)
        assert len(titles) == 2

    def test_never_repeats_seen_url(self, engine):
        engine._hot_cache = {"at": 0, "items": []}
        engine._hot_seen_urls = ["https://seen.com/x"]
        svc = MagicMock()
        svc.search_for_topic.return_value = [
            self._source("已经展示过的完整新闻标题内容", "https://seen.com/x"),
            self._source("另一个全新科技新闻标题条目", "https://new.com/y"),
        ]
        with patch('src.search.unified_search.get_unified_search_service', return_value=svc):
            items = engine.get_hot_topics(limit=6)
        assert all(i["url"] != "https://seen.com/x" for i in items)

    def test_cache_hit_skips_search(self, engine):
        engine._hot_cache = {"at": 9999999999.0, "items": [{"title": "缓存项", "url": "u", "content": "", "source": ""}]}
        svc = MagicMock()
        with patch('src.search.unified_search.get_unified_search_service', return_value=svc):
            items = engine.get_hot_topics(limit=6)
        assert items[0]["title"] == "缓存项"
        svc.search_for_topic.assert_not_called()

    def test_search_failure_returns_empty(self, engine):
        engine._hot_cache = {"at": 0, "items": []}
        with patch('src.search.unified_search.get_unified_search_service', side_effect=RuntimeError("net")):
            assert engine.get_hot_topics() == []


class TestStageContextSuccess:
    """阶段上下文成功注入路径测试（mock 服务正常返回）"""

    def test_search_and_vector_injected(self, engine):
        """文献阶段应注入 search_context 与 knowledge_hits"""
        svc = MagicMock()
        svc.search_for_topic.return_value = [
            type("S", (), {"url": "https://n.com", "title": "新闻", "content": "内容", "source": "T"})()]
        vs = MagicMock()
        vs.search.return_value = [{"text": "知识片段" * 30, "score": 0.8, "metadata": {"source": "lib"}}]
        with patch('src.search.unified_search.get_unified_search_service', return_value=svc), \
             patch('src.knowledge.vector_store.get_vector_store', return_value=vs):
            ctx = engine._build_stage_context(WorkflowStage.LITERATURE, {"topic": "嫦娥六号"})
        assert ctx["search_context"][0]["url"] == "https://n.com"
        assert ctx["search_context"][0]["content"]  # 内容截断 400
        assert "search_query" in ctx
        assert ctx["knowledge_hits"][0]["score"] == 0.8

    def test_kg_entities_injected_for_inspiration(self, engine):
        kg = MagicMock()
        kg.find_related_entities.return_value = [{"entity": f"实体{i}"} for i in range(12)]
        with patch('src.knowledge.kg_builder.get_knowledge_graph', return_value=kg):
            ctx = engine._build_stage_context(WorkflowStage.INSPIRATION, {"topic": "嫦娥六号"})
        assert len(ctx["kg_entities"]) == 10  # 限制 10

    def test_empty_topic_returns_empty(self, engine):
        ctx = engine._build_stage_context(WorkflowStage.WRITING, {})
        assert "search_context" not in ctx  # 无 topic → 无查询
