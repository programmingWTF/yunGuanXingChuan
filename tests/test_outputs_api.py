"""
云观星传 - 成果生成 API 路由单元测试
验证注册表、任务流转、结果持久化与磁盘回退逻辑
"""
import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def outputs_module():
    """导入成果路由模块，清空全局状态"""
    import api.routes.outputs as mod
    mod.outputs_results.clear()
    mod.outputs_status.clear()
    mod.outputs_progress.clear()
    yield mod
    mod.outputs_results.clear()
    mod.outputs_status.clear()
    mod.outputs_progress.clear()


class TestOutputTypes:
    """成果类型注册表测试"""

    def test_register_7_types(self, outputs_module):
        """应注册 7 类成果"""
        assert len(outputs_module.OUTPUT_TYPES) == 7

    def test_seven_real_generators(self, outputs_module):
        """7 个生成器全部为真实生成器"""
        for key in ["research_plan", "strategy_report", "press_release", "paper_outline", "science_script", "kg_report", "expression_adaptation"]:
            assert outputs_module.OUTPUT_TYPES[key]["real"] is True

    def test_no_placeholder_remaining(self, outputs_module):
        """无占位生成器"""
        placeholders = [k for k, v in outputs_module.OUTPUT_TYPES.items() if not v["real"]]
        assert placeholders == []


class TestPlaceholder:
    """占位生成器测试"""

    def test_placeholder_structure(self, outputs_module):
        """占位结果应包含 status=placeholder 与标题"""
        result = outputs_module._placeholder_result("expression_adaptation", "嫦娥六号")
        assert result["status"] == "placeholder"
        assert result["topic"] == "嫦娥六号"
        assert result["title"] == "表达适配建议"
        assert "sections" in result

    def test_unknown_type_placeholder(self, outputs_module):
        """未知类型占位应回退到类型名"""
        result = outputs_module._placeholder_result("unknown_xyz", "嫦娥六号")
        assert result["title"] == "unknown_xyz"


class TestSourceMaterial:
    """素材加载测试"""

    def test_no_source_returns_empty(self, outputs_module):
        """无 source_task_id 应返回空素材"""
        assert outputs_module._load_source_material(None) == {}

    def test_load_parliament_material(self, outputs_module, tmp_path):
        """应能从 parliament 结果文件加载素材"""
        outputs_module.RESULTS_DIR = tmp_path
        sample = {
            "task_id": "parl_20260801120000",
            "topic": "嫦娥六号",
            "final_report": {"one_line_takeaway": "test"},
            "final_strategies": {
                "pipeline_strategies": {"strategies": [{"strategy_id": "S001"}]},
                "pipeline_verification": [{"claim": "test"}],
            },
        }
        # 文件名尾部须含 task_id 前 8 位（parl_2026），供磁盘回退匹配
        f = tmp_path / "parliament_嫦娥六号_parl_2026.json"
        f.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

        material = outputs_module._load_source_material("parl_20260801120000")
        assert material["topic"] == "嫦娥六号"
        assert material["final_report"]["one_line_takeaway"] == "test"
        assert material["strategies"] == [{"strategy_id": "S001"}]
        assert material["verification_report"] == [{"claim": "test"}]


