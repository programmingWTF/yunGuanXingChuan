"""认知议会路由 - 运行 Cognitive Parliament
支持异步召集议会 + 实时进度上报 + 辩论记录持久化
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
from uuid import uuid4

from api.routes.security import is_safe_task_id

router = APIRouter()

# 结果持久化目录
RESULTS_DIR = Path(__file__).parent.parent.parent / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 存储运行状态
parliament_results: Dict[str, dict] = {}
parliament_status: Dict[str, str] = {}
parliament_progress: Dict[str, dict] = {}
parliament_stop_flags: set = set()  # 记录被用户请求停止的 task_id


def _safe_name(name: str, max_len: int = 20) -> str:
    """清洗文件名：替换 Windows 非法字符（<>:\"/\\|?* 及控制字符），避免写盘失败"""
    import re
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return cleaned.strip(" ._").replace(" ", "_")[:max_len]

# 议会阶段定义（完整声明，含子步骤——前端据此显示精细化进度条）
PARLIAMENT_PHASES: list[dict] = [
    {
        "key": "opening", "label": "开幕报告", "icon": "🏛️",
        "sub_steps": [
            {"key": "scientist_report", "label": "Scientist 科学事实扫描", "icon": "🔬"},
            {"key": "humanist_report",  "label": "Humanist 文化敏感审查", "icon": "🎭"},
            {"key": "motions_generated", "label": "生成初始动议", "icon": "📝"},
        ],
    },
    {
        "key": "debate", "label": "多轮辩论", "icon": "⚔️",
        "sub_steps": None,  # 动态
    },
    {
        "key": "pipeline", "label": "Pipeline 校验+策略", "icon": "🔍",
        "sub_steps": [
            {"key": "search",       "label": "Tavily + 百炼 联网搜索",      "icon": "🌐"},
            {"key": "verification", "label": "RAG + KG + Wikidata 四路校验", "icon": "✅"},
        ],
        # strategy:rN / evaluation:rN 动态添加
    },
    {
        "key": "summary", "label": "最终总结报告", "icon": "📝",
        "sub_steps": [
            {"key": "report", "label": "结构化总结生成", "icon": "📊"},
        ],
    },
]


class ParliamentRequest(BaseModel):
    topic: str = "嫦娥六号"
    max_rounds: Optional[int] = None  # 辩论最大轮次
    max_pipeline_rounds: Optional[int] = None  # Pipeline 评测最大轮次


class ParliamentResponse(BaseModel):
    task_id: str
    status: str
    message: str


