"""分析路由 - 运行完整 Pipeline
支持实时阶段进度上报 + 结果持久化
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio

from src.pipeline import Pipeline

router = APIRouter()

# 结果持久化目录
RESULTS_DIR = Path(__file__).parent.parent.parent / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 存储运行状态
pipeline_results: Dict[str, dict] = {}
pipeline_status: Dict[str, str] = {}
# 阶段进度：task_id -> { rounds: [ {label, steps: [...]} ] }
pipeline_progress: Dict[str, dict] = {}

# Pipeline 阶段定义
PRE_ITERATION_STEPS = ["science", "context", "hypothesis", "verification"]
ITERATION_STEPS = ["strategy", "evaluation"]

STEP_NAMES = {
    "science": "🔬 科学理解",
    "context": "🌍 语境分析",
    "hypothesis": "💡 假设生成",
    "verification": "✅ 事实校验",
    "strategy": "📋 策略转译",
    "evaluation": "🏆 评测迭代",
}


class AnalyzeRequest(BaseModel):
    topic: str = "嫦娥六号"
    max_iterations: int = 3


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str
    message: str


def make_progress_callback(task_id: str):
    """创建进度回调函数，供 Pipeline 调用
    
    进度结构：
    {
      "rounds": [
        {"label": "基础分析", "steps": [{name, display_name, status, message}]},
        {"label": "迭代第1轮", "steps": [...]},
        {"label": "迭代第2轮", "steps": [...]},
      ]
    }
    """
    def callback(step: str, status: str, message: str = "", round_num: int = 0):
        if task_id not in pipeline_progress:
            pipeline_progress[task_id] = {"rounds": []}
        progress = pipeline_progress[task_id]

        # 确定属于哪个 round
        if step in PRE_ITERATION_STEPS:
            target_round = 0
            round_label = "基础分析"
        else:
            target_round = round_num if round_num > 0 else 1
            round_label = f"迭代第{target_round}轮"

        # 确保 round 存在
        while len(progress["rounds"]) <= target_round:
            progress["rounds"].append({"label": "", "steps": []})
        progress["rounds"][target_round]["label"] = round_label

        # 更新或添加步骤
        steps = progress["rounds"][target_round]["steps"]
        existing = next((s for s in steps if s["name"] == step), None)
        if existing:
            existing["status"] = status
            existing["message"] = message
        else:
            steps.append({
                "name": step,
                "display_name": STEP_NAMES.get(step, step),
                "status": status,
                "message": message,
            })
    return callback


@router.post("/run", response_model=AnalyzeResponse)
async def run_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    启动分析任务（异步）
    """
    task_id = f"task_{request.topic}_{len(pipeline_results)}"
    pipeline_status[task_id] = "running"
    pipeline_progress[task_id] = {"rounds": []}

    # 在后台运行 Pipeline
    background_tasks.add_task(run_pipeline_task, task_id, request.topic, request.max_iterations)

    return AnalyzeResponse(
        task_id=task_id,
        status="running",
        message=f"开始分析议题: {request.topic}"
    )


def run_pipeline_task(task_id: str, topic: str, max_iterations: int):
    """后台运行 Pipeline，带进度回调"""
    try:
        progress_cb = make_progress_callback(task_id)
        pipeline = Pipeline(max_iterations=max_iterations, progress_callback=progress_cb)
        result = pipeline.run(topic)
        result_dict = result.model_dump()
        pipeline_results[task_id] = result_dict
        pipeline_status[task_id] = "completed"
        # 标记所有步骤完成
        if task_id in pipeline_progress:
            for rnd in pipeline_progress[task_id].get("rounds", []):
                for s in rnd["steps"]:
                    if s["status"] != "error":
                        s["status"] = "completed"
        # 持久化到磁盘
        _save_result(task_id, result_dict)
    except Exception as e:
        pipeline_status[task_id] = f"error: {str(e)}"
        # 标记当前步骤出错
        if task_id in pipeline_progress:
            for rnd in pipeline_progress[task_id].get("rounds", []):
                for s in rnd["steps"]:
                    if s["status"] == "running":
                        s["status"] = "error"
                        s["message"] = str(e)


def _save_result(task_id: str, result_dict: dict):
    """将结果保存到磁盘 JSON 文件"""
    try:
        file_path = RESULTS_DIR / f"{task_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"保存结果失败: {e}")


def _load_history() -> List[dict]:
    """加载所有历史结果摘要"""
    history = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            history.append({
                "task_id": f.stem,
                "topic": data.get("topic", ""),
                "timestamp": data.get("timestamp", ""),
                "final_status": data.get("final_status", ""),
                "iteration_count": data.get("iteration_count", 0),
            })
        except Exception:
            pass
    return history


@router.post("/run-sync")
async def run_analysis_sync(request: AnalyzeRequest):
    """
    同步运行分析（等待完成）
    """
    try:
        pipeline = Pipeline(max_iterations=request.max_iterations)
        result = pipeline.run(request.topic)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态（含阶段进度）"""
    if task_id not in pipeline_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    progress = pipeline_progress.get(task_id, {"rounds": []})

    return {
        "task_id": task_id,
        "status": pipeline_status[task_id],
        "has_result": task_id in pipeline_results,
        "progress": progress,
    }


@router.get("/result/{task_id}")
async def get_task_result(task_id: str):
    """获取任务结果（内存或磁盘）"""
    if task_id in pipeline_results:
        return pipeline_results[task_id]
    # 尝试从磁盘加载
    file_path = RESULTS_DIR / f"{task_id}.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pipeline_results[task_id] = data
        return data
    raise HTTPException(status_code=404, detail="结果不存在")


@router.get("/history")
async def get_history():
    """获取历史分析记录"""
    # 合并内存中的 + 磁盘上的
    disk_history = _load_history()
    # 内存中已完成但不在磁盘上的（刚完成还没写入的情况）
    for tid, status in pipeline_status.items():
        if status == "completed" and tid in pipeline_results:
            if not any(h["task_id"] == tid for h in disk_history):
                r = pipeline_results[tid]
                disk_history.insert(0, {
                    "task_id": tid,
                    "topic": r.get("topic", ""),
                    "timestamp": r.get("timestamp", ""),
                    "final_status": r.get("final_status", ""),
                    "iteration_count": r.get("iteration_count", 0),
                })
    return {"history": disk_history}


@router.get("/results")
async def list_results():
    """列出所有结果"""
    return {
        "count": len(pipeline_results),
        "tasks": [
            {"task_id": tid, "status": pipeline_status.get(tid, "unknown")}
            for tid in pipeline_results
        ]
    }
