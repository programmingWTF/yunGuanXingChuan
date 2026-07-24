"""
云观星传 - 认知议会 API 路由单元测试
验证历史记录加载、磁盘回退、进度回调等逻辑
"""
import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def parliament_module():
    """导入议会路由模块"""
    with patch('src.pipeline.CognitiveParliament'):
        import api.routes.parliament as mod
        # 重置全局状态
        mod.parliament_results.clear()
        mod.parliament_status.clear()
        mod.parliament_progress.clear()
        yield mod
        mod.parliament_results.clear()
        mod.parliament_status.clear()
        mod.parliament_progress.clear()


class TestParliamentCallback:
    """进度回调机制测试"""

    def test_callback_initializes_phases(self, parliament_module):
        """回调创建时应初始化所有阶段为 pending"""
        callback = parliament_module.make_parliament_callback("test_task_001")
        progress = parliament_module.parliament_progress["test_task_001"]

        assert len(progress["phases"]) == 3
        assert progress["current_round"] == 0
        assert progress["total_rounds"] == 0

        # 所有阶段初始为 pending
        for phase in progress["phases"]:
            assert phase["status"] == "pending"

    def test_callback_updates_phase_status(self, parliament_module):
        """回调应正确更新阶段状态"""
        callback = parliament_module.make_parliament_callback("test_task_002")

        # 模拟 opening 阶段完成
        callback("opening", "running", "开幕中...")
        progress = parliament_module.parliament_progress["test_task_002"]
        opening = next(p for p in progress["phases"] if p["key"] == "opening")
        assert opening["status"] == "running"

        callback("opening", "completed", "开幕完成")
        assert opening["status"] == "completed"

    def test_callback_updates_sub_steps(self, parliament_module):
        """回调应正确更新子步骤"""
        callback = parliament_module.make_parliament_callback("test_task_003")

        callback("opening.scientist_report", "running", "Scientist 报告中...")
        progress = parliament_module.parliament_progress["test_task_003"]
        opening = next(p for p in progress["phases"] if p["key"] == "opening")
        sci_step = next(s for s in opening["sub_steps"] if s["key"] == "scientist_report")
        assert sci_step["status"] == "running"

        callback("opening.scientist_report", "completed", "完成")
        assert sci_step["status"] == "completed"

    def test_callback_tracks_debate_rounds(self, parliament_module):
        """回调应正确跟踪辩论轮次"""
        callback = parliament_module.make_parliament_callback("test_task_004")

        callback("debate", "running", "第1轮辩论中...")
        progress = parliament_module.parliament_progress["test_task_004"]
        assert progress["current_round"] == 1

        callback("debate", "running", "第2轮辩论中...")
        assert progress["current_round"] == 2
        assert progress["total_rounds"] == 2

    def test_callback_adds_debate_speakers(self, parliament_module):
        """辩论阶段应动态添加发言者子步骤"""
        callback = parliament_module.make_parliament_callback("test_task_005")

        callback("debate.speaker:scientist", "running", "第1轮辩论中...")
        progress = parliament_module.parliament_progress["test_task_005"]
        debate = next(p for p in progress["phases"] if p["key"] == "debate")
        assert len(debate["sub_steps"]) == 1
        assert "scientist" in debate["sub_steps"][0]["key"]

    def test_callback_pipeline_sub_steps(self, parliament_module):
        """Pipeline 阶段子步骤更新"""
        callback = parliament_module.make_parliament_callback("test_task_006")

        callback("pipeline.search", "running", "搜索中...")
        progress = parliament_module.parliament_progress["test_task_006"]
        pipeline = next(p for p in progress["phases"] if p["key"] == "pipeline")
        search_step = next(s for s in pipeline["sub_steps"] if s["key"] == "search")
        assert search_step["status"] == "running"

        callback("pipeline.search", "completed", "搜索完成")
        assert search_step["status"] == "completed"