def make_parliament_callback(task_id: str):
    """创建议会进度回调——初始化全部阶段+子步骤为 pending"""
    phases: list[dict] = []
    for p in PARLIAMENT_PHASES:
        phase = {"key": p["key"], "label": p["label"], "icon": p["icon"],
                 "status": "pending", "message": "", "sub_steps": []}
        if p["sub_steps"] is not None:
            for ss in p["sub_steps"]:
                phase["sub_steps"].append({
                    "key": ss["key"], "status": "pending",
                    "label": ss["label"], "icon": ss["icon"],
                    "detail": "", "full_content": "",
                })
        elif p["key"] == "debate":
            phase["sub_steps"] = []  # 动态添加发言者
        phases.append(phase)

    parliament_progress[task_id] = {
        "phases": phases,
        "current_round": 0,
        "total_rounds": 0,
        "pipeline_round": 0,
    }

    def callback(step: str, status: str, message: str = "", *args):
        # 解析 full_content: 第4个位置参数即为发言全文
        full_content = ""
        if len(args) >= 1 and isinstance(args[0], str):
            full_content = args[0]

        progress = parliament_progress.get(task_id)
        if not progress:
            return
        # 解析 step: "phase.sub_step" 格式
        parts = step.split(".", 1)
        phase_key = parts[0]
        sub_key = parts[1] if len(parts) > 1 else ""

        for phase in progress["phases"]:
            if phase["key"] != phase_key:
                continue

            # 辩论轮次跟踪
            if phase_key == "debate":
                import re
                m = re.search(r"(\d+)", message)
                if m:
                    rnum = int(m.group(1))
                    progress["current_round"] = rnum
                    progress["total_rounds"] = max(progress["total_rounds"], rnum)

                if sub_key and status == "running":
                    # 动态添加发言者子步骤
                    # 解析 "speaker:R1:scientist" 格式
                    label = sub_key
                    icon = "💬"
                    key_parts = sub_key.split(":")
                    if len(key_parts) >= 3:
                        agent_name = key_parts[2]
                        round_str = key_parts[1]  # e.g. "R1"
                        icon = {"scientist": "🔬", "skeptic": "🔍", "humanist": "🎭",
                                "strategist": "📋", "evaluator": "🏆"}.get(agent_name, "💬")
                        label = f"{round_str} {agent_name} ：发言"
                    phase["sub_steps"].append({
                        "key": sub_key, "status": "running",
                        "label": label,
                        "icon": icon, "detail": message, "full_content": "",
                    })
                    phase["status"] = "running"
                elif sub_key and status == "completed":
                    # 标记对应发言者完成
                    for ss in reversed(phase["sub_steps"]):
                        if ss["key"] == sub_key and ss["status"] == "running":
                            ss["status"] = "completed"
                            ss["detail"] = message
                            if full_content:
                                ss["full_content"] = full_content
                            break
                elif not sub_key:
                    # 阶段级别状态更新
                    phase["status"] = status
                    phase["message"] = message
                continue

            # Pipeline 阶段：支持动态 round-based sub_steps
            if phase_key == "pipeline":
                import re
                # 检查是否是 round-based key (strategy:r1, evaluation:r2)
                round_match = re.match(r'(strategy|evaluation):r(\d+)', sub_key)
                if round_match:
                    step_type = round_match.group(1)
                    rnum = int(round_match.group(2))
                    progress["pipeline_round"] = max(progress.get("pipeline_round", 0), rnum)

                    # 查找或创建动态 sub_step
                    existing = None
                    for ss in phase["sub_steps"]:
                        if ss["key"] == sub_key:
                            existing = ss
                            break
                    if not existing:
                        icon = "📋" if step_type == "strategy" else "📊"
                        lbl = f"R{rnum} {'Strategy 策略生成' if step_type == 'strategy' else 'Evaluator 五维评测'}"
                        existing = {"key": sub_key, "status": "pending",
                                    "label": lbl, "icon": icon,
                                    "detail": "", "full_content": ""}
                        phase["sub_steps"].append(existing)

                    existing["status"] = status
                    existing["detail"] = message
                    if full_content:
                        existing["full_content"] = full_content

                    # 检查是否所有子步骤完成
                    all_done = all(s["status"] == "completed" for s in phase["sub_steps"])
                    if all_done:
                        phase["status"] = "completed"
                else:
                    # 静态 sub_step (search, verification)
                    for ss in phase.get("sub_steps", []):
                        if ss["key"] == sub_key:
                            ss["status"] = status
                            ss["detail"] = message
                            if full_content:
                                ss["full_content"] = full_content
                            break
                    # 检查是否所有子步骤完成
                    all_done = all(s["status"] == "completed" for s in phase["sub_steps"])
                    if all_done and len(phase["sub_steps"]) >= 2:
                        phase["status"] = "completed"
                if not sub_key:
                    phase["status"] = status
                    phase["message"] = message
                continue

            # 其他阶段 (opening)
            if not sub_key:
                phase["status"] = status
                phase["message"] = message
            else:
                for ss in phase.get("sub_steps", []):
                    if ss["key"] == sub_key:
                        ss["status"] = status
                        ss["detail"] = message
                        if full_content:
                            ss["full_content"] = full_content
                        break
                all_done = all(s["status"] == "completed" for s in phase.get("sub_steps", []))
                if all_done:
                    phase["status"] = "completed"
            break

    return callback


def run_parliament_task(task_id: str, topic: str, max_rounds: Optional[int], max_pipeline_rounds: Optional[int]):
    """后台运行议会任务"""
    from src.pipeline import CognitiveParliament

    parliament_status[task_id] = "running"
    try:
        # 加载本地科学数据
        science_facts = None
        try:
            from src.knowledge.data_loader import get_data_loader
            facts_list = get_data_loader().load_science_facts(topic)
            if facts_list:
                science_facts = facts_list[0]  # load_science_facts 返回 List[Dict]，取第一个
        except Exception:
            pass

        parliament = CognitiveParliament(
            max_rounds=max_rounds,
            max_pipeline_rounds=max_pipeline_rounds,
            progress_callback=make_parliament_callback(task_id),
            stop_check=lambda: task_id in parliament_stop_flags,
        )
        transcript = parliament.convene(
            topic=topic,
            science_facts=science_facts,
        )

        result = transcript.model_dump()
        result["task_id"] = task_id
        result["task_status"] = "stopped" if task_id in parliament_stop_flags else "completed"
        # 保存进度数据（供历史任务加载时显示流程图）
        result["progress_snapshot"] = parliament_progress.get(task_id)

        # 持久化到磁盘（成功后再置状态，避免写盘失败时状态错乱）
        safe_name = _safe_name(topic)
        out_path = RESULTS_DIR / f"parliament_{safe_name}_{task_id[:8]}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        parliament_results[task_id] = result
        # 若用户请求过停止，保留 stopped 状态而不是覆盖为 completed
        if task_id in parliament_stop_flags:
            parliament_status[task_id] = "stopped"
        else:
            parliament_status[task_id] = "completed"

    except Exception as e:
        parliament_status[task_id] = f"error: {e}"


