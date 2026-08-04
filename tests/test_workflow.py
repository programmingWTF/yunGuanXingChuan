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
        assert rec.output == {"topic": "t", "directions": []}

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
