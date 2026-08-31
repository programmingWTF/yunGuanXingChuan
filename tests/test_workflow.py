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

    # ------------------------------------------------------------------
    # issue #115：写作阶段「按照我的风格写作」开关（use_user_style）
    # ------------------------------------------------------------------

    def _unlock_to_writing(self, engine, interest="朱雀2号火箭"):
        """跑完并确认前 5 阶段，解锁写作阶段（6），返回项目"""
        p = engine.create_project(interest=interest)
        for stage in range(1, 6):
            engine.run_stage(p.id, stage, {"topic": interest}, owner_id="user-1")
            engine.approve_stage(p.id, stage)
        return p

    def test_inject_user_style_disabled_skips_style_sample(self, engine):
        """issue #115：use_user_style=False 时写作阶段不注入用户论文库风格（style_sample 不出现）"""
        from src.knowledge.user_library import get_user_library
        fake_lib = MagicMock()
        fake_lib.global_style.return_value = {
            "few_shot": ["示例1：句式A"],
            "terms": ["术语A", "术语B"],
        }
        with patch("src.knowledge.user_library.get_user_library", return_value=fake_lib):
            p = self._unlock_to_writing(engine)
            agent = engine._get_agent(6)
            agent.run.side_effect = lambda inputs: dict(inputs)  # 原样返回输入以检查
            engine.run_stage(p.id, 6, {"topic": "朱雀2号火箭"}, owner_id="user-1", use_user_style=False)
            called = agent.run.call_args[0][0]
            assert "style_sample" not in called, "use_user_style=False 时不得注入 style_sample"

    def test_inject_user_style_enabled_by_default(self, engine):
        """issue #115：默认 use_user_style=True（现状）仍自动注入用户论文库风格"""
        from src.knowledge.user_library import get_user_library
        fake_lib = MagicMock()
        fake_lib.global_style.return_value = {
            "few_shot": ["示例1：句式A"],
            "terms": ["术语A"],
        }
        with patch("src.knowledge.user_library.get_user_library", return_value=fake_lib):
            p = self._unlock_to_writing(engine)
            agent = engine._get_agent(6)
            agent.run.side_effect = lambda inputs: dict(inputs)
            engine.run_stage(p.id, 6, {"topic": "朱雀2号火箭"}, owner_id="user-1")
            called = agent.run.call_args[0][0]
            assert "style_sample" in called, "默认应注入用户论文库风格"
            assert "示例1：句式A" in called["style_sample"]
            assert "术语A" in called["style_sample"]

    def test_run_all_use_user_style_false_skips_style(self, engine):
        """issue #115：run_all 透传 use_user_style=False，写作阶段不注入用户风格"""
        from src.knowledge.user_library import get_user_library
        fake_lib = MagicMock()
        fake_lib.global_style.return_value = {"few_shot": ["示例X"], "terms": ["术语X"]}
        with patch("src.knowledge.user_library.get_user_library", return_value=fake_lib):
            p = engine.create_project(interest="朱雀2号火箭")
            engine.run_all(p.id, owner_id="user-1", use_user_style=False)
            agent6 = engine._get_agent(6)
            called = agent6.run.call_args[0][0]
            assert "style_sample" not in called, "run_all use_user_style=False 时不得注入 style_sample"

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

    def test_attach_search_sources_with_sources(self, engine):
        """存在有效搜索来源时，structured search_sources 附加到产出物（Issue #98）"""
        output: dict = {}
        context = [
            {"url": "https://example.com/a", "title": "来源A", "content": "摘要A", "source": "TavilySearch"},
            {"url": "https://example.com/b", "title": "来源B", "content": "", "source": "QwenWebSearch"},
            {"url": "", "title": "无URL来源", "content": "x", "source": ""},  # 无 url 也应透传（前端负责兜底）
            "非字典项",  # 应被过滤
        ]
        WorkflowEngine._attach_search_sources(output, context)
        assert len(output["search_sources"]) == 3
        assert output["search_sources"][0] == {
            "url": "https://example.com/a", "title": "来源A", "content": "摘要A", "source": "TavilySearch",
        }
        assert output["search_sources"][2]["url"] == ""
        assert not any(k == "非字典项" for s in output["search_sources"] for k in s)

    def test_attach_search_sources_empty_omits_field(self, engine):
        """无搜索来源时产出物不附加空 search_sources 字段，避免污染"""
        output: dict = {"topic": "t", "directions": []}
        WorkflowEngine._attach_search_sources(output, [])
        assert "search_sources" not in output

    def test_run_stage_attaches_search_sources_to_output(self, engine):
        """run_stage 全链路：搜索上下文非空时产出物携带 search_sources"""
        p = engine.create_project(interest="朱雀2号火箭")
        with patch(
            "src.search.unified_search.get_unified_search_service"
        ) as mock_svc:
            svc = MagicMock()
            hit = MagicMock()
            hit.url = "https://example.com/rocket"
            hit.title = "朱雀2号点火"
            hit.content = "发射成功"
            hit.source = "TavilySearch"
            svc.search_for_topic.return_value = [hit]
            mock_svc.return_value = svc
            with patch("src.workflow.engine.WorkflowEngine._attach_verification"):
                record = engine.run_stage(p.id, 1, {"topic": "朱雀2号火箭"})
        assert record.status == StageStatus.AWAITING_REVIEW
        assert record.output["search_sources"][0]["title"] == "朱雀2号点火"
        assert record.output["search_sources"][0]["url"] == "https://example.com/rocket"


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