@router.post("/convene", response_model=ParliamentResponse)
async def convene_parliament(req: ParliamentRequest, background_tasks: BackgroundTasks):
    """异步召集认知议会"""
    task_id = f"parl_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
    background_tasks.add_task(run_parliament_task, task_id, req.topic, req.max_rounds, req.max_pipeline_rounds)
    return ParliamentResponse(
        task_id=task_id,
        status="submitted",
        message=f"认知议会已提交: {req.topic}",
    )


@router.post("/stop/{task_id}")
async def stop_parliament(task_id: str):
    """停止运行中的议会任务"""
    if task_id in parliament_status and parliament_status[task_id] == "running":
        parliament_status[task_id] = "stopped"
        parliament_stop_flags.add(task_id)  # 后台任务据此提前中断辩论循环
        return {"task_id": task_id, "status": "stopped", "message": "任务已标记停止，将提前结束"}
    return {"task_id": task_id, "status": parliament_status.get(task_id, "not_found"), "message": "任务不在运行中"}


@router.get("/status/{task_id}")
async def get_parliament_status(task_id: str):
    """查询议会任务状态"""
    if task_id not in parliament_status:
        return {"task_id": task_id, "status": "not_found", "has_result": False, "progress": None}
    return {
        "task_id": task_id,
        "status": parliament_status[task_id],
        "has_result": task_id in parliament_results,
        "progress": parliament_progress.get(task_id),
    }


@router.get("/result/{task_id}")
async def get_parliament_result(task_id: str):
    """获取议会辩论记录（内存优先，回退磁盘）"""
    if task_id in parliament_results:
        return parliament_results[task_id]

    # 防路径穿越/glob 注入：task_id 参与 glob 模式拼接
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="非法的 task_id 格式")

    # 回退：从磁盘文件中查找（文件名含 task_id 前8位，但必须精确匹配 task_id）
    # 注意：不能用 f.stem.endswith(prefix) 判断——task_id[:8] 对 parl_ 前缀任务恒相同，
    #       会误匹配到同年的其他任务。必须读取文件内容精确比对 task_id。
    prefix = task_id[:8] if len(task_id) >= 8 else task_id
    for f in RESULTS_DIR.glob(f"parliament_*{prefix}*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("task_id") == task_id:
                # 缓存到内存
                parliament_results[task_id] = data
                return data
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="结果不存在或任务未完成")


@router.get("/history")
async def get_parliament_history():
    """获取议会历史记录 + 全局统计"""
    history = []
    all_motions = 0; all_votes = 0; all_minority = 0; all_rounds = 0; all_scores = []

    for f in sorted(RESULTS_DIR.glob("parliament_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            votes = data.get("votes", [])
            motions = data.get("motions", [])
            minority = data.get("minority_opinions", [])
            total_rounds = data.get("total_rounds", 0)
            passed = sum(1 for v in votes if v.get("result") == "passed")
            pass_rate = round(passed / len(votes) * 100) if votes else 0
            fs = data.get("final_strategies", {})
            pe = fs.get("pipeline_evaluation", {})
            avg_score = None
            if pe and isinstance(pe, dict):
                vals = [v for v in pe.values() if isinstance(v, (int, float))]
                if vals: avg_score = round(sum(vals) / len(vals), 1)
            history.append({
                "task_id": data.get("task_id", f.stem),
                "topic": data.get("topic", ""),
                "total_rounds": total_rounds,
                "motion_count": len(motions),
                "vote_count": len(votes),
                "passed_count": passed,
                "pass_rate": pass_rate,
                "minority_count": len(minority),
                "avg_score": avg_score,
                "completed_at": data.get("completed_at", ""),
            })
            all_motions += len(motions); all_votes += len(votes)
            all_minority += len(minority); all_rounds += total_rounds
            if avg_score is not None: all_scores.append(avg_score)
        except Exception:
            continue

    n = len(history)
    summary = {
        "total_runs": n,
        "avg_rounds": round(all_rounds / n, 1) if n else 0,
        "avg_motions": round(all_motions / n, 1) if n else 0,
        "avg_minority": round(all_minority / n, 1) if n else 0,
        "avg_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        "total_votes": all_votes,
    }
    return {"history": history[:20], "summary": summary}


@router.get("/records")
async def list_parliament_records():
    """列出所有议会记录文件"""
    records = []
    for f in sorted(RESULTS_DIR.glob("parliament_*.json"), reverse=True):
        records.append({"filename": f.name, "path": str(f)})
    return {"count": len(records), "records": records}
