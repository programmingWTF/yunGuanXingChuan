"""成果路由 - 统一成果生成接口（Research Output Center）
支持 7 类成果生成器注册表 + 异步任务 + 进度上报 + 结果持久化
复用 parliament.py 的异步任务模式（BackgroundTasks + 全局 dict + 磁盘 JSON）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

router = APIRouter()

# 结果持久化目录（与 parliament 共用 data/results）
RESULTS_DIR = Path(__file__).parent.parent.parent / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 存储运行状态
outputs_results: Dict[str, dict] = {}
outputs_status: Dict[str, str] = {}
outputs_progress: Dict[str, dict] = {}

# ==========================================================================
# 生成器注册表：7 类成果
#   real=True   -> 真实生成器（调用 Agent）
#   real=False  -> 占位生成器（返回结构化"即将上线"结果）
# ==========================================================================

OUTPUT_TYPES = {
    "research_plan": {
        "name": "科学假设与研究计划",
        "module": "智能体",
        "description": "输入研究主题，生成研究背景/已有研究/研究空白/科学假设/方法/数据/步骤/可行性",
        "real": True,
    },
    "strategy_report": {
        "name": "国际传播策略报告",
        "module": "智能体",
        "description": "生成目标国家/受众/传播目标/叙事框架/推荐媒体/标题/关键词/风险/中外媒体差异",
        "real": True,
    },
    "press_release": {
        "name": "新闻传播建议稿",
        "module": "智能体",
        "description": "生成传播目标/推荐标题/导语建议/正文框架/采访对象/配图建议",
        "real": True,
    },
    "paper_outline": {
        "name": "论文大纲",
        "module": "智能体",
        "description": "生成 Title/Abstract/Introduction/Literature Review/Method/Result/Discussion/Future Work 框架",
        "real": True,
    },
    "science_script": {
        "name": "科普视频脚本",
        "module": "前端",
        "description": "生成多平台科普视频脚本（短视频/公众号/微博/B站/小红书）",
        "real": True,
    },
    "kg_report": {
        "name": "知识图谱报告",
        "module": "知识图谱",
        "description": "生成基于知识图谱的分析报告",
        "real": True,
    },
    "expression_adaptation": {
        "name": "表达适配建议",
        "module": "前端",
        "description": "生成中英对照术语/隐喻/表达建议表",
        "real": False,
    },
}


class OutputGenerateRequest(BaseModel):
    generator_type: str = "research_plan"
    topic: str = "嫦娥六号"
    source_task_id: Optional[str] = None  # 可选：复用某次 parliament/pipeline 结果作为素材
    platform: Optional[str] = None       # 可选：成果需要的平台参数（科普视频脚本等用到）


class OutputGenerateResponse(BaseModel):
    task_id: str
    status: str
    message: str


# ==========================================================================
# 生成器实现
# ==========================================================================

def _run_real_generator(generator_type: str, input_data: Dict) -> dict:
    """调用真实生成器生成成果（Agent 或数据驱动函数）"""
    if generator_type == "research_plan":
        from src.agents.research_plan_agent import ResearchPlanAgent
        result = ResearchPlanAgent().run(input_data)
    elif generator_type == "strategy_report":
        from src.agents.strategy_report_agent import StrategyReportAgent
        result = StrategyReportAgent().run(input_data)
    elif generator_type == "press_release":
        from src.agents.press_release_agent import PressReleaseAgent
        result = PressReleaseAgent().run(input_data)
    elif generator_type == "paper_outline":
        from src.agents.paper_outline_agent import PaperOutlineAgent
        result = PaperOutlineAgent().run(input_data)
    elif generator_type == "science_script":
        from src.agents.science_script_agent import ScienceScriptAgent
        result = ScienceScriptAgent().run(input_data)
    elif generator_type == "kg_report":
        # 数据驱动纯函数分支（不走 Agent/LLM，从知识图谱统计组装）
        from src.agents.kg_report_generator import generate_kg_report
        result = generate_kg_report(input_data)
    else:
        raise ValueError(f"未知生成器: {generator_type}")
    return result


def _placeholder_result(generator_type: str, topic: str) -> dict:
    """返回结构化占位结果（该成果生成器尚未实现）"""
    meta = OUTPUT_TYPES.get(generator_type, {})
    return {
        "topic": topic,
        "status": "placeholder",
        "title": meta.get("name", generator_type),
        "message": "该成果生成器尚未实现，敬请期待（架构已就绪，按议题逐个填充）",
        "sections": [],
        "evidence_sources": [],
    }


def _load_source_material(source_task_id: Optional[str]) -> Dict:
    """从已有结果文件加载生成素材（议会结果优先，pipeline 结果兜底）"""
    material: Dict = {}
    if not source_task_id:
        return material

    prefix = source_task_id[:8] if len(source_task_id) >= 8 else source_task_id
    # 议会结果：data/results/parliament_*.json
    for f in RESULTS_DIR.glob(f"parliament_*{prefix}*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("task_id") == source_task_id or f.stem.endswith(prefix):
                material["topic"] = data.get("topic", "")
                material["final_report"] = data.get("final_report", {})
                material["motions"] = data.get("motions", [])
                material["votes"] = data.get("votes", [])
                fs = data.get("final_strategies", {})
                material["science_facts"] = fs.get("pipeline_science_facts", {})
                material["context_analysis"] = fs.get("pipeline_context", {})
                material["strategies"] = fs.get("pipeline_strategies", {}).get("strategies", [])
                material["hypotheses"] = fs.get("pipeline_hypotheses", [])
                material["verification_report"] = fs.get("pipeline_verification", [])
                return material
        except Exception:
            continue

    # pipeline 结果：data/results/{task_id}.json
    result_file = RESULTS_DIR / f"{source_task_id}.json"
    if result_file.exists():
        try:
            with open(result_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            material["topic"] = data.get("topic", "")
            material["science_facts"] = data.get("science_facts", {})
            material["context_analysis"] = data.get("context_analysis", {})
            material["hypotheses"] = data.get("hypotheses", [])
            material["verification_report"] = data.get("verification_report", [])
            material["strategies"] = data.get("strategies", [])
            material["final_report"] = data.get("final_report", {})
        except Exception:
            pass

    return material


def run_output_task(task_id: str, generator_type: str, topic: str, source_task_id: Optional[str], platform: Optional[str] = None):
    """后台运行成果生成任务"""
    outputs_status[task_id] = "running"
    try:
        # 校验生成器类型
        if generator_type not in OUTPUT_TYPES:
            raise ValueError(f"未知成果类型: {generator_type}，可选: {', '.join(OUTPUT_TYPES.keys())}")

        # 组装素材
        input_data = {"topic": topic}
        if platform:
            input_data["platform"] = platform
        source_material = _load_source_material(source_task_id)
        input_data.update(source_material)
        input_data["topic"] = topic or input_data.get("topic", "")

        # 调生成器
        meta = OUTPUT_TYPES[generator_type]
        if meta["real"]:
            result = _run_real_generator(generator_type, input_data)
        else:
            result = _placeholder_result(generator_type, topic)

        # 统一包装
        payload = {
            "task_id": task_id,
            "generator_type": generator_type,
            "name": meta["name"],
            "topic": topic,
            "source_task_id": source_task_id,
            "created_at": datetime.now().isoformat(),
            "status": "completed",
            "data": result,
        }

        outputs_results[task_id] = payload
        outputs_status[task_id] = "completed"

        # 持久化到磁盘
        safe_name = topic.replace(" ", "_").replace("/", "_")[:20]
        out_path = RESULTS_DIR / f"output_{safe_name}_{task_id[:8]}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    except Exception as e:
        outputs_status[task_id] = f"error: {e}"


@router.get("/types")
async def list_output_types():
    """列出所有成果类型（前端卡片数据源）"""
    types = [
        {
            "generator_type": key,
            "name": meta["name"],
            "module": meta["module"],
            "description": meta["description"],
            "real": meta["real"],
        }
        for key, meta in OUTPUT_TYPES.items()
    ]
    return {"count": len(types), "types": types}


@router.post("/generate", response_model=OutputGenerateResponse)
async def generate_output(req: OutputGenerateRequest, background_tasks: BackgroundTasks):
    """异步生成成果"""
    if req.generator_type not in OUTPUT_TYPES:
        raise HTTPException(status_code=400, detail=f"未知成果类型: {req.generator_type}")
    task_id = f"out_{req.generator_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    background_tasks.add_task(run_output_task, task_id, req.generator_type, req.topic, req.source_task_id, req.platform)
    return OutputGenerateResponse(
        task_id=task_id,
        status="submitted",
        message=f"成果生成已提交: {OUTPUT_TYPES[req.generator_type]['name']}",
    )


@router.get("/status/{task_id}")
async def get_output_status(task_id: str):
    """查询成果生成任务状态"""
    if task_id not in outputs_status:
        return {"task_id": task_id, "status": "not_found", "has_result": False, "progress": None}
    return {
        "task_id": task_id,
        "status": outputs_status[task_id],
        "has_result": task_id in outputs_results,
        "progress": outputs_progress.get(task_id),
    }


@router.get("/result/{task_id}")
async def get_output_result(task_id: str):
    """获取成果生成结果（内存优先，回退磁盘）"""
    if task_id in outputs_results:
        return outputs_results[task_id]

    # 回退：从磁盘文件中查找（文件名含 task_id 前8位）
    prefix = task_id[:8] if len(task_id) >= 8 else task_id
    for f in RESULTS_DIR.glob(f"output_*{prefix}*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("task_id") == task_id or f.stem.endswith(prefix):
                outputs_results[task_id] = data
                return data
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="结果不存在或任务未完成")


@router.get("/history")
async def get_output_history():
    """获取成果生成历史记录"""
    history = []
    for f in sorted(RESULTS_DIR.glob("output_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            history.append({
                "task_id": data.get("task_id", f.stem),
                "generator_type": data.get("generator_type", ""),
                "name": data.get("name", ""),
                "topic": data.get("topic", ""),
                "created_at": data.get("created_at", ""),
                "status": data.get("status", ""),
            })
        except Exception:
            continue

    return {"count": len(history), "history": history[:50]}
