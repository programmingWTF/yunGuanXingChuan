"""
云观星传 - 覆盖率补充测试
1) WorkflowEngine.run_all 剩余分支：项目不存在 / update_stage 返回 None /
   style_sample 注入 / agent 产出 None（超时）/ 产出缺 topic 自动补全 /
   auto_iterate=True 接棒成功与异常降级
2) export_service 剩余分支：非法 JSON 片段容错、对象数组空单元格与 dict 单元格、
   混合数组、多行段落合并、HTML 表格行补齐、_pdf_wrap 空串、字体缺失回退、
   PDF latin-1 降级、Word code/quote 块
"""
import sys
import io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from src.schemas import StageStatus
from src.workflow.stages import WorkflowStage
from src.workflow.project import ProjectStore
from src.workflow.engine import WorkflowEngine
from src.export_service import (
    export_markdown, export_html, export_word, export_pdf,
    _parse_md_blocks, _render_html_blocks, _pdf_wrap, _find_cjk_font,
)


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


# ===========================================================================
# run_all 剩余分支
# ===========================================================================

class TestRunAllExtra:
    """WorkflowEngine.run_all 覆盖补充"""

    def test_run_all_unknown_project_raises(self, engine):
        """项目不存在应抛 ValueError（run_all 入口校验）"""
        with pytest.raises(ValueError, match="项目不存在"):
            engine.run_all("proj_does_not_exist")

    def test_run_all_update_stage_returning_none_raises(self, engine):
        """循环中 update_stage 返回 None（项目被删）应抛 ValueError"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine.store.update_stage = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="项目不存在"):
            engine.run_all(p.id)

    def test_run_all_passes_style_sample_to_writing(self, engine):
        """显式传 style_sample 时应注入写作（阶段 6）输入"""
        p = engine.create_project(interest="朱雀2号火箭")
        style = "样本：务求平实严谨，少用修饰。"
        engine.run_all(p.id, style_sample=style)
        agent6 = engine._get_agent(6)
        called = agent6.run.call_args[0][0]
        assert called["style_sample"] == style

    def test_run_all_agent_none_output_marks_failed(self, engine):
        """agent 返回 None 视作超时，阶段标记失败并停止后续"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine._get_agent(1).run.return_value = None
        result = engine.run_all(p.id)
        final = engine.get_project(p.id)
        assert final.stages["1"].status == StageStatus.FAILED
        assert "超时" in result["stages"][1]["error"]
        assert final.stages["2"].status == StageStatus.PENDING
        assert set(result["stages"]) == {1}

    def test_run_all_output_without_topic_backfills(self, engine):
        """产出缺 topic 时引擎应自动补当前选题"""
        p = engine.create_project(interest="朱雀2号火箭")
        engine._get_agent(1).run.return_value = {"directions": [{"title": "方向X"}]}
        result = engine.run_all(p.id)
        final = engine.get_project(p.id)
        assert final.stages["1"].output["topic"] == "朱雀2号火箭"
        assert all(s["status"] == "completed" for s in result["stages"].values())

    def test_run_all_auto_iterate_success(self, engine):
        """auto_iterate=True 且全流程成功时自动接棒迭代"""
        p = engine.create_project(interest="朱雀2号火箭")
        with patch.object(engine, "auto_iterate", return_value=[{"round": 1}]) as mock_ai:
            result = engine.run_all(p.id, auto_iterate=True)
        mock_ai.assert_called_once()
        final = engine.get_project(p.id)
        assert final.status == "completed"
        assert any(h.get("action") == "auto_iterate_start" for h in final.history)
        assert len(result["stages"]) == 7

    def test_run_all_auto_iterate_exception_ignored(self, engine):
        """auto_iterate 抛异常不应影响主流程结果返回"""
        p = engine.create_project(interest="朱雀2号火箭")
        with patch.object(engine, "auto_iterate", side_effect=RuntimeError("迭代失败")):
            result = engine.run_all(p.id, auto_iterate=True)
        assert result["project"] is not None
        assert all(s["status"] == "completed" for s in result["stages"].values())


# ===========================================================================
# export_service 剩余分支
# ===========================================================================

# 数据形态：覆盖非法 JSON 片段 / 对象数组空单元格 / 对象数组 dict 单元格 /
# 混合数组 / 多行文本段落 / 引用开头文本（→quote 块）/ JSON 片段（→code 块）
EXTRA_DATA = {
    "short_kv": "月球背面",
    "bad_json_fragment": "{\"unterminated",
    "multi_line_note": "第一段普通说明文字\n第二段继续普通说明，不触发表格与列表。",
    "obj_rows": [
        {"name": None, "meta": {"a": 1}, "note": "文本", "empty": ""},
        {"name": "天问三号", "meta": {"b": 2}, "note": "", "empty": "有值"},
    ],
    "mixed_items": [{"k": "v"}, "纯文本项", "[9, 9, 9]"],
    "quote_like": "> 引用样式的说明\n补充引用后的续写文字。",
    "code_like_json": '{"ok": true, "n": 1}',
    "long_text": "字" * 300,
}
EXTRA_META = {
    "generator_type": "research_plan",
    "name": "覆盖率补充报告",
    "topic": "嫦娥六号国际传播",
}


