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