def _make_auth_client(app, *, email=None, admin=False):
    """创建已登录 TestClient：直连建用户 + 签发 JWT，绕开真实邮件验证码。
    用户系统（Issue #90）上线后 /api/workflow 项目接口全部要求登录。"""
    import os
    import secrets as _secrets
    from fastapi.testclient import TestClient
    from api.auth import create_user, issue_token, SESSION_COOKIE

    if email is None:
        email = f"t{_secrets.token_hex(6)}@test.local"
    if admin:
        prev = os.environ.get("ADMIN_EMAILS")
        os.environ["ADMIN_EMAILS"] = email
        try:
            user = create_user(email, "管理员", "Test@123456")
        finally:
            if prev is None:
                os.environ.pop("ADMIN_EMAILS", None)
            else:
                os.environ["ADMIN_EMAILS"] = prev
    else:
        user = create_user(email, "测试用户", "Test@123456")
    # 多租户模式：API 测试默认给用户配 mock LLM（绕过「未配置 400」拦截；agent 层已 mock）
    from api.auth import set_user_llm_config
    set_user_llm_config(user["id"], {
        "llm": {"api_key": "test-key", "base_url": "http://llm.test/v1", "model": "test-model"},
        "embedding": None,
    })
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, issue_token(user["id"]))
    return user, client


class TestWorkflowAPI:
    def test_create_and_get_project(self, api_engine):
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            r = client.post("/api/workflow/projects", json={"title": "我的研究", "interest": "朱雀2号"})
            assert r.status_code == 200
            pid = r.json()["project"]["id"]
            r2 = client.get(f"/api/workflow/projects/{pid}")
            assert r2.status_code == 200
            assert r2.json()["project"]["interest"] == "朱雀2号"

    def test_unauthenticated_401(self, api_engine):
        """用户系统上线后：未登录访问项目接口一律 401"""
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            assert client.post("/api/workflow/projects", json={"interest": "x"}).status_code == 401
            assert client.get("/api/workflow/projects").status_code == 401
            assert client.get("/api/workflow/projects/proj_nope").status_code == 401
            assert client.delete("/api/workflow/projects/proj_nope").status_code == 401

    def test_project_isolation_between_users(self, api_engine):
        """历史隔离（Issue #90 核心）：他人项目 404，admin 可见全部"""
        from api.main import app
        _, client_a = _make_auth_client(app)
        r = client_a.post("/api/workflow/projects", json={"title": "A的研究", "interest": "朱雀2号"})
        assert r.status_code == 200
        pid = r.json()["project"]["id"]
        # 用户 B：他人项目一律 404
        _, client_b = _make_auth_client(app)
        assert client_b.get(f"/api/workflow/projects/{pid}").status_code == 404
        assert client_b.delete(f"/api/workflow/projects/{pid}").status_code == 404
        # 用户 A：自己的项目列表可见
        ids = [p["id"] for p in client_a.get("/api/workflow/projects").json()["projects"]]
        assert pid in ids
        # admin：全部可见
        _, admin_client = _make_auth_client(app, admin=True)
        ids = [p["id"] for p in admin_client.get("/api/workflow/projects").json()["projects"]]
        assert pid in ids

    def test_stages_meta_endpoint(self, api_engine):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            r = client.get("/api/workflow/stages")
            assert r.status_code == 200
            assert len(r.json()["stages"]) == 7

    def test_run_approve_export_flow(self, api_engine):
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
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
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            assert client.get("/api/workflow/projects/proj_nope").status_code == 404

    def test_delete_project(self, api_engine):
        """DELETE /api/workflow/projects/{id}：物理删除项目与产出物文件"""
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
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
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            assert client.delete("/api/workflow/projects/proj_nope").status_code == 404