class TestExportServiceExtraBranches:
    """export_service 覆盖补充"""

    def test_markdown_edge_shapes(self):
        """非法 JSON 容错 + 对象数组空/dict 单元格 + 混合数组"""
        md = export_markdown(EXTRA_DATA, EXTRA_META).decode("utf-8")
        assert "| 字段 | 值 |" in md           # 键值对表格
        assert "```json" in md                 # code 片段围栏
        assert "```" in md
        assert "- k: v" in md                  # 混合数组中 dict → 行内拼接
        assert "- 纯文本项" in md
        assert "[9, 9, 9]" in md
        assert "| name |" in md                # 对象数组表格

    def test_parse_md_merges_multiline_para(self):
        """连续普通文本行应合并为一个段落块"""
        blocks = _parse_md_blocks("第一段话\n第二段还是普通文本\n\n第三段独立")
        paras = [b for b in blocks if b["type"] == "para"]
        assert any(b["text"] == "第一段话\n第二段还是普通文本" for b in paras)
        assert any(b["text"] == "第三段独立" for b in paras)

    def test_render_html_pads_short_table_row(self):
        """表格行单元格数不足表头时应补空 <td> 保证对齐"""
        html = _render_html_blocks([
            {"type": "table", "headers": ["a", "b"], "rows": [["1"]]},
        ])
        assert "<td></td>" in html

    def test_pdf_wrap_empty_text(self):
        """空文本应返回单元素空串，避免渲染报错"""
        assert _pdf_wrap(MagicMock(), "", 100) == [""]

    def test_find_cjk_font_missing_falls_back(self):
        """找不到任何 CJK 字体时应回退 Helvetica"""
        with patch("os.path.exists", return_value=False):
            assert _find_cjk_font() == (None, "Helvetica")

    def test_word_code_and_quote_blocks(self):
        """Word 导出应渲染 code（底纹）与 quote（斜体）块"""
        from docx import Document
        out = export_word(EXTRA_DATA, EXTRA_META)
        doc = Document(io.BytesIO(out))
        texts = "\n".join(p.text for p in doc.paragraphs)
        assert '{"ok": true, "n": 1}' in texts
        assert "引用样式的说明" in texts
        assert "第一段普通说明文字" in texts

    def test_pdf_fallback_no_cjk_font_latin1(self):
        """无 CJK 字体时 PDF 应 latin-1 降级而非崩溃"""
        with patch("src.export_service._find_cjk_font", return_value=(None, "Helvetica")):
            out = export_pdf(EXTRA_DATA, EXTRA_META)
        assert out.startswith(b"%PDF")

    def test_html_full_export_smoke(self):
        """HTML 全链路冒烟：上述数据形态可整体渲染"""
        out = export_html(EXTRA_DATA, EXTRA_META)
        assert b"<!DOCTYPE html>" in out or b"<html" in out
        assert "嫦娥六号国际传播".encode("utf-8") in out

    def test_parse_md_breaks_para_on_block_start(self):
        """段落续行遇到列表/标题等块起始行应停止合并"""
        blocks = _parse_md_blocks("说明文字第一行\n- 列表项甲\n\n| a |\n| --- |\n| 1 |")
        paras = [b for b in blocks if b["type"] == "para"]
        assert any(b["text"] == "说明文字第一行" for b in paras)
        assert any(b["type"] == "ul" and b["items"] == ["列表项甲"] for b in blocks)
        assert any(b["type"] == "table" for b in blocks)

    def test_pdf_add_font_failure_falls_back(self, tmp_path):
        """CJK 字体注册失败应回退 Helvetica 且不崩溃"""
        with patch("src.export_service._find_cjk_font", return_value=(str(tmp_path), "CJK")):
            out = export_pdf(EXTRA_DATA, EXTRA_META)
        assert out.startswith(b"%PDF")


# ===========================================================================
# workflow API 路由剩余分支（复用 api_engine / _make_auth_client 模式）
# ===========================================================================

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
    """创建已登录 TestClient（同 test_workflow 惯例：直连建用户 + 签发 JWT）"""
    import os
    import secrets as _secrets
    from fastapi.testclient import TestClient
    from api.auth import create_user, issue_token, SESSION_COOKIE, set_user_llm_config

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
    set_user_llm_config(user["id"], {
        "llm": {"api_key": "test-key", "base_url": "http://llm.test/v1", "model": "test-model"},
        "embedding": None,
    })
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, issue_token(user["id"]))
    return user, client


