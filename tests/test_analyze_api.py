"""
云观星传 - 分析路由（/api/analyze）单元测试
覆盖进度回调分组、后台任务成功/失败路径、结果持久化与历史加载（Mock Pipeline）
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
def analyze_mod(tmp_path, monkeypatch):
    """导入分析路由模块，隔离全局状态与落盘目录"""
    with patch('src.pipeline.Pipeline'), patch('api.routes.analyze.Pipeline'):
        import api.routes.analyze as mod
        mod.pipeline_results.clear()
        mod.pipeline_status.clear()
        mod.pipeline_progress.clear()
        # 落盘目录指向临时目录，避免污染 data/results（mkdir：_save_result 失败会静默降级）
        fake_results = tmp_path / 'results'
        fake_results.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mod, 'RESULTS_DIR', fake_results)
        yield mod
        mod.pipeline_results.clear()
        mod.pipeline_status.clear()
        mod.pipeline_progress.clear()


def _fake_pipeline_result():
    """构造可 model_dump 的 Pipeline 结果 mock"""
    result = MagicMock()
    result.model_dump.return_value = {
        "topic": "嫦娥六号",
        "timestamp": "2026-09-02T12:00:00",
        "final_status": "passed",
        "iteration_count": 1,
    }
    return result


class TestProgressCallback:
    """进度回调测试"""

    def test_pre_iteration_steps_in_round_0(self, analyze_mod):
        """science/context 等基础步骤应归入第 0 轮（基础分析）"""
        cb = analyze_mod.make_progress_callback("t1")
        cb("science", "running", "分析中")
        progress = analyze_mod.pipeline_progress["t1"]
        assert len(progress["rounds"]) == 1
        assert progress["rounds"][0]["label"] == "基础分析"
        assert progress["rounds"][0]["steps"][0]["name"] == "science"
        assert "科学理解" in progress["rounds"][0]["steps"][0]["display_name"]

    def test_iteration_steps_in_own_round(self, analyze_mod):
        """strategy/evaluation 步骤应按 round_num 归入对应迭代轮"""
        cb = analyze_mod.make_progress_callback("t2")
        cb("strategy", "running", "策略生成中", round_num=2)
        progress = analyze_mod.pipeline_progress["t2"]
        # 第 0 轮未创建，直接落在第 2 轮
        assert len(progress["rounds"]) >= 3
        assert progress["rounds"][2]["label"] == "迭代第2轮"
        assert progress["rounds"][2]["steps"][0]["name"] == "strategy"

    def test_round_defaults_to_1_when_missing(self, analyze_mod):
        """迭代步骤未传 round_num 时默认第 1 轮"""
        cb = analyze_mod.make_progress_callback("t3")
        cb("evaluation", "running")
        progress = analyze_mod.pipeline_progress["t3"]
        assert progress["rounds"][1]["label"] == "迭代第1轮"

    def test_step_update_not_duplicate(self, analyze_mod):
        """同一步骤重复回调应更新而非追加"""
        cb = analyze_mod.make_progress_callback("t4")
        cb("science", "running", "开始")
        cb("science", "completed", "完成")
        steps = analyze_mod.pipeline_progress["t4"]["rounds"][0]["steps"]
        assert len(steps) == 1
        assert steps[0]["status"] == "completed"
        assert steps[0]["message"] == "完成"


class TestRunPipelineTask:
    """后台任务执行测试"""

    def test_success_marks_completed_and_saves(self, analyze_mod):
        """成功运行应置 completed、步骤收尾并落盘"""
        fake_result = _fake_pipeline_result()
        with patch.object(analyze_mod, 'Pipeline') as MockPipeline:
            MockPipeline.return_value.run.return_value = fake_result
            cb = analyze_mod.make_progress_callback("ok_task")
            analyze_mod.pipeline_progress["ok_task"] = {"rounds": [
                {"label": "基础分析", "steps": [
                    {"name": "science", "display_name": "科学理解", "status": "running", "message": ""},
                ]},
            ]}
            # 用真实回调让 run_pipeline_task 重新建回调也 OK，这里直接预置进度
            analyze_mod.run_pipeline_task("ok_task", "嫦娥六号", 2)

        assert analyze_mod.pipeline_status["ok_task"] == "completed"
        assert "ok_task" in analyze_mod.pipeline_results
        # running 步骤被标记 completed
        step = analyze_mod.pipeline_progress["ok_task"]["rounds"][0]["steps"][0]
        assert step["status"] == "completed"
        # 结果已落盘
        saved = list(analyze_mod.RESULTS_DIR.glob("ok_task.json"))
        assert len(saved) == 1
        assert json.loads(saved[0].read_text(encoding="utf-8"))["topic"] == "嫦娥六号"

    def test_failure_marks_error(self, analyze_mod):
        """异常应置 error 状态并将 running 步骤标记 error"""
        with patch.object(analyze_mod, 'Pipeline') as MockPipeline:
            MockPipeline.return_value.run.side_effect = RuntimeError("LLM 超时")
            analyze_mod.pipeline_progress["err_task"] = {"rounds": [
                {"label": "基础分析", "steps": [
                    {"name": "science", "display_name": "科学理解", "status": "running", "message": ""},
                ]},
            ]}
            analyze_mod.run_pipeline_task("err_task", "嫦娥六号", 2)

        assert "error" in analyze_mod.pipeline_status["err_task"]
        assert "LLM 超时" in analyze_mod.pipeline_status["err_task"]
        step = analyze_mod.pipeline_progress["err_task"]["rounds"][0]["steps"][0]
        assert step["status"] == "error"
        assert "LLM 超时" in step["message"]


class TestSaveAndLoadHistory:
    """持久化与历史加载测试"""

    def test_save_result_writes_json(self, analyze_mod):
        analyze_mod._save_result("task_x", {"topic": "天问三号"})
        f = analyze_mod.RESULTS_DIR / "task_x.json"
        assert f.exists()
        assert json.loads(f.read_text(encoding="utf-8"))["topic"] == "天问三号"

    def test_load_history_filters_task_prefix(self, analyze_mod):
        """只加载 task_*.json，过滤 parliament_/output_ 等其他产物"""
        (analyze_mod.RESULTS_DIR).mkdir(parents=True, exist_ok=True)
        (analyze_mod.RESULTS_DIR / "task_a.json").write_text(
            json.dumps({"topic": "A", "timestamp": "t1", "final_status": "passed", "iteration_count": 1}),
            encoding="utf-8")
        (analyze_mod.RESULTS_DIR / "parliament_b.json").write_text(
            json.dumps({"topic": "B"}), encoding="utf-8")
        (analyze_mod.RESULTS_DIR / "output_c.json").write_text(
            json.dumps({"topic": "C"}), encoding="utf-8")
        history = analyze_mod._load_history()
        task_ids = [h["task_id"] for h in history]
        assert "task_a" in task_ids
        assert "parliament_b" not in task_ids
        assert "output_c" not in task_ids

    def test_load_history_corrupt_file_skipped(self, analyze_mod):
        """损坏 JSON 文件应被跳过不崩溃"""
        analyze_mod.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (analyze_mod.RESULTS_DIR / "task_bad.json").write_text("{invalid json", encoding="utf-8")
        history = analyze_mod._load_history()
        assert all(h["task_id"] != "task_bad" for h in history)


class TestAnalyzeEndpoints:
    """HTTP 端点测试"""

    @pytest.fixture
    def client(self, analyze_mod):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_run_returns_task_id(self, client, analyze_mod):
        """POST /run 应返回 task_id 与 running 状态"""
        with patch.object(analyze_mod, 'run_pipeline_task'):
            resp = client.post("/api/analyze/run", json={"topic": "嫦娥六号", "max_iterations": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["task_id"].startswith("task_")
        assert "嫦娥六号" in data["message"]

    def test_status_unknown_task_404(self, client, analyze_mod):
        """查询不存在的任务应 404"""
        resp = client.get("/api/analyze/status/task_not_exists_999")
        assert resp.status_code == 404

    def test_status_with_progress(self, client, analyze_mod):
        """运行中任务应返回进度结构"""
        analyze_mod.pipeline_status["task_live"] = "running"
        analyze_mod.pipeline_progress["task_live"] = {"rounds": [
            {"label": "基础分析", "steps": [
                {"name": "science", "display_name": "科学理解", "status": "running", "message": ""},
            ]},
        ]}
        resp = client.get("/api/analyze/status/task_live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["has_result"] is False
        assert data["progress"]["rounds"][0]["steps"][0]["name"] == "science"

    def test_result_from_memory(self, client, analyze_mod):
        """内存中有结果应直接返回"""
        analyze_mod.pipeline_results["task_mem"] = {"topic": "内存结果"}
        analyze_mod.pipeline_status["task_mem"] = "completed"
        resp = client.get("/api/analyze/result/task_mem")
        assert resp.status_code == 200
        assert resp.json()["topic"] == "内存结果"

    def test_result_from_disk(self, client, analyze_mod):
        """内存无结果时应从磁盘回载"""
        analyze_mod.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (analyze_mod.RESULTS_DIR / "task_disk.json").write_text(
            json.dumps({"topic": "磁盘结果"}), encoding="utf-8")
        resp = client.get("/api/analyze/result/task_disk")
        assert resp.status_code == 200
        assert resp.json()["topic"] == "磁盘结果"
        # 回载后进入内存缓存
        assert "task_disk" in analyze_mod.pipeline_results

    def test_result_path_traversal_blocked(self, client, analyze_mod):
        """非法 task_id（含点/斜杠等不安全字符）应 400 防穿越"""
        # 合法字符集仅 [A-Za-z0-9_-]：点号用于路径穿越（..），斜杠被路由层拦截
        resp = client.get("/api/analyze/result/task_..%2F..%2Fsecret")
        assert resp.status_code in (400, 404)  # 路由层 404 或校验层 400 均视为拦截
        # 直接验证校验函数对穿越串的判定
        from api.routes.security import is_safe_task_id
        assert is_safe_task_id("../../etc/passwd") is False
        assert is_safe_task_id("task_20260101120000_a1b2c3") is True
        assert is_safe_task_id("task_x*") is False  # glob 元字符
        assert is_safe_task_id("") is False

    def test_result_not_found_404(self, client, analyze_mod):
        resp = client.get("/api/analyze/result/task_missing_404")
        assert resp.status_code == 404

    def test_history_merges_memory_and_disk(self, client, analyze_mod):
        """历史应合并磁盘记录与内存中未落盘的完成结果"""
        analyze_mod.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (analyze_mod.RESULTS_DIR / "task_h1.json").write_text(
            json.dumps({"topic": "磁盘", "timestamp": "t1", "final_status": "passed", "iteration_count": 1}),
            encoding="utf-8")
        analyze_mod.pipeline_status["task_h2"] = "completed"
        analyze_mod.pipeline_results["task_h2"] = {
            "topic": "内存", "timestamp": "t2", "final_status": "passed", "iteration_count": 2}
        resp = client.get("/api/analyze/history")
        assert resp.status_code == 200
        ids = [h["task_id"] for h in resp.json()["history"]]
        assert "task_h1" in ids
        assert "task_h2" in ids

    def test_results_list(self, client, analyze_mod):
        """results 应列出内存中的任务及状态"""
        analyze_mod.pipeline_results["task_l1"] = {"topic": "x"}
        analyze_mod.pipeline_status["task_l1"] = "completed"
        resp = client.get("/api/analyze/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        task = next(t for t in data["tasks"] if t["task_id"] == "task_l1")
        assert task["status"] == "completed"
