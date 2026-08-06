"""
云观星传 - 科研流程工作流测试
覆盖：阶段元数据 / schema 往返 / ProjectStore 状态机 / WorkflowEngine 编排 /
7 个科研流程 Agent（mock LLM）/ /api/workflow API
"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖（faiss 未装时兜底；httpx 为真包，starlette.testclient 需要真实实现）
for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from src.schemas import (
    InspirationResult, TopicDirection, LiteratureReview, LiteratureSection, ResearchGap,
    ResearchDesignResult, ResearchQuestion, QuestionQualityReport,
    MethodRecommendationResult, MethodRecommendation, AnalysisResult,
    PaperDraft, PaperSection, ReviewerFeedback, ReviewerOpinion, ReviewerScores,
    ResearchProject, StageRecord, StageStatus,
)
from src.workflow.stages import WorkflowStage, STAGE_META, get_stage_meta_list
from src.workflow.project import ProjectStore
from src.workflow.engine import WorkflowEngine

# ---------------------------------------------------------------------------
# 阶段元数据
# ---------------------------------------------------------------------------


class TestStageMeta:
    def test_7_stages_in_order(self):
        """7 个阶段按科研流程顺序"""
        stages = get_stage_meta_list()
        assert len(stages) == 7
        assert [s["stage"] for s in stages] == [1, 2, 3, 4, 5, 6, 7]
        names = [s["name"] for s in stages]
        assert names == ["选题孵化", "文献综述", "研究设计", "方法推荐", "数据分析", "学术写作", "同行评审"]

    def test_each_stage_has_agent(self):
        """每个阶段映射一个智能体"""
        for stage, meta in STAGE_META.items():
            assert meta["agent_name"].endswith("_agent")
            assert meta["output_schema"]

    def test_icons_unique(self):
        """阶段图标不重复"""
        icons = [meta["icon"] for meta in STAGE_META.values()]
        assert len(set(icons)) == 7

    def test_stage_enum_values(self):
        """枚举数值即顺序"""
        assert WorkflowStage.INSPIRATION == 1
        assert WorkflowStage.REVIEW == 7


# ---------------------------------------------------------------------------
# Schema 往返
# ---------------------------------------------------------------------------


class TestWorkflowSchemas:
    def test_inspiration_result_roundtrip(self):
        r = InspirationResult(
            topic="朱雀2号火箭",
            directions=[TopicDirection(title="科技竞争传播", research_value=92, innovation_potential=88)],
            selected_direction="科技竞争传播",
        )
        d = r.model_dump()
        assert d["directions"][0]["research_value"] == 92

    def test_literature_review_roundtrip(self):
        r = LiteratureReview(
            topic="t",
            sections=[LiteratureSection(theme="框架研究", content="...")],
            research_gap=ResearchGap(description="缺东盟视角", missing_perspectives=["东盟"]),
        )
        assert r.research_gap.missing_perspectives == ["东盟"]

    def test_design_result_roundtrip(self):
        r = ResearchDesignResult(
            topic="t",
            research_questions=[ResearchQuestion(id="RQ1", text="东盟媒体如何报道？")],
            quality_report=QuestionQualityReport(clarity=90, innovativeness=80, operability=85),
        )
        assert r.quality_report.clarity == 90

    def test_reviewer_feedback_roundtrip(self):
        r = ReviewerFeedback(
            topic="t",
            reviewers=[ReviewerOpinion(reviewer_id="Reviewer 1", perspective="方法专家",
                                       scores=ReviewerScores(innovation=70, methodology=60))],
        )
        assert r.reviewers[0].scores.methodology == 60

    def test_project_model(self):
        p = ResearchProject(id="p1", title="T", interest="I")
        p.stages["1"] = StageRecord(stage=1, status=StageStatus.AWAITING_REVIEW, output={"topic": "x"})
        assert p.stages["1"].status == StageStatus.AWAITING_REVIEW


# ---------------------------------------------------------------------------
# ProjectStore 状态机
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return ProjectStore(base_dir=tmp_path / "projects")


class TestProjectStore:
    def test_create_initializes_7_stages(self, store):
        p = store.create(title="测试项目", interest="朱雀2号火箭")
        assert len(p.stages) == 7
        assert p.current_stage == 1
        assert p.stages["1"].status == StageStatus.PENDING

    def test_get_and_list(self, store):
        p = store.create(title="A", interest="议题A")
        store.create(title="B", interest="议题B")
        got = store.get(p.id)
        assert got.title == "A"
        assert len(store.list()) == 2

    def test_update_stage_and_advance(self, store):
        p = store.create(title="A", interest="议题A")
        updated = store.update_stage(p.id, 1, status=StageStatus.AWAITING_REVIEW,
                                     output={"topic": "议题A", "directions": []})
        assert updated.stages["1"].status == StageStatus.AWAITING_REVIEW
        # 确认后推进到阶段 2
        done = store.update_stage(p.id, 1, status=StageStatus.COMPLETED)
        assert done.current_stage == 2

    def test_update_stage_history(self, store):
        p = store.create(title="A", interest="议题A")
        updated = store.update_stage(p.id, 1, status=StageStatus.RUNNING,
                                     append_history={"stage": 1, "action": "run_start", "summary": "开始"})
        assert len(updated.history) == 1
        assert updated.history[0]["action"] == "run_start"

    def test_delete(self, store):
        p = store.create(title="A", interest="议题A")
        assert store.delete(p.id) is True
        assert store.get(p.id) is None

    def test_path_traversal_blocked(self, store):
        """project_id 含路径穿越字符时仍落在 base_dir 内"""
        p = store.create(title="A", interest="议题A")
        # 直接构造恶意 id 路径（内部用 _path）
        path = store._path("../evil")
        assert path.resolve().parent == store.base_dir.resolve()
        assert "../" not in str(path)

    def test_list_skips_corrupted_file(self, store, tmp_path):
        store.create(title="A", interest="议题A")
        # 写入一个损坏 JSON
        bad = store.base_dir / "proj_bad.json"
        bad.write_text("{not json", encoding="utf-8")
        projects = store.list()
        assert len(projects) == 1  # 损坏文件被跳过
        assert projects[0].title == "A"

    def test_list_sorted_by_created_at_desc(self, store):
        p1 = store.create(title="A", interest="议题A")
        p2 = store.create(title="B", interest="议题B")
        assert [p.id for p in store.list()] == [p2.id, p1.id]  # 后创建在前


# ---------------------------------------------------------------------------
# WorkflowEngine 编排
# ---------------------------------------------------------------------------


def make_mock_agent(output: dict):
    """构造返回固定输出的 mock Agent"""
    agent = MagicMock()
    agent.run.return_value = output
    return agent


@pytest.fixture
def engine(store, tmp_path):
    """带 mock Agent 的引擎（不触发 LLM / 搜索）"""
    agents = {
        WorkflowStage.INSPIRATION: make_mock_agent({"topic": "t", "directions": [{"title": "方向A", "research_value": 90}]}),
        WorkflowStage.LITERATURE: make_mock_agent({"topic": "t", "sections": [], "research_gap": {}}),
        WorkflowStage.DESIGN: make_mock_agent({"topic": "t", "research_questions": []}),
        WorkflowStage.METHOD: make_mock_agent({"topic": "t", "methods": []}),
        WorkflowStage.DATA_ANALYSIS: make_mock_agent({"topic": "t", "findings": []}),
        WorkflowStage.WRITING: make_mock_agent({"topic": "t", "sections": []}),
        WorkflowStage.REVIEW: make_mock_agent({"topic": "t", "reviewers": []}),
    }
    with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError("no net")), \
         patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError("no vs")), \
         patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError("no kg")):
        eng = WorkflowEngine(store=store, agents=agents)
        yield eng


class TestWorkflowEngine:
    def test_create_project(self, engine):
        p = engine.create_project(title="我的研究", interest="朱雀2号火箭的国际报道")
        assert p.title == "我的研究"
        assert p.current_stage == 1

    def test_run_stage_awaits_review(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        record = engine.run_stage(p.id, 1, {"topic": "朱雀2号火箭"})
        assert record.status == StageStatus.AWAITING_REVIEW
        assert record.output["directions"][0]["title"] == "方向A"

    def test_run_stage_denies_locked_stage(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        with pytest.raises(ValueError, match="未解锁"):
            engine.run_stage(p.id, 3, {})

    def test_run_stage_reject_unknown_project(self, engine):
        with pytest.raises(ValueError, match="项目不存在"):
            engine.run_stage("proj_xxxx", 1, {})

    def test_approve_advances(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        engine.run_stage(p.id, 1, {})
        project = engine.approve_stage(p.id, 1)
        assert project.stages["1"].status == StageStatus.COMPLETED
        assert project.current_stage == 2

    def test_approve_requires_output(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        with pytest.raises(ValueError, match="无待确认"):
            engine.approve_stage(p.id, 1)

    def test_full_flow_7_stages(self, engine):
        """完整跑完 7 阶段：每阶段 run + approve"""
        p = engine.create_project(interest="朱雀2号火箭")
        for stage in range(1, 8):
            rec = engine.run_stage(p.id, stage, {"topic": "朱雀2号火箭"})
            assert rec.status == StageStatus.AWAITING_REVIEW
            project = engine.approve_stage(p.id, stage)
            assert project.stages[str(stage)].status == StageStatus.COMPLETED
        final = engine.get_project(p.id)
        assert final.current_stage == 7
        assert final.status == "completed"

    def test_6_stages_not_completed(self, engine):
        """回归：完成前 6 阶段时项目不得标记 completed（第 7 阶段尚未执行）"""
        p = engine.create_project(interest="朱雀2号火箭")
        for stage in range(1, 7):
            engine.run_stage(p.id, stage, {})
            engine.approve_stage(p.id, stage)
        project = engine.get_project(p.id)
        assert project.current_stage == 7
        assert project.status == "active", "第 7 阶段未执行前不得标记 completed"

    def test_rerun_after_failure_clears_output(self, engine):
        """回归：阶段执行失败后 output 清空，重跑成功恢复"""
        p = engine.create_project(interest="朱雀2号火箭")
        agent = engine._get_agent(1)
        agent.run.side_effect = [RuntimeError("LLM 不可用"), {"topic": "t", "directions": []}]
        with pytest.raises(RuntimeError):
            engine.run_stage(p.id, 1, {})
        failed = engine.get_project(p.id)
        assert failed.stages["1"].status == StageStatus.FAILED
        assert failed.stages["1"].output is None
        assert failed.stages["1"].run_count == 1
        # 重跑成功
        rec = engine.run_stage(p.id, 1, {})
        assert rec.status == StageStatus.AWAITING_REVIEW
        assert rec.run_count == 2
        # 引擎兜底补全 project_title
        assert rec.output == {"topic": "t", "directions": [], "project_title": p.title}

    def test_rerun_failure_after_success_clears_old_output(self, engine):
        """回归：已有成功产出后重跑失败，旧产出物必须被清空（不得残留展示）"""
        p = engine.create_project(interest="朱雀2号火箭")
        agent = engine._get_agent(1)
        agent.run.side_effect = [{"topic": "t", "directions": [{"title": "旧产出"}]}, RuntimeError("LLM 不可用")]
        # 第一次成功
        rec = engine.run_stage(p.id, 1, {})
        assert rec.status == StageStatus.AWAITING_REVIEW
        assert rec.output["directions"][0]["title"] == "旧产出"
        # 重跑失败 → 旧产出必须清空
        with pytest.raises(RuntimeError):
            engine.run_stage(p.id, 1, {})
        failed = engine.get_project(p.id)
        assert failed.stages["1"].status == StageStatus.FAILED
        assert failed.stages["1"].output is None, "重跑失败后不得残留旧产出物"
        assert failed.stages["1"].run_count == 2

    def test_previous_outputs_injected(self, engine):
        """跨阶段数据流：执行阶段 2 时自动注入阶段 1 的产出物"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine.run_stage(p.id, 1, {})
        engine.approve_stage(p.id, 1)
        agent = engine._get_agent(2)
        agent.run.side_effect = lambda inputs: dict(inputs)  # 原样返回输入以检查
        engine.run_stage(p.id, 2, {})
        called_inputs = agent.run.call_args[0][0]
        assert "inspiration_result" in called_inputs
        assert called_inputs["inspiration_result"]["directions"][0]["title"] == "方向A"

    def test_run_count_increments(self, engine):
        """每次 run_stage 递增 run_count"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine.run_stage(p.id, 1, {})
        assert engine.get_project(p.id).stages["1"].run_count == 1
        engine.run_stage(p.id, 1, {})  # 重跑
        assert engine.get_project(p.id).stages["1"].run_count == 2

    def test_run_all_completes_all_stages(self, engine):
        """一键全流程：7 阶段全部直接完成，项目 completed"""
        p = engine.create_project(interest="朱雀2号火箭")
        result = engine.run_all(p.id)
        final = engine.get_project(p.id)
        assert final.status == "completed"
        for stage in range(1, 8):
            rec = final.stages[str(stage)]
            assert rec.status == StageStatus.COMPLETED, f"阶段 {stage} 未完成: {rec.status}"
            assert rec.output is not None
        assert len(result["stages"]) == 7
        assert all(s["status"] == "completed" for s in result["stages"].values())

    def test_run_all_injects_previous_outputs(self, engine):
        """全流程阶段 2 自动收到阶段 1 产出"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine.run_all(p.id)
        agent2 = engine._get_agent(2)
        called = agent2.run.call_args[0][0]
        assert called["inspiration_result"]["directions"][0]["title"] == "方向A"

    def test_run_all_passes_materials_to_stage5(self, engine):
        """全流程将素材传给数据分析阶段"""
        p = engine.create_project(interest="朱雀2号火箭")
        materials = [{"name": "报道1", "content": "text"}]
        engine.run_all(p.id, materials=materials)
        agent5 = engine._get_agent(5)
        called = agent5.run.call_args[0][0]
        assert called["materials"] == materials

    def test_run_all_stops_on_failure(self, engine):
        """全流程中途失败即停止，后续阶段保持 pending"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine._get_agent(3).run.side_effect = RuntimeError("LLM 不可用")
        result = engine.run_all(p.id)
        final = engine.get_project(p.id)
        assert final.stages["1"].status == StageStatus.COMPLETED
        assert final.stages["2"].status == StageStatus.COMPLETED
        assert final.stages["3"].status == StageStatus.FAILED
        assert final.stages["4"].status == StageStatus.PENDING
        assert result["stages"][3]["status"] == "failed"

    def test_export_markdown_contains_stages(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        engine.run_stage(p.id, 1, {})
        result = engine.export_project(p.id, "md")
        assert result["format"] == "md"
        assert "选题孵化" in result["content"]
        assert "朱雀2号火箭" in result["content"]

    def test_export_json(self, engine):
        p = engine.create_project(interest="朱雀2号火箭")
        result = engine.export_project(p.id, "json")
        data = json.loads(result["content"])
        assert data["interest"] == "朱雀2号火箭"
        assert len(data["stages"]) == 7

    def test_stage_context_degrades_gracefully(self, engine):
        """搜索/知识库不可达时上下文注入为空但不报错"""
        p = engine.create_project(interest="朱雀2号火箭")
        record = engine.run_stage(p.id, 1, {"topic": "朱雀2号火箭"})
        assert record.status == StageStatus.AWAITING_REVIEW


# ---------------------------------------------------------------------------
# 7 个科研流程 Agent（mock LLM）
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    """Mock LLM 客户端：chat_json 返回指定 JSON"""
    with patch("src.agents.base_agent.get_llm_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


def _inspiration_output():
    return {
        "topic": "朱雀2号火箭",
        "directions": [{
            "title": "科技竞争传播", "summary": "研究朱雀2号报道中的竞争框架",
            "research_value": 92, "existing_coverage": 60, "innovation_potential": 88,
            "reasons": ["议题新", "数据可得", "理论契合"], "keywords": ["朱雀2号", "框架", "国际报道"],
        }],
        "selected_direction": "科技竞争传播",
        "discussion_summary": "学者们认为该方向兼具前沿性与可行性。",
    }


class TestResearchInspirationAgent:
    def test_build_user_prompt(self, mock_llm):
        from src.agents.research_inspiration_agent import ResearchInspirationAgent
        a = ResearchInspirationAgent(llm_client=mock_llm)
        prompt = a._build_user_prompt({"topic": "朱雀2号", "kg_entities": ["朱雀2号"]})
        assert "朱雀2号" in prompt and "知识图谱关联实体" in prompt

    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = _inspiration_output()
        from src.agents.research_inspiration_agent import ResearchInspirationAgent
        a = ResearchInspirationAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号"})
        assert result["selected_direction"] == "科技竞争传播"
        assert result["directions"][0]["research_value"] == 92


class TestLiteratureReviewAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "sections": [{"theme": "竞争框架研究", "content": "既有研究集中于欧美媒体"}],
            "research_gap": {"description": "缺少东盟视角", "missing_perspectives": ["东盟"], "suggestion": "扩展样本"},
            "references": [{"title": "Space Race 2.0", "source": "Journal of Communication", "year": "2025"}],
        }
        from src.agents.literature_review_agent import LiteratureReviewAgent
        a = LiteratureReviewAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "direction": "科技竞争传播"})
        assert result["research_gap"]["missing_perspectives"] == ["东盟"]
        assert len(result["sections"]) == 1


class TestResearchQuestionAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "research_questions": [{"id": "RQ1", "text": "东盟媒体如何报道朱雀2号？"}],
            "hypotheses": [{"id": "H1", "statement": "东盟媒体更多使用发展框架", "hypothesis_type": "quantitative"}],
            "quality_report": {"clarity": 90, "innovativeness": 85, "operability": 88, "comments": ["清晰"]},
        }
        from src.agents.research_question_agent import ResearchQuestionAgent
        a = ResearchQuestionAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "literature_review": {"research_gap": {}}})
        assert result["research_questions"][0]["id"] == "RQ1"
        assert result["quality_report"]["clarity"] == 90


class TestMethodAdvisorAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "methods": [{
                "name": "框架分析", "method_type": "qualitative", "fit_score": 89,
                "representative_papers": ["Entman (1993)"],
                "operation_steps": ["确定分析单位", "构建类目", "编码", "信度检验"],
                "rationale": "适合识别报道框架",
            }],
        }
        from src.agents.method_advisor_agent import MethodAdvisorAgent
        a = MethodAdvisorAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "research_questions": [{"id": "RQ1", "text": "如何报道？"}]})
        assert result["methods"][0]["fit_score"] == 89
        assert len(result["methods"][0]["operation_steps"]) == 4


class TestDataAnalysisAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "analysis_type": "framework_analysis",
            "coding_table": [{"category": "竞争框架", "count": 12}],
            "findings": [{"finding": "竞争框架占主导", "evidence": "原文摘录", "confidence": 0.8}],
            "interpretation": "初步解读",
        }
        from src.agents.data_analysis_agent import DataAnalysisAgent
        a = DataAnalysisAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "method": {"name": "框架分析"},
                        "materials": [{"name": "报道1", "content": "..."}]})
        assert result["coding_table"][0]["count"] == 12


class TestPaperWriterAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "title": "朱雀2号火箭的国际媒体报道框架研究",
            "sections": [{"section": "摘要", "content": "本研究..."}, {"section": "引言", "content": "..."}],
            "style_notes": ["学习到紧凑句式"],
        }
        from src.agents.paper_writer_agent import PaperWriterAgent
        a = PaperWriterAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "analysis_result": {"findings": []}})
        assert result["title"].startswith("朱雀2号")
        assert len(result["sections"]) == 2


class TestReviewerSimulatorAgent:
    def test_run_parses_schema(self, mock_llm):
        mock_llm.chat_json.return_value = {
            "topic": "朱雀2号",
            "reviewers": [{
                "reviewer_id": "Reviewer 1", "perspective": "方法专家",
                "scores": {"innovation": 70, "methodology": 60, "argumentation": 75, "literature": 65, "language": 80},
                "suggestions": ["补充编码信度检验"],
            }],
            "revision_notes": "优先补充信度检验。",
        }
        from src.agents.reviewer_simulator_agent import ReviewerSimulatorAgent
        a = ReviewerSimulatorAgent(llm_client=mock_llm)
        result = a.run({"topic": "朱雀2号", "paper_draft": {"sections": []}})
        assert result["reviewers"][0]["perspective"] == "方法专家"
        assert result["revision_notes"]


class TestAgentInfo:
    def test_all_agents_have_info(self, mock_llm):
        from src.agents.research_inspiration_agent import ResearchInspirationAgent
        from src.agents.literature_review_agent import LiteratureReviewAgent
        from src.agents.research_question_agent import ResearchQuestionAgent
        from src.agents.method_advisor_agent import MethodAdvisorAgent
        from src.agents.data_analysis_agent import DataAnalysisAgent
        from src.agents.paper_writer_agent import PaperWriterAgent
        from src.agents.reviewer_simulator_agent import ReviewerSimulatorAgent
        for cls in [ResearchInspirationAgent, LiteratureReviewAgent, ResearchQuestionAgent,
                    MethodAdvisorAgent, DataAnalysisAgent, PaperWriterAgent, ReviewerSimulatorAgent]:
            a = cls(llm_client=mock_llm)
            info = a.get_agent_info()
            assert info["name"] == cls.agent_name
            assert info["description"]


# ---------------------------------------------------------------------------
# /api/workflow API
# ---------------------------------------------------------------------------


@pytest.fixture
def api_engine(store, tmp_path):
    """供 API 测试的 mock 引擎（patch 路由中的单例获取）"""
    agents = {stage: make_mock_agent({"topic": "t"}) for stage in range(1, 8)}
    with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError), \
         patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError), \
         patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError), \
         patch("api.routes.workflow.get_workflow_engine") as mock_engine_get:
        eng = WorkflowEngine(store=store, agents=agents)
        mock_engine_get.return_value = eng
        yield eng


class TestWorkflowAPI:
    def test_create_and_get_project(self, api_engine):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            r = client.post("/api/workflow/projects", json={"title": "我的研究", "interest": "朱雀2号"})
            assert r.status_code == 200
            pid = r.json()["project"]["id"]
            r2 = client.get(f"/api/workflow/projects/{pid}")
            assert r2.status_code == 200
            assert r2.json()["project"]["interest"] == "朱雀2号"

    def test_stages_meta_endpoint(self, api_engine):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            r = client.get("/api/workflow/stages")
            assert r.status_code == 200
            assert len(r.json()["stages"]) == 7

    def test_run_approve_export_flow(self, api_engine):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            pid = client.post("/api/workflow/projects", json={"interest": "朱雀2号"}).json()["project"]["id"]
            # 未解锁阶段 400
            assert client.post(f"/api/workflow/projects/{pid}/stages/3/run", json={"inputs": {}}).status_code == 400
            # 阶段 1 执行
            r = client.post(f"/api/workflow/projects/{pid}/stages/1/run", json={"inputs": {"topic": "朱雀2号"}})
            assert r.status_code == 200
            assert r.json()["status"] == "awaiting_review"
            # 产出物
            r = client.get(f"/api/workflow/projects/{pid}/stages/1/result")
            assert r.status_code == 200
            assert r.json()["output"]["topic"] == "t"
            # 确认 → 推进
            r = client.post(f"/api/workflow/projects/{pid}/stages/1/approve")
            assert r.status_code == 200
            assert r.json()["project"]["current_stage"] == 2
            # 导出
            r = client.get(f"/api/workflow/projects/{pid}/export", params={"fmt": "md"})
            assert r.status_code == 200
            assert "选题孵化" in r.json()["content"]

    def test_404_unknown_project(self, api_engine):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            assert client.get("/api/workflow/projects/proj_nope").status_code == 404

    def test_delete_project(self, api_engine):
        """DELETE /api/workflow/projects/{id}：物理删除项目与产出物文件"""
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            pid = client.post("/api/workflow/projects", json={"interest": "朱雀2号"}).json()["project"]["id"]
            # 删除前项目文件存在
            assert api_engine.store.get(pid) is not None
            r = client.delete(f"/api/workflow/projects/{pid}")
            assert r.status_code == 200
            assert r.json()["status"] == "deleted"
            assert r.json()["project_id"] == pid
            # 物理移除：store 中不再有该项目文件
            assert api_engine.store.get(pid) is None
            # 列表不再包含
            ids = [p["id"] for p in client.get("/api/workflow/projects").json()["projects"]]
            assert pid not in ids

    def test_delete_project_404(self, api_engine):
        """删除不存在的项目返回 404"""
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            assert client.delete("/api/workflow/projects/proj_nope").status_code == 404


# ---------------------------------------------------------------------------
# 增强功能：RAG+KG 双校验 / 章节润色 / Word 导出 / 今日热点
# ---------------------------------------------------------------------------


class TestWorkflowEnhancements:
    """产出物后置校验 + 润色 + Word 导出 + 热点（全部可降级，不阻塞主流程）"""

    def test_extract_claims_by_stage(self, engine):
        """各阶段断言抽取规则"""
        claims = engine._extract_claims(WorkflowStage.DESIGN, {
            "research_questions": [{"id": "RQ1", "text": "全球南方媒体如何框架化报道嫦娥六号月球样品研究？"}],
        })
        assert claims and "嫦娥六号" in claims[0]

    def test_attach_verification_appends(self, engine):
        """校验结果附加到产出物"""
        from src.schemas import VerificationResult, VerificationStatus
        fake_validator = MagicMock()
        fake_validator.cross_validate_claim.return_value = VerificationResult(
            claim="x", status=VerificationStatus.VERIFIED, confidence=0.9,
            rag_evidence="证据文本", kg_match="嫦娥六号", notes="RAG: verified | KG: partial | External: unverified",
        )
        with patch("src.verification.cross_validator.CrossValidator", return_value=fake_validator):
            output = {"topic": "嫦娥六号", "directions": [
                {"title": "嫦娥六号月球样品研究的国际传播框架", "summary": "分析全球南方媒体对月球样品研究的报道框架", "keywords": ["嫦娥六号", "国际传播"]},
            ]}
            engine._attach_verification(WorkflowStage.INSPIRATION, output, "嫦娥六号")
        v = output["verification"]
        assert v["summary"]["total"] >= 1
        assert v["summary"]["verified"] >= 1
        assert v["items"][0]["claim"]

    def test_attach_verification_degrades(self, engine):
        """校验器异常时静默降级，不抛错也不写 verification"""
        with patch("src.verification.cross_validator.CrossValidator", side_effect=RuntimeError("validator down")):
            output = {"topic": "t", "directions": [{"title": "一个足够长的选题方向标题用于校验断言", "summary": "对应摘要说明"}]}
            engine._attach_verification(1, output, "t")
        assert "verification" not in output

    def test_run_stage_attaches_verification(self, store, tmp_path):
        """run_stage 产出物自动附带双校验结果（mock validator）"""
        from src.schemas import VerificationResult, VerificationStatus
        agents = {WorkflowStage.INSPIRATION: make_mock_agent({
            "topic": "嫦娥六号",
            "directions": [{"title": "嫦娥六号月球样品国际传播研究", "summary": "分析各国媒体报道框架与叙事差异"}],
        })}
        fake_validator = MagicMock()
        fake_validator.cross_validate_claim.return_value = VerificationResult(
            claim="x", status=VerificationStatus.PARTIALLY_VERIFIED, confidence=0.7,
        )
        with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError()), \
             patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError()), \
             patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError()), \
             patch("src.verification.cross_validator.CrossValidator", return_value=fake_validator):
            eng = WorkflowEngine(store=store, agents=agents)
            p = eng.create_project(interest="嫦娥六号")
            rec = eng.run_stage(p.id, 1, {"topic": "嫦娥六号"})
        assert rec.status == StageStatus.AWAITING_REVIEW
        assert rec.output["verification"]["summary"]["total"] >= 1

    def test_run_stage_survives_verification_failure(self, store, tmp_path):
        """校验器完全不可用时 run_stage 依旧成功（不阻塞主流程）"""
        agents = {WorkflowStage.INSPIRATION: make_mock_agent({
            "topic": "t",
            "directions": [{"title": "一个足够长的选题方向标题用于校验断言", "summary": "对应摘要说明"}],
        })}
        with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError()), \
             patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError()), \
             patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError()), \
             patch("src.verification.cross_validator.CrossValidator", side_effect=RuntimeError("validator down")):
            eng = WorkflowEngine(store=store, agents=agents)
            p = eng.create_project(interest="t")
            rec = eng.run_stage(p.id, 1, {"topic": "t"})
        assert rec.status == StageStatus.AWAITING_REVIEW
        assert rec.output is not None

    def test_polish_section(self, engine):
        """章节润色：调用 LLM（json_mode=False），返回文本"""
        fake_llm = MagicMock()
        fake_llm.chat.return_value = "润色后的引言正文。"
        with patch("src.llm_client.get_llm_client", return_value=fake_llm):
            text = engine.polish_section("引言", "这是一段足够长的原文用于测试润色。", "更简洁")
        assert text == "润色后的引言正文。"
        assert fake_llm.chat.call_args.kwargs["json_mode"] is False

    def test_export_word(self, engine):
        """Word 导出返回 docx 二进制（PK 魔数）"""
        p = engine.create_project(interest="测试项目")
        engine.store.update_stage(
            p.id, 1, status=StageStatus.COMPLETED,
            output={"topic": "t", "directions": [{"title": "方向A", "research_value": 90}]},
        )
        result = engine.export_project(p.id, "word")
        assert result["format"] == "word"
        assert isinstance(result["content_bytes"], bytes)
        assert result["content_bytes"].startswith(b"PK")

    def test_get_hot_topics_degrades(self, engine):
        """热点搜索不可用时降级为空列表"""
        with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError("no net")):
            assert engine.get_hot_topics() == []

    def test_extract_claims_guards_malformed_output(self, engine):
        """LLM 输出字段类型漂移（dict 而非 list）不抛异常，正常降级为空"""
        malformed = {"directions": {"title": "方向", "summary": "摘要"}, "sections": {"theme": "x"}}
        for stage in range(1, 8):
            claims = engine._extract_claims(stage, malformed)
            assert claims == []

    def test_attach_verification_survives_malformed_output(self, engine):
        """畸形产出物 + 可用校验器：抽取为空则直接返回，不写 verification 也不抛错"""
        from src.schemas import VerificationResult, VerificationStatus
        fake_validator = MagicMock()
        fake_validator.cross_validate_claim.return_value = VerificationResult(
            claim="x", status=VerificationStatus.VERIFIED, confidence=0.9,
        )
        with patch("src.verification.cross_validator.CrossValidator", return_value=fake_validator):
            output = {"topic": "t", "directions": {"title": "方向", "summary": "摘要"}}  # 畸形：dict 非 list
            engine._attach_verification(WorkflowStage.INSPIRATION, output, "t")
        assert "verification" not in output

    def test_run_stage_malformed_output_not_failed(self, store, tmp_path):
        """畸形产出物时 run_stage 依旧成功（校验不拖垮主流程）"""
        agents = {WorkflowStage.INSPIRATION: make_mock_agent({
            "topic": "t", "directions": {"title": "方向", "summary": "摘要"},  # 畸形
        })}
        with patch("src.search.unified_search.get_unified_search_service", side_effect=RuntimeError()), \
             patch("src.knowledge.vector_store.get_vector_store", side_effect=RuntimeError()), \
             patch("src.knowledge.kg_builder.get_knowledge_graph", side_effect=RuntimeError()), \
             patch("src.verification.cross_validator.CrossValidator", side_effect=RuntimeError("validator down")):
            eng = WorkflowEngine(store=store, agents=agents)
            p = eng.create_project(interest="t")
            rec = eng.run_stage(p.id, 1, {"topic": "t"})
        assert rec.status == StageStatus.AWAITING_REVIEW
        assert rec.output["directions"] == {"title": "方向", "summary": "摘要"}  # 产出物原样保留

    def test_literature_review_theory_relations_roundtrip(self):
        """文献综述 schema 支持理论关系（前端理论关系图数据源）"""
        from src.schemas import LiteratureReview, TheoryRelation
        lr = LiteratureReview(
            topic="嫦娥六号",
            theory_relations=[
                TheoryRelation(source="框架理论", relation="承继自", target="议程设置理论"),
                TheoryRelation(source="框架理论", relation="互补于", target="沉默的螺旋理论"),
            ],
        )
        d = lr.model_dump()
        assert len(d["theory_relations"]) == 2
        assert d["theory_relations"][0]["source"] == "框架理论"

    def test_analysis_result_sentiment_roundtrip(self):
        """数据分析 schema 支持情绪分布（前端情绪分析图数据源）"""
        from src.schemas import AnalysisResult, SentimentDistribution
        ar = AnalysisResult(
            topic="嫦娥六号",
            sentiment=SentimentDistribution(positive=45, neutral=40, negative=15, summary="整体以正面为主"),
        )
        d = ar.model_dump()
        assert d["sentiment"]["positive"] == 45
        assert d["sentiment"]["summary"] == "整体以正面为主"
        # 缺省时零值可用（LLM 漏填不破坏 schema）
        empty = AnalysisResult(topic="x").model_dump()
        assert empty["sentiment"] == {"positive": 0.0, "neutral": 0.0, "negative": 0.0, "summary": ""}

    def test_export_pdf(self, engine):
        """PDF 导出返回二进制（%PDF 魔数），复用 fpdf2 中文字体链"""
        p = engine.create_project(interest="测试项目")
        engine.store.update_stage(
            p.id, 1, status=StageStatus.COMPLETED,
            output={"topic": "t", "directions": [{"title": "方向A", "research_value": 90}]},
        )
        result = engine.export_project(p.id, "pdf")
        assert result["format"] == "pdf"
        assert isinstance(result["content_bytes"], bytes)
        assert result["content_bytes"][:4] in (b"%PDF", b"%\xe2\xe3\xcf\xd3") or result["content_bytes"].startswith(b"%PDF")

    def test_export_word_pdf_binary_download_http(self, api_engine):
        """Word/PDF 经 HTTP 下载返回 200 且 Content-Disposition 中文名 RFC5987 编码（防 latin-1 报错）"""
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            pid = client.post("/api/workflow/projects", json={"interest": "嫦娥六号"}).json()["project"]["id"]
            client.post(f"/api/workflow/projects/{pid}/stages/1/run", json={"inputs": {"topic": "嫦娥六号"}})
            for fmt, magic in [("word", b"PK"), ("pdf", b"%PDF")]:
                r = client.get(f"/api/workflow/projects/{pid}/export", params={"fmt": fmt})
                assert r.status_code == 200, f"{fmt} 导出失败: {r.text[:200]}"
                assert r.content.startswith(magic), f"{fmt} 魔数不符: {r.content[:8]}"
                cd = r.headers.get("content-disposition", "")
                assert "filename*=UTF-8''" in cd, f"{fmt} 未做 RFC5987 编码: {cd}"

    def test_reviewer_suggestions_normalize_dict_output(self):
        """评审建议 LLM 格式漂移（对象列表）时归一化为字符串，不抛 Schema 校验失败"""
        from src.schemas import ReviewerFeedback, ReviewerOpinion, ReviewerScores
        # 复现用户报错场景：suggestions 每条为 {"problem": "..."}
        fb = ReviewerFeedback(
            topic="t",
            reviewers=[
                ReviewerOpinion(
                    reviewer_id="Reviewer 1",
                    suggestions=[{"problem": "方法部分缺少样本量论证，建议补充抽样依据及最终样本量。"}],
                    scores={"innovation": "92.6", "methodology": 88, "argumentation": "85", "literature": 79.4, "language": 90},
                ),
                ReviewerOpinion(reviewer_id="Reviewer 2", suggestions=["正常字符串建议"]),
            ],
            revision_notes={"notes": "一键修改说明文本"},
        )
        d = fb.model_dump()
        assert d["reviewers"][0]["suggestions"] == ["方法部分缺少样本量论证，建议补充抽样依据及最终样本量。"]
        assert d["reviewers"][1]["suggestions"] == ["正常字符串建议"]
        assert d["revision_notes"] == "一键修改说明文本"
        # scores 浮点/字符串数值归一为整数
        assert d["reviewers"][0]["scores"]["innovation"] == 93
        assert d["reviewers"][0]["scores"]["literature"] == 79

    def test_method_representative_papers_normalize_dict_output(self):
        """方法推荐代表论文 LLM 格式漂移（对象列表）时归一化为字符串，不抛 Schema 校验失败"""
        from src.schemas import MethodRecommendationResult, MethodRecommendation
        # 复现 NAS 报错场景：representative_papers 每条为 {"title": "..."}
        r = MethodRecommendationResult(
            topic="嫦娥七号",
            methods=[
                MethodRecommendation(
                    name="框架分析",
                    representative_papers=[
                        {"title": "全球南方媒体中的科技合作叙事：以中国空间站报道为例"},
                        "Entman, R. M. (1993). Framing. Journal of Communication.",
                    ],
                    operation_steps=[{"step": "构建初始框架类目"}, "确定分析单位"],
                ),
            ],
        )
        d = r.model_dump()
        papers = d["methods"][0]["representative_papers"]
        assert papers[0] == "全球南方媒体中的科技合作叙事：以中国空间站报道为例"
        assert papers[1].startswith("Entman")
        steps = d["methods"][0]["operation_steps"]
        assert steps[0] == "构建初始框架类目"
        assert steps[1] == "确定分析单位"

    def test_topic_direction_reasons_keywords_normalize(self):
        """选题 reasons/keywords 对象列表同样归一化（StrList 通用防漂移）"""
        from src.schemas import InspirationResult, TopicDirection
        r = InspirationResult(
            topic="t",
            directions=[
                TopicDirection(
                    title="方向A",
                    reasons=[{"reason": "理由一"}, "理由二"],
                    keywords=[{"keyword": "关键词A"}, "关键词B"],
                ),
            ],
        )
        d = r.model_dump()
        assert d["directions"][0]["reasons"] == ["理由一", "理由二"]
        assert d["directions"][0]["keywords"] == ["关键词A", "关键词B"]


class TestTopicCorpusAutoFill:
    """议题语料自动补齐（新议题冷启动防护）"""

    def test_load_science_facts_empty_trigger(self):
        """本地无该议题 facts 时应触发补齐分支（_ensure 逻辑判定）"""
        from src.knowledge.data_loader import get_data_loader
        loader = get_data_loader()
        # 一个极不可能存在的议题 → 应返回空（触发补齐）
        fake = "完全不存在的议题XYZ_2026"
        assert loader.load_science_facts(fake) == []