class TestOutputTask:
    """后台任务执行测试"""

    def test_placeholder_task_completes(self, outputs_module, tmp_path):
        """占位生成任务应同步完成并落盘（模拟临时占位类型）"""
        outputs_module.RESULTS_DIR = tmp_path
        # 临时注入一个占位类型
        outputs_module.OUTPUT_TYPES["_test_placeholder"] = {"name": "测试占位", "module": "测试", "description": "", "real": False}
        try:
            outputs_module.run_output_task("out_test_1", "_test_placeholder", "嫦娥六号", None)
            assert outputs_module.outputs_status["out_test_1"] == "completed"
            assert "out_test_1" in outputs_module.outputs_results

            payload = outputs_module.outputs_results["out_test_1"]
            assert payload["generator_type"] == "_test_placeholder"
            assert payload["status"] == "completed"
            assert payload["data"]["status"] == "placeholder"

            # 磁盘持久化
            files = list(tmp_path.glob("output_*.json"))
            assert len(files) == 1
            with open(files[0], "r", encoding="utf-8") as fp:
                disk_data = json.load(fp)
            assert disk_data["task_id"] == "out_test_1"
        finally:
            del outputs_module.OUTPUT_TYPES["_test_placeholder"]

    def test_unknown_type_errors(self, outputs_module, tmp_path):
        """未知成果类型应记录 error 状态"""
        outputs_module.RESULTS_DIR = tmp_path
        outputs_module.run_output_task("out_bad", "not_a_type", "嫦娥六号", None)
        assert outputs_module.outputs_status["out_bad"].startswith("error")

    def test_real_generator_dispatched(self, outputs_module, tmp_path):
        """真实生成器应调用 Agent（mock 掉 Agent 避免真实 LLM）"""
        outputs_module.RESULTS_DIR = tmp_path

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"topic": "嫦娥六号", "research_background": "mock"}

        with patch('src.agents.research_plan_agent.ResearchPlanAgent', return_value=mock_agent):
            outputs_module.run_output_task("out_real_1", "research_plan", "嫦娥六号", None)
            assert outputs_module.outputs_status["out_real_1"] == "completed"
            payload = outputs_module.outputs_results["out_real_1"]
            assert payload["data"]["research_background"] == "mock"

    def test_press_release_agent_dispatched(self, outputs_module, tmp_path):
        """press_release 应调用 PressReleaseAgent"""
        outputs_module.RESULTS_DIR = tmp_path
        mock_agent = MagicMock()
        mock_agent.run.return_value = {"topic": "嫦娥六号", "lead_suggestions": ["mock"]}

        with patch('src.agents.press_release_agent.PressReleaseAgent', return_value=mock_agent):
            outputs_module.run_output_task("out_pr", "press_release", "嫦娥六号", None)
            assert outputs_module.outputs_status["out_pr"] == "completed"
            assert outputs_module.outputs_results["out_pr"]["data"]["lead_suggestions"] == ["mock"]

    def test_paper_outline_agent_dispatched(self, outputs_module, tmp_path):
        """paper_outline 应调用 PaperOutlineAgent"""
        outputs_module.RESULTS_DIR = tmp_path
        mock_agent = MagicMock()
        mock_agent.run.return_value = {"topic": "嫦娥六号", "paper_title": "mock"}

        with patch('src.agents.paper_outline_agent.PaperOutlineAgent', return_value=mock_agent):
            outputs_module.run_output_task("out_po", "paper_outline", "嫦娥六号", None)
            assert outputs_module.outputs_status["out_po"] == "completed"
            assert outputs_module.outputs_results["out_po"]["data"]["paper_title"] == "mock"

    def test_kg_report_generator_dispatched(self, outputs_module, tmp_path):
        """kg_report 应调用数据驱动生成函数（不走 Agent/LLM）"""
        outputs_module.RESULTS_DIR = tmp_path

        with patch('src.agents.kg_report_generator.generate_kg_report', return_value={"topic": "嫦娥六号", "kg_summary": "mock"}):
            outputs_module.run_output_task("out_kg", "kg_report", "嫦娥六号", None)
            assert outputs_module.outputs_status["out_kg"] == "completed"
            assert outputs_module.outputs_results["out_kg"]["data"]["kg_summary"] == "mock"

    def test_science_script_real_generator_dispatched(self, outputs_module, tmp_path):
        """science_script 应调用真实 Agent 且透传 platform 给 input_data"""
        outputs_module.RESULTS_DIR = tmp_path

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"topic": "嫦娥六号", "platform": "B站", "shots": []}

        with patch('src.agents.science_script_agent.ScienceScriptAgent', return_value=mock_agent):
            outputs_module.run_output_task("out_script_1", "science_script", "嫦娥六号", None, "B站")
            assert outputs_module.outputs_status["out_script_1"] == "completed"
            payload = outputs_module.outputs_results["out_script_1"]
            assert payload["data"]["platform"] == "B站"
            # 校验 Agent 收到的 input_data 包含 platform
            call_input = mock_agent.run.call_args[0][0]
            assert call_input.get("platform") == "B站"