# ---------------------------------------------------------------------------
# /api/auth 用户认证（Issue #90）
# ---------------------------------------------------------------------------


class TestAuthAPI:
    def test_send_code_validation(self):
        """非法邮箱 400；已注册邮箱 409"""
        import secrets as _secrets
        from fastapi.testclient import TestClient
        from api.main import app
        from api.auth import create_user

        taken_email = f"taken{_secrets.token_hex(4)}@test.local"
        create_user(taken_email, "已注册", "Test@123456")
        with TestClient(app) as client:
            assert client.post("/api/auth/send-code", json={"email": "not-an-email"}).status_code == 400
            assert client.post("/api/auth/send-code", json={"email": taken_email}).status_code == 409

    def test_register_login_me_logout_flow(self):
        """完整注册流程：发码 → 错码 400 → 正确码注册 → 冷却 429 → 重复注册 409 → 登录 → me → 登出"""
        import secrets as _secrets
        from fastapi.testclient import TestClient
        from api.main import app
        from api.routes import auth as auth_routes

        email = f"u{_secrets.token_hex(4)}@test.local"
        with TestClient(app) as client:
            with patch.object(auth_routes, "send_verification_code", return_value=True) as send_mock:
                r = client.post("/api/auth/send-code", json={"email": email})
                assert r.status_code == 200
                code = send_mock.call_args[0][1]
                assert len(code) == 6 and code.isdigit()
            # 60s 冷却期内重发 → 429
            assert client.post("/api/auth/send-code", json={"email": email}).status_code == 429
            # 错误验证码 → 400
            r = client.post("/api/auth/register", json={"name": "测试", "email": email, "password": "Passw0rd!", "code": "000000"})
            assert r.status_code == 400
            # 正确验证码 → 注册成功（普通 user 角色；201 对齐 liguiyu-home）
            r = client.post("/api/auth/register", json={"name": "测试", "email": email, "password": "Passw0rd!", "code": code})
            assert r.status_code == 201
            assert r.json()["user"]["role"] == "user"
            # 重复注册 → 409
            r = client.post("/api/auth/register", json={"name": "测试", "email": email, "password": "Passw0rd!", "code": code})
            assert r.status_code == 409
            # 未登录 me → 401
            assert client.get("/api/auth/me").status_code == 401
            # 错误密码 → 401
            assert client.post("/api/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
            # 登录成功 → 会话 Cookie + me
            r = client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!"})
            assert r.status_code == 200
            assert r.json()["user"]["email"] == email
            r = client.get("/api/auth/me")
            assert r.status_code == 200
            assert r.json()["user"]["email"] == email
            # 登出后 me → 401
            assert client.post("/api/auth/logout").status_code == 200
            assert client.get("/api/auth/me").status_code == 401

    def test_admin_email_gets_admin_role(self):
        """ADMIN_EMAILS 中的邮箱注册即 admin（照搬 liguiyu-home）"""
        import os
        import secrets as _secrets
        from fastapi.testclient import TestClient
        from api.main import app
        from api.routes import auth as auth_routes

        email = f"boss{_secrets.token_hex(4)}@test.local"
        prev = os.environ.get("ADMIN_EMAILS")
        os.environ["ADMIN_EMAILS"] = email
        try:
            with TestClient(app) as client:
                with patch.object(auth_routes, "send_verification_code", return_value=True) as send_mock:
                    client.post("/api/auth/send-code", json={"email": email})
                    code = send_mock.call_args[0][1]
                r = client.post("/api/auth/register", json={"name": "老板", "email": email, "password": "Passw0rd!", "code": code})
                assert r.status_code == 201
                assert r.json()["user"]["role"] == "admin"
        finally:
            if prev is None:
                os.environ.pop("ADMIN_EMAILS", None)
            else:
                os.environ["ADMIN_EMAILS"] = prev

    def test_admin_endpoints(self):
        """管理后台：admin 可见用户/项目列表；普通用户 403；不存在项目 404"""
        from unittest.mock import MagicMock, patch as _patch
        from api.main import app

        fake_engine = MagicMock()
        fake_engine.list_projects.return_value = []
        fake_engine.get_project.return_value = None
        with _patch("api.routes.admin.get_workflow_engine", return_value=fake_engine):
            _, admin_client = _make_auth_client(app, admin=True)
            assert admin_client.get("/api/admin/users").status_code == 200
            assert admin_client.get("/api/admin/projects").status_code == 200
            assert admin_client.get("/api/admin/projects/nope").status_code == 404
            _, user_client = _make_auth_client(app)
            assert user_client.get("/api/admin/users").status_code == 403
            assert user_client.get("/api/admin/projects").status_code == 403


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
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
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


# ---------------------------------------------------------------------------
# 用户论文库风格注入（个人论文库模块接入点）
# ---------------------------------------------------------------------------


class TestUserStyleInjection:
    """WorkflowEngine._inject_user_style：写作阶段自动注入用户论文库风格

    直接白盒调用该方法（不走完整 run_stage——前置校验/语料补齐/校验层太重）。
    """

    def _make_engine(self, store, tmp_path):
        agents = {
            WorkflowStage.INSPIRATION: make_mock_agent({"topic": "t", "directions": []}),
            WorkflowStage.WRITING: make_mock_agent({"topic": "t", "sections": []}),
        }
        return WorkflowEngine(store=store, agents=agents)

    def test_writing_stage_injects_style(self, store, tmp_path, monkeypatch):
        """WRITING 阶段且用户有论文库 → 注入 style_sample"""
        # _inject_user_style 内部是 `from src.knowledge.user_library import get_user_library`，
        # 运行时从该模块取绑定 → patch 模块属性即可生效
        import src.knowledge.user_library as ul_mod
        fake_style = {
            "terms": ["深度学习", "Transformer"],
            "few_shot": ["本文基于深度学习框架展开研究，系统比较了多种模型结构的性能差异。"],
            "structure": {},
        }
        monkeypatch.setattr(ul_mod, "get_user_library", lambda uid: MagicMock(global_style=lambda: fake_style))

        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t"}
        eng._inject_user_style(WorkflowStage.WRITING, inputs, owner_id="u1")
        assert "style_sample" in inputs
        assert "深度学习" in inputs["style_sample"]
        assert "个人论文风格示例" in inputs["style_sample"]

    def test_style_sample_not_overwritten(self, store, tmp_path, monkeypatch):
        """用户显式提供 style_sample 时不覆盖"""
        import src.knowledge.user_library as ul_mod
        monkeypatch.setattr(ul_mod, "get_user_library", lambda uid: MagicMock(global_style=lambda: {
            "terms": ["A"], "few_shot": ["B"], "structure": {},
        }))
        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t", "style_sample": "用户显式风格"}
        eng._inject_user_style(WorkflowStage.WRITING, inputs, owner_id="u1")
        assert inputs["style_sample"] == "用户显式风格"

    def test_no_owner_skips(self, store, tmp_path, monkeypatch):
        """未提供 owner_id（未登录/内部调用）→ 跳过注入"""
        called = {"n": 0}

        def fake_lib(uid):
            called["n"] += 1
            return MagicMock(global_style=lambda: {"terms": ["X"], "few_shot": [], "structure": {}})

        import src.knowledge.user_library as ul_mod
        monkeypatch.setattr(ul_mod, "get_user_library", fake_lib)
        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t"}
        eng._inject_user_style(WorkflowStage.WRITING, inputs, owner_id=None)
        assert called["n"] == 0
        assert "style_sample" not in inputs

    def test_empty_library_skips(self, store, tmp_path, monkeypatch):
        """论文库为空 → 不注入、不报错"""
        import src.knowledge.user_library as ul_mod
        monkeypatch.setattr(ul_mod, "get_user_library", lambda uid: MagicMock(global_style=lambda: {}))
        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t"}
        eng._inject_user_style(WorkflowStage.WRITING, inputs, owner_id="u1")
        assert "style_sample" not in inputs

    def test_non_writing_stage_skips(self, store, tmp_path, monkeypatch):
        """非写作阶段不注入"""
        import src.knowledge.user_library as ul_mod
        monkeypatch.setattr(ul_mod, "get_user_library", lambda uid: MagicMock(global_style=lambda: {
            "terms": ["X"], "few_shot": ["Y"], "structure": {},
        }))
        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t"}
        eng._inject_user_style(WorkflowStage.LITERATURE, inputs, owner_id="u1")
        assert "style_sample" not in inputs

    def test_exception_degrades(self, store, tmp_path, monkeypatch):
        """风格库异常 → 降级（不抛错、不注入）"""
        def boom(uid):
            raise RuntimeError("库损坏")

        import src.knowledge.user_library as ul_mod
        monkeypatch.setattr(ul_mod, "get_user_library", boom)
        eng = self._make_engine(store, tmp_path)
        inputs = {"topic": "t"}
        eng._inject_user_style(WorkflowStage.WRITING, inputs, owner_id="u1")  # 不应抛异常
        assert "style_sample" not in inputs


# ---------------------------------------------------------------------------
# 闭环迭代（issue #129）：save_design 原子性 + 版本号 + 入参校验
# ---------------------------------------------------------------------------


class TestClosedLoopIteration:
    def test_update_stage_atomic_bump_design_version(self, store):
        """update_stage(bump_design_version=True) 单次加锁内同时更新产出物与版本号"""
        p = store.create(title="原子", interest="i")
        assert p.design_version == 1
        updated = store.update_stage(
            p.id, 3,
            status=StageStatus.AWAITING_REVIEW,
            output={"research_questions": [{"id": "RQ1", "text": "x"}], "hypotheses": []},
            bump_design_version=True,
            append_history={"stage": 3, "action": "design_saved", "summary": "保存 V2"},
        )
        # 一次写盘：产出物 + 版本号同步落盘，无中间态
        assert updated.design_version == 2
        assert updated.stages["3"].output["research_questions"][0]["id"] == "RQ1"
        # 重新从盘上读，确认已持久化
        reloaded = store.get(p.id)
        assert reloaded.design_version == 2
        assert reloaded.stages["3"].output["hypotheses"] == []

    def test_save_design_updates_output_and_version(self, store, tmp_path):
        """save_design：更新 stage3 产出物 + design_version +1，同一次写盘完成"""
        p = store.create(title="闭环", interest="i")
        store.update_stage(p.id, 3, status=StageStatus.COMPLETED,
                           output={"research_questions": [{"id": "RQ1", "text": "旧"}],
                                   "hypotheses": [{"id": "H1", "statement": "旧", "hypothesis_type": "qualitative"}]})
        eng = WorkflowEngine(store=store)
        proj = eng.save_design(p.id, [{"id": "RQ1", "text": "新"}], [{"id": "H1", "statement": "新", "hypothesis_type": "quantitative"}], suggestion="建议")
        assert proj.design_version == 2
        out = proj.stages["3"].output
        assert out["research_questions"][0]["text"] == "新"
        assert out["hypotheses"][0]["hypothesis_type"] == "quantitative"
        reloaded = store.get(p.id)
        assert reloaded.design_version == 2  # 落盘一致

    def test_save_design_requires_design_output(self, store):
        """设计阶段尚无产出物时保存应报 ValueError"""
        p = store.create(title="无产出", interest="i")
        eng = WorkflowEngine(store=store)
        with pytest.raises(ValueError, match="尚无产出物"):
            eng.save_design(p.id, [], [])

    def test_save_design_request_rejects_malformed_items(self):
        """畸形 RQ/H 条目（缺字段）应在校验层拒绝（422），而非静默落盘"""
        from api.routes.workflow import SaveDesignRequest
        from pydantic import ValidationError
        with pytest.raises(Exception):
            SaveDesignRequest(research_questions=[{"text": "缺 id"}])
        with pytest.raises(Exception):
            SaveDesignRequest(hypotheses=[{"id": "H1"}])  # 缺 statement
        ok = SaveDesignRequest(
            research_questions=[{"id": "RQ1", "text": "合法"}],
            hypotheses=[{"id": "H1", "statement": "合法", "hypothesis_type": "quantitative"}],
        )
        assert ok.research_questions[0].id == "RQ1"


# ---------------------------------------------------------------------------
# 自动闭环迭代完整回路（2026-09-01 桂鱼反馈修复）
# ---------------------------------------------------------------------------


class TestAutoIterateLoop:
    """自动迭代：iterating 状态标记 + 多阶段路由修订 + 结束自动评审确认"""

    def _completed_project(self, engine):
        """构造已跑完全流程的项目（current_stage=7, status=completed）"""
        p = engine.create_project(interest="朱雀2号火箭")
        for s in range(1, 8):
            engine.store.update_stage(p.id, s, status=StageStatus.COMPLETED, output={"topic": "t"})
        return engine.store.get(p.id)

    def test_auto_iterate_marks_iterating_then_completed_and_finalizes_review(self, engine):
        """迭代中 status=iterating（前端显示「迭代中」而非「已完成」），
        结束后自动重跑评审并 approve（自动确认 + 重新评估）"""
        p = self._completed_project(engine)
        called = []
        with patch.object(engine.store, "set_status", wraps=engine.store.set_status) as spy:
            rounds = engine.auto_iterate(p.id, max_rounds=1)
            called = [c.args[1] for c in spy.call_args_list if c.args[1] in ("iterating", "completed")]
        assert called[0] == "iterating", "迭代开始应置 iterating"
        assert called[-1] == "completed", "迭代结束应恢复 completed"
        assert len(rounds) == 1
        # 迭代记录已落盘；评审已重新跑并自动确认；每轮数据分析产出也已自动确认
        p2 = engine.store.get(p.id)
        assert len(p2.iterations) >= 1
        assert p2.stages["5"].status == StageStatus.COMPLETED, "迭代中数据分析产出应自动确认（不留给前端待确认）"
        assert p2.stages["7"].status == StageStatus.COMPLETED, "收尾应自动评审并确认"
        assert p2.status == "completed"

    def test_auto_iterate_revises_stages_by_target_stage(self, engine):
        """诊断问题 target_stage 2/3/4/6 → 分别修订文献/设计/方法/写作产出"""
        p = engine.create_project(interest="i")
        engine.store.update_stage(p.id, 2, status=StageStatus.COMPLETED, output={"sections": [{"theme": "A", "content": "旧A"}, {"theme": "B", "content": "旧B"}]})
        engine.store.update_stage(p.id, 3, status=StageStatus.COMPLETED, output={
            "research_questions": [{"id": "RQ1", "text": "旧1"}, {"id": "RQ2", "text": "旧2"}],
            "hypotheses": [{"id": "H1", "statement": "旧H", "hypothesis_type": "qualitative"}, {"id": "H2", "statement": "旧H2", "hypothesis_type": "quantitative"}],
        })
        engine.store.update_stage(p.id, 4, status=StageStatus.COMPLETED, output={"methods": [{"name": "M1", "method_type": "qualitative"}, {"name": "M2", "method_type": "quantitative"}]})
        engine.store.update_stage(p.id, 6, status=StageStatus.COMPLETED, output={"sections": [{"heading": "a", "content": "旧a"}, {"heading": "b", "content": "旧b"}]})
        from src.schemas import IterationRecord
        it = IterationRecord(
            iteration=1, timestamp="", source_stage=5, design_version=1,
            problems=[
                {"text": "补文献", "target_stage": 2},
                {"text": "改设计", "target_stage": 3},
                {"text": "调方法", "target_stage": 4},
                {"text": "改写作", "target_stage": 6},
            ],
        )
        # mock 修订只返回「部分条目」——验证未提及条目被保留（防顶掉）
        with patch.object(engine, "_revise_literature_with_llm", return_value={"sections": [{"theme": "A", "content": "新A"}], "references": ["ref-new"]}), \
             patch.object(engine, "_revise_design_with_llm", return_value={
                 "research_questions": [{"id": "RQ1", "text": "新1"}],
                 "hypotheses": [{"id": "H2", "statement": "新H2", "hypothesis_type": "quantitative"}],
             }), \
             patch.object(engine, "_revise_method_with_llm", return_value={"methods": [{"name": "M1", "method_type": "quantitative", "fit_score": 90}]}), \
             patch.object(engine, "_revise_writing_with_llm", return_value={"sections": [{"heading": "b", "content": "新b"}]}):
            proj = engine.store.get(p.id)
            touched = engine._revise_stage_by_problems(proj, it, None)
        assert touched == [2, 3, 4, 6]
        proj = engine.store.get(p.id)
        assert proj.design_version == 2, "修订设计应使版本号 +1"
        # 文献：A 被替换、B 保留（未提及不被顶掉）
        s2 = proj.stages["2"].output["sections"]
        assert {x["theme"] for x in s2} == {"A", "B"}
        assert next(x for x in s2 if x["theme"] == "A")["content"] == "新A"
        assert next(x for x in s2 if x["theme"] == "B")["content"] == "旧B"
        assert "ref-new" in proj.stages["2"].output["references"]
        # 设计：RQ1 替换、RQ2 保留；H2 替换、H1 保留
        rqs = proj.stages["3"].output["research_questions"]
        assert {x["id"] for x in rqs} == {"RQ1", "RQ2"}
        assert next(x for x in rqs if x["id"] == "RQ1")["text"] == "新1"
        assert next(x for x in rqs if x["id"] == "RQ2")["text"] == "旧2"
        hys = proj.stages["3"].output["hypotheses"]
        assert {x["id"] for x in hys} == {"H1", "H2"}
        assert next(x for x in hys if x["id"] == "H2")["statement"] == "新H2"
        assert next(x for x in hys if x["id"] == "H1")["statement"] == "旧H"
        # 方法：M1 替换、M2 保留
        ms = proj.stages["4"].output["methods"]
        assert {x["name"] for x in ms} == {"M1", "M2"}
        assert next(x for x in ms if x["name"] == "M2")["method_type"] == "quantitative"
        # 写作：b 替换、a 保留
        w6 = proj.stages["6"].output["sections"]
        assert {x["heading"] for x in w6} == {"a", "b"}
        assert next(x for x in w6 if x["heading"] == "a")["content"] == "旧a"
        assert next(x for x in w6 if x["heading"] == "b")["content"] == "新b"

    def test_auto_iterate_stops_when_no_revision_possible(self, engine):
        """本轮所有修订失败（如无 LLM）→ 提前终止且不崩，状态仍回 completed"""
        p = self._completed_project(engine)
        rounds = engine.auto_iterate(p.id, max_rounds=3)
        assert len(rounds) == 1  # 首轮分析后修订失败即终止
        p2 = engine.store.get(p.id)
        assert p2.status == "completed"
        assert p2.stages["7"].status == StageStatus.COMPLETED

    def test_auto_iterate_reaches_target_confidence_stops_early(self, engine):
        """可信度达标（无问题）→ 直接停，不再浪费轮数"""
        p = self._completed_project(engine)
        it = None
        with patch.object(engine, "_llm_diagnose", return_value=("达标", 0.95, [])):
            rounds = engine.auto_iterate(p.id, max_rounds=3)
            it = engine.store.get(p.id).iterations
        assert len(rounds) == 1
        assert rounds[0]["confidence"] == 0.95



    def test_merge_stage_patch_preserves_untouched_items(self):
        """_merge_stage_patch：模型只输出部分条目时，未提及条目必须保留（防顶掉）"""
        base = {
            "sections": [{"theme": "A", "content": "旧A"}, {"theme": "B", "content": "旧B"}, {"theme": "C", "content": "旧C"}],
            "references": ["r1", "r2"],
            "research_gap": {"description": "旧gap"},
        }
        patch = {"sections": [{"theme": "B", "content": "新B"}]}
        merged = WorkflowEngine._merge_stage_patch(base, patch)
        themes = [s["theme"] for s in merged["sections"]]
        assert themes == ["A", "B", "C"], "未提及章节必须保留且顺序不变"
        assert merged["sections"][1]["content"] == "新B"
        assert merged["sections"][0]["content"] == "旧A"
        assert merged["references"] == ["r1", "r2"], "未提供 references 时保留原值"
        assert merged["research_gap"] == {"description": "旧gap"}, "未提供 research_gap 时保留原值"

    def test_merge_stage_patch_append_and_dedup(self):
        """_merge_stage_patch：新增条目追加；references 去重追加"""
        base = {
            "methods": [{"name": "M1", "method_type": "qualitative"}],
            "references": ["r1"],
        }
        patch = {
            "methods": [{"name": "M2", "method_type": "quantitative"}],
            "references": ["r1", "r-new"],
        }
        merged = WorkflowEngine._merge_stage_patch(base, patch)
        assert [m["name"] for m in merged["methods"]] == ["M1", "M2"]
        assert merged["references"] == ["r1", "r-new"]



# ---------------------------------------------------------------------------
# LLM 退化输出容错清洗（2026-08-31 线上故障回归）
# ---------------------------------------------------------------------------


class TestOutputSanitize:
    def test_sanitize_drops_repetition_loop_strings(self):
        """LLM 重复循环产生的 484 条 'id: ' 空字符串项应被清洗为空列表，阶段不崩"""
        from src.agents.base_agent import sanitize_for_schema
        bad = {"research_questions": [{"id": "RQ1", "text": "ok"}],
               "hypotheses": ["id: ", "statement: ", "hypothesis_type: "] * 200,
               "quality_report": {"clarity": 80, "innovativeness": 70, "operability": 75,
                                  "comments": ["评语"]}}
        cleaned = sanitize_for_schema(bad, ResearchDesignResult)
        out = ResearchDesignResult.model_validate(cleaned)
        assert out.hypotheses == []
        assert out.research_questions[0].id == "RQ1"

    def test_sanitize_caps_absurd_list_length(self):
        """合法但超长列表应截断（防 LLM 失控生成）"""
        from src.agents.base_agent import sanitize_for_schema
        bad = {"research_questions": [{"id": f"RQ{i}", "text": f"问题{i}"} for i in range(50)],
               "hypotheses": []}
        cleaned = sanitize_for_schema(bad, ResearchDesignResult)
        out = ResearchDesignResult.model_validate(cleaned)
        assert len(out.research_questions) <= 12

    def test_validate_output_recovers_via_sanitize(self):
        """BaseAgent._validate_output 对退化输出应清洗后成功而非抛 ValidationError"""
        from src.agents.research_question_agent import ResearchQuestionAgent
        agent = ResearchQuestionAgent.__new__(ResearchQuestionAgent)  # 不走 __init__（避免依赖注入）
        agent.output_schema = ResearchDesignResult
        agent.agent_name = "research_question_agent"
        bad = {"research_questions": [{"id": "RQ1", "text": "ok"}],
               "hypotheses": ["id: ", "statement: "] * 100}
        out = agent._validate_output(bad)  # 不应抛异常
        assert out["research_questions"][0]["id"] == "RQ1"