class TestParliamentResultRetrieval:
    """结果获取测试（内存 + 磁盘回退）"""

    def test_in_memory_result(self, parliament_module):
        """内存中的结果直接返回"""
        parliament_module.parliament_results["task_123"] = {
            "task_id": "task_123", "topic": "测试", "total_rounds": 3
        }
        # 模拟 FastAPI 路由调用
        import asyncio
        result = asyncio.run(parliament_module.get_parliament_result("task_123"))
        assert result["topic"] == "测试"

    def test_disk_fallback(self, parliament_module, tmp_path):
        """内存中无结果时从磁盘加载"""
        # 写入磁盘文件
        task_data = {
            "task_id": "parl_20260101120000",
            "topic": "嫦娥六号",
            "total_rounds": 4,
            "votes": [],
            "motions": [],
        }
        disk_file = tmp_path / "parliament_嫦娥六号_parl_202.json"
        with open(disk_file, "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False)

        # 临时替换 RESULTS_DIR
        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path

        try:
            import asyncio
            result = asyncio.run(
                parliament_module.get_parliament_result("parl_20260101120000")
            )
            assert result["topic"] == "嫦娥六号"
            assert result["total_rounds"] == 4
            # 应缓存到内存
            assert "parl_20260101120000" in parliament_module.parliament_results
        finally:
            parliament_module.RESULTS_DIR = original_dir

    def test_not_found_raises_404(self, parliament_module, tmp_path):
        """找不到结果时抛 404"""
        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path

        try:
            import asyncio
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(
                    parliament_module.get_parliament_result("nonexistent_task")
                )
            assert exc_info.value.status_code == 404
        finally:
            parliament_module.RESULTS_DIR = original_dir


class TestParliamentHistory:
    """历史记录列表测试"""

    def test_history_reads_from_disk(self, parliament_module, tmp_path):
        """历史列表从磁盘文件读取"""
        # 创建多个记录文件
        for i in range(3):
            data = {
                "task_id": f"parl_2026010{i}120000",
                "topic": f"议题{i}",
                "total_rounds": i + 2,
                "votes": [{"motion_id": f"M{j}", "result": "passed"} for j in range(i + 1)],
                "motions": [{"motion_id": f"M{j}"} for j in range(i + 1)],
                "minority_opinions": [],
                "final_strategies": {"pipeline_evaluation": {"factual_accuracy": 75 + i}},
                "completed_at": f"2026-01-0{i}T12:00:00",
            }
            f = tmp_path / f"parliament_议题{i}_parl_2026010{i}.json"
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)

        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path

        try:
            import asyncio
            result = asyncio.run(parliament_module.get_parliament_history())
            assert len(result["history"]) == 3
            assert result["summary"]["total_runs"] == 3
            assert result["summary"]["total_votes"] == 6  # 1+2+3
        finally:
            parliament_module.RESULTS_DIR = original_dir

    def test_empty_history(self, parliament_module, tmp_path):
        """无记录时返回空列表"""
        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path

        try:
            import asyncio
            result = asyncio.run(parliament_module.get_parliament_history())
            assert result["history"] == []
            assert result["summary"]["total_runs"] == 0
        finally:
            parliament_module.RESULTS_DIR = original_dir

    def test_corrupted_file_skipped(self, parliament_module, tmp_path):
        """损坏的文件应被跳过"""
        # 正常文件
        good_data = {
            "task_id": "parl_good", "topic": "正常", "total_rounds": 2,
            "votes": [], "motions": [], "minority_opinions": [],
            "final_strategies": {}, "completed_at": "2026-01-01T12:00:00",
        }
        with open(tmp_path / "parliament_正常_parl_good.json", "w", encoding="utf-8") as f:
            json.dump(good_data, f, ensure_ascii=False)

        # 损坏文件
        with open(tmp_path / "parliament_损坏_parl_bad00.json", "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")

        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path

        try:
            import asyncio
            result = asyncio.run(parliament_module.get_parliament_history())
            # 只有正常文件被读取
            assert len(result["history"]) == 1
            assert result["history"][0]["topic"] == "正常"
        finally:
            parliament_module.RESULTS_DIR = original_dir


class TestParliamentStatus:
    """任务状态查询测试"""

    def test_running_status(self, parliament_module):
        """运行中状态查询"""
        parliament_module.parliament_status["task_run"] = "running"
        parliament_module.parliament_progress["task_run"] = {
            "phases": [], "current_round": 1, "total_rounds": 3
        }

        import asyncio
        result = asyncio.run(parliament_module.get_parliament_status("task_run"))
        assert result["status"] == "running"
        assert result["has_result"] is False
        assert result["progress"]["current_round"] == 1

    def test_completed_status(self, parliament_module):
        """完成状态查询"""
        parliament_module.parliament_status["task_done"] = "completed"
        parliament_module.parliament_results["task_done"] = {"topic": "测试"}

        import asyncio
        result = asyncio.run(parliament_module.get_parliament_status("task_done"))
        assert result["status"] == "completed"
        assert result["has_result"] is True

    def test_unknown_task(self, parliament_module):
        """未知任务返回 not_found"""
        import asyncio
        result = asyncio.run(parliament_module.get_parliament_status("unknown"))
        assert result["status"] == "not_found"
        assert result["has_result"] is False