class TestStatusResult:
    """状态与结果查询测试"""

    def test_unknown_task(self, outputs_module):
        """未知任务返回 not_found"""
        import asyncio
        result = asyncio.run(outputs_module.get_output_status("unknown"))
        assert result["status"] == "not_found"
        assert result["has_result"] is False

    def test_completed_status(self, outputs_module):
        """完成状态查询"""
        outputs_module.outputs_status["task_done"] = "completed"
        outputs_module.outputs_results["task_done"] = {"topic": "测试"}
        import asyncio
        result = asyncio.run(outputs_module.get_output_status("task_done"))
        assert result["status"] == "completed"
        assert result["has_result"] is True

    def test_result_disk_fallback(self, outputs_module, tmp_path):
        """内存无结果时应从磁盘回退"""
        import asyncio

        outputs_module.RESULTS_DIR = tmp_path
        payload = {
            "task_id": "out_disk_1",
            "generator_type": "paper_outline",
            "name": "论文大纲",
            "topic": "嫦娥六号",
            "status": "completed",
            "data": {"status": "placeholder"},
        }
        f = tmp_path / "output_嫦娥六号_out_disk.json"
        f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = asyncio.run(outputs_module.get_output_result("out_disk_1"))
        assert result["data"]["status"] == "placeholder"

    def test_result_404(self, outputs_module, tmp_path):
        """不存在的结果应抛 404"""
        import asyncio
        from fastapi import HTTPException

        outputs_module.RESULTS_DIR = tmp_path
        with pytest.raises(HTTPException) as exc:
            asyncio.run(outputs_module.get_output_result("nope_12345678"))
        assert exc.value.status_code == 404


class TestExportFilename:
    """导出接口中文文件名编码测试"""

    def test_chinese_filename_uses_rfc5987(self, outputs_module):
        """中文文件名应走 filename*=UTF-8'' 编码，避免 latin-1 header 500"""
        import asyncio
        import re

        outputs_module.outputs_results["task_cn"] = {
            "task_id": "task_cn",
            "generator_type": "paper_outline",
            "name": "论文大纲",
            "topic": "嫦娥六号",
            "status": "completed",
            "data": {"status": "placeholder", "topic": "嫦娥六号", "sections": []},
        }
        resp = asyncio.run(outputs_module.export_output("task_cn", "markdown"))
        assert resp.status_code == 200
        cd = resp.headers["Content-Disposition"]
        assert "filename*=UTF-8''" in cd
        # header 中不应出现裸中文（RFC 5987 会 percent-encode）
        assert not re.search(r"[一-鿿]", cd)

    def test_ascii_filename_still_works(self, outputs_module):
        """ASCII 文件名正常导出"""
        import asyncio

        outputs_module.outputs_results["task_en"] = {
            "task_id": "task_en",
            "generator_type": "paper_outline",
            "name": "Paper Outline",
            "topic": "ChangE-6",
            "status": "completed",
            "data": {"status": "placeholder", "topic": "ChangE-6", "sections": []},
        }
        resp = asyncio.run(outputs_module.export_output("task_en", "markdown"))
        assert resp.status_code == 200
        assert "filename*=UTF-8''" in resp.headers["Content-Disposition"]


class TestExportFormatsEndpoint:
    """导出格式查询端点 HTTP 测试"""

    def test_formats_for_kg_report(self, outputs_module, tmp_path, monkeypatch):
        """kg_report 结果应含 kg_png 格式"""
        from fastapi.testclient import TestClient
        from api.main import app
        monkeypatch.setattr(outputs_module, "RESULTS_DIR", tmp_path)
        outputs_module.outputs_results["task_kg"] = {"generator_type": "kg_report", "topic": "嫦娥六号"}
        with TestClient(app) as client:
            r = client.get("/api/outputs/export-formats/task_kg")
        assert r.status_code == 200
        assert "kg_png" in r.json()["formats"]
        assert r.json()["generator_type"] == "kg_report"

    def test_formats_404(self, outputs_module, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from api.main import app
        monkeypatch.setattr(outputs_module, "RESULTS_DIR", tmp_path)
        with TestClient(app) as client:
            r = client.get("/api/outputs/export-formats/task_missing")
        assert r.status_code == 404

    def test_generate_endpoint_rejects_unknown_type(self, outputs_module, tmp_path, monkeypatch):
        """POST /generate 非法类型应 400"""
        from fastapi.testclient import TestClient
        from api.main import app
        monkeypatch.setattr(outputs_module, "RESULTS_DIR", tmp_path)
        with TestClient(app) as client:
            r = client.post("/api/outputs/generate", json={
                "generator_type": "bad_type", "topic": "嫦娥六号"})
        assert r.status_code == 400