class TestWorkflowApiExtra:
    """workflow 路由剩余错误/降级分支补充"""

    def _create_project(self, client):
        r = client.post("/api/workflow/projects", json={"title": "接口测试", "interest": "朱雀2号"})
        assert r.status_code == 200
        return r.json()["project"]["id"]

    def test_run_stage_internal_error_500(self, api_engine):
        """阶段执行遇到非 ValueError 内部异常应 500"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "run_stage", side_effect=RuntimeError("boom")):
            with client:
                pid = self._create_project(client)
                r = client.post(f"/api/workflow/projects/{pid}/stages/1/run", json={"inputs": {}})
                assert r.status_code == 500

    def test_save_design_value_error_400(self, api_engine):
        """save_design 抛 ValueError 应 400"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "save_design", side_effect=ValueError("设计不存在")):
            with client:
                pid = self._create_project(client)
                r = client.post(f"/api/workflow/projects/{pid}/stages/3/save", json={
                    "research_questions": [], "hypotheses": [], "suggestion": "",
                })
                assert r.status_code == 400

    def test_save_design_internal_error_500(self, api_engine):
        """save_design 遇到非 ValueError 内部异常应 500"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "save_design", side_effect=RuntimeError("boom")):
            with client:
                pid = self._create_project(client)
                r = client.post(f"/api/workflow/projects/{pid}/stages/3/save", json={
                    "research_questions": [], "hypotheses": [], "suggestion": "",
                })
                assert r.status_code == 500

    def test_delete_internal_false_404(self, api_engine):
        """delete_project 返回 False（物理删除失败）应 404"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "delete_project", return_value=False):
            with client:
                pid = self._create_project(client)
                assert client.delete(f"/api/workflow/projects/{pid}").status_code == 404

    def test_run_all_already_completed_400(self, api_engine):
        """已完成全部 7 阶段的项目再次 run-all 应 400"""
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            pid = self._create_project(client)
            api_engine.run_all(pid)  # 直接驱动引擎完成全流程（mock agent，不触网）
            r = client.post(f"/api/workflow/projects/{pid}/run-all", json={"materials": []})
            assert r.status_code == 400
            assert "已全部生成完成" in r.json()["detail"]

    def test_export_missing_stage_404(self, api_engine):
        """导出时引擎抛 ValueError（无产出）应 404"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "export_project", side_effect=ValueError("阶段 1 暂无产出物")):
            with client:
                pid = self._create_project(client)
                r = client.get(f"/api/workflow/projects/{pid}/export?fmt=md")
                assert r.status_code == 404

    def test_polish_rejects_non_stage6(self, api_engine):
        """润色仅限写作阶段（stage 6），其它阶段应 400"""
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            pid = self._create_project(client)
            r = client.post(f"/api/workflow/projects/{pid}/stages/1/polish", json={
                "section": "引言", "content": "足够长的润色测试内容。", "instruction": "更学术",
            })
            assert r.status_code == 400

    def test_polish_internal_error_500(self, api_engine):
        """润色遇到内部异常应 500"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "polish_section", side_effect=RuntimeError("boom")):
            with client:
                pid = self._create_project(client)
                r = client.post(f"/api/workflow/projects/{pid}/stages/6/polish", json={
                    "section": "引言", "content": "足够长的润色测试内容。", "instruction": "更学术",
                })
                assert r.status_code == 500

    def _complete_three_stages(self, api_engine, pid):
        """推进并确认前 3 阶段，使研究设计（V1）可用"""
        for stage in range(1, 4):
            api_engine.run_stage(pid, stage, {"topic": "朱雀2号"})
            api_engine.approve_stage(pid, stage)

    def test_auto_iterate_requires_design_done_400(self, api_engine):
        """研究设计未完成时启动自动迭代应 400"""
        from api.main import app
        _, client = _make_auth_client(app)
        with client:
            pid = self._create_project(client)
            r = client.post(f"/api/workflow/projects/{pid}/auto-iterate", json={})
            assert r.status_code == 400
            assert "研究设计" in r.json()["detail"]

    def test_auto_iterate_start_success(self, api_engine):
        """设计完成后启动自动迭代应返回 started=True"""
        from api.main import app
        _, client = _make_auth_client(app)
        with patch.object(api_engine, "auto_iterate", return_value=[{"round": 1}]) as mock_ai:
            with client:
                pid = self._create_project(client)
                self._complete_three_stages(api_engine, pid)
                r = client.post(f"/api/workflow/projects/{pid}/auto-iterate", json={})
                assert r.status_code == 200
                assert r.json()["started"] is True
                mock_ai.assert_called_once()
