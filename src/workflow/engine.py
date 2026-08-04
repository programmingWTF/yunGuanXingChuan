"""
科研流程编排引擎 - 7 智能体工作流状态机

职责：
- 创建/查询科研项目（委托 ProjectStore）
- 按阶段执行对应智能体（注入知识库/搜索上下文，产出物落盘）
- 研究者确认（approve）后推进到下一阶段
- 汇总导出（JSON/Markdown）

设计原则：
- 智能体隐藏在流程背后：前端只感知"科研流程"，不感知 Agent
- 知识库/搜索注入全部 try/except 降级：外部服务不可达时不影响主流程
- 旧流水线（src/pipeline.py + 认知议会）保留向后兼容，本引擎为独立新路径
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.schemas import ResearchProject, StageRecord, StageStatus
from src.workflow.stages import WorkflowStage, STAGE_META, get_stage_meta_list
from src.workflow.project import ProjectStore, get_project_store

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """7 智能体科研流程编排引擎"""

    def __init__(self, store: Optional[ProjectStore] = None, agents: Optional[Dict[int, Any]] = None):
        self.store = store or get_project_store()
        # agents: {stage: BaseAgent}；不传则延迟构建（避免导入环 + 测试可注入 mock）
        self._agents = agents or {}

    # ------------------------------------------------------------------
    # Agent 构建（延迟导入，避免循环依赖）
    # ------------------------------------------------------------------
    def _build_agents(self) -> Dict[int, Any]:
        from src.agents.research_inspiration_agent import ResearchInspirationAgent
        from src.agents.literature_review_agent import LiteratureReviewAgent
        from src.agents.research_question_agent import ResearchQuestionAgent
        from src.agents.method_advisor_agent import MethodAdvisorAgent
        from src.agents.data_analysis_agent import DataAnalysisAgent
        from src.agents.paper_writer_agent import PaperWriterAgent
        from src.agents.reviewer_simulator_agent import ReviewerSimulatorAgent

        return {
            WorkflowStage.INSPIRATION: ResearchInspirationAgent(),
            WorkflowStage.LITERATURE: LiteratureReviewAgent(),
            WorkflowStage.DESIGN: ResearchQuestionAgent(),
            WorkflowStage.METHOD: MethodAdvisorAgent(),
            WorkflowStage.DATA_ANALYSIS: DataAnalysisAgent(),
            WorkflowStage.WRITING: PaperWriterAgent(),
            WorkflowStage.REVIEW: ReviewerSimulatorAgent(),
        }

    def _get_agent(self, stage: int) -> Any:
        if stage not in self._agents:
            if not self._agents:
                self._agents = self._build_agents()
            else:
                # 部分注入时补齐缺失
                built = self._build_agents()
                for k, v in built.items():
                    self._agents.setdefault(k, v)
        return self._agents.get(stage)

    # ------------------------------------------------------------------
    # 项目 CRUD
    # ------------------------------------------------------------------
    def create_project(self, title: str = "", interest: str = "") -> ResearchProject:
        return self.store.create(title=title, interest=interest)

    def list_projects(self) -> List[ResearchProject]:
        return self.store.list()

    def get_project(self, project_id: str) -> Optional[ResearchProject]:
        return self.store.get(project_id)

    def get_stage_meta(self) -> list:
        """阶段元数据列表（前端 Research Pipeline 渲染）"""
        return get_stage_meta_list()

    # ------------------------------------------------------------------
    # 阶段执行
    # ------------------------------------------------------------------
    def run_stage(self, project_id: str, stage: int, inputs: Dict[str, Any]) -> StageRecord:
        """
        执行指定阶段智能体。

        - 前置校验：项目存在；阶段在 [1,7]；未解锁（> current_stage）拒绝
        - 注入知识库/搜索上下文（try/except 降级）
        - 产出物落盘为 awaiting_review（等待研究者确认）
        """
        project = self.store.get(project_id)
        if project is None:
            raise ValueError(f"项目不存在: {project_id}")
        if stage < 1 or stage > 7:
            raise ValueError(f"非法阶段: {stage}")

        # 前置阶段校验：只能运行当前阶段或已解锁阶段（重跑已完成阶段）
        if stage > project.current_stage:
            raise ValueError(
                f"阶段 {stage} 未解锁：当前进度在第 {project.current_stage} 阶段"
            )

        agent = self._get_agent(stage)
        if agent is None:
            raise RuntimeError(f"阶段 {stage} 无对应智能体")

        # 标记运行中（清空旧产出物避免失败残留；递增运行次数）
        self.store.update_stage(
            project_id, stage,
            status=StageStatus.RUNNING,
            clear_output=True,
            increment_run_count=True,
            append_history={"stage": stage, "action": "run_start", "summary": f"开始执行{STAGE_META[WorkflowStage(stage)]['name']}"},
        )

        # 合并输入 + 注入知识库/搜索上下文 + 前序阶段产出物
        full_inputs = dict(inputs or {})
        full_inputs.setdefault("topic", project.interest)
        full_inputs.setdefault("project_title", project.title)
        context = self._build_stage_context(stage, full_inputs)
        full_inputs.update(context)
        self._inject_previous_outputs(project, stage, full_inputs)

        try:
            output = agent.run(full_inputs)
            updated = self.store.update_stage(
                project_id, stage,
                status=StageStatus.AWAITING_REVIEW,
                output=output,
                append_history={"stage": stage, "action": "run_done", "summary": f"{STAGE_META[WorkflowStage(stage)]['name']}产出完成"},
            )
            if updated is None:
                raise RuntimeError(f"项目已不存在: {project_id}")
            return updated.stages[str(stage)]
        except Exception as e:
            logger.error(f"[WorkflowEngine] 阶段 {stage} 执行失败: {e}")
            self.store.update_stage(
                project_id, stage,
                status=StageStatus.FAILED,
                error=str(e),
                append_history={"stage": stage, "action": "run_failed", "summary": f"执行失败: {str(e)[:100]}"},
            )
            raise

    def approve_stage(self, project_id: str, stage: int) -> ResearchProject:
        """研究者确认阶段产出物，推进到下一阶段"""
        project = self.store.get(project_id)
        if project is None:
            raise ValueError(f"项目不存在: {project_id}")
        record = project.stages.get(str(stage))
        if record is None or record.status not in (StageStatus.AWAITING_REVIEW, StageStatus.COMPLETED):
            raise ValueError(f"阶段 {stage} 无待确认的产出物")

        updated = self.store.update_stage(
            project_id, stage,
            status=StageStatus.COMPLETED,
            append_history={"stage": stage, "action": "approve", "summary": f"确认{STAGE_META[WorkflowStage(stage)]['name']}产出"},
        )
        return updated

    def get_stage_result(self, project_id: str, stage: int) -> Optional[Dict]:
        project = self.store.get(project_id)
        if project is None:
            return None
        record = project.stages.get(str(stage))
        return record.output if record else None

    # ------------------------------------------------------------------
    # 知识库/搜索上下文注入（全部降级，不影响主流程）
    # ------------------------------------------------------------------
    def _build_stage_context(self, stage: int, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """按阶段注入检索上下文（unified search / vector store / KG）"""
        context: Dict[str, Any] = {}
        topic = inputs.get("topic", "")
        keywords = self._extract_keywords(inputs)

        try:
            from src.search.unified_search import get_unified_search_service
            service = get_unified_search_service()
            sources = service.search_for_topic(topic) if topic else []
            context["search_context"] = [
                {"url": s.url, "title": s.title, "content": (s.content or "")[:400], "source": s.source}
                for s in (sources or [])[:8]
            ]
        except Exception as e:
            logger.warning(f"[WorkflowEngine] 搜索上下文注入失败: {e}")
            context["search_context"] = []

        if stage in (WorkflowStage.LITERATURE, WorkflowStage.DESIGN, WorkflowStage.METHOD):
            try:
                from src.knowledge.vector_store import get_vector_store
                vs = get_vector_store()
                hits = vs.search(topic, top_k=6) if topic else []
                context["knowledge_hits"] = [
                    {"text": h.get("text", "")[:500], "score": round(float(h.get("score", 0)), 3), "metadata": h.get("metadata", {})}
                    for h in (hits or [])
                ]
            except Exception as e:
                logger.warning(f"[WorkflowEngine] 知识库检索注入失败: {e}")
                context["knowledge_hits"] = []

        if stage == WorkflowStage.INSPIRATION:
            try:
                from src.knowledge.kg_builder import get_knowledge_graph
                kg = get_knowledge_graph()
                related = kg.find_related_entities(topic, depth=2) if topic else []
                context["kg_entities"] = [r["entity"] for r in (related or [])[:10]]
            except Exception as e:
                logger.warning(f"[WorkflowEngine] KG 实体注入失败: {e}")
                context["kg_entities"] = []

        return context

    # 阶段输出 → 下游 Agent 输入 key 映射
    _STAGE_OUTPUT_KEYS: Dict[int, str] = {
        1: "inspiration_result",
        2: "literature_review",
        3: "research_design",
        4: "method_result",
        5: "analysis_result",
        6: "paper_draft",
    }

    def _inject_previous_outputs(self, project, stage: int, inputs: Dict[str, Any]) -> None:
        """自动注入已完成前序阶段的产出物，保证跨阶段数据流连续。

        下游 Agent 无需前端手动拼 inputs；用户显式传入的 key 优先（setdefault）。
        """
        for prev_stage in range(1, stage):
            rec = project.stages.get(str(prev_stage))
            if rec is None or rec.status != StageStatus.COMPLETED or not rec.output:
                continue
            key = self._STAGE_OUTPUT_KEYS.get(prev_stage)
            if key:
                inputs.setdefault(key, rec.output)

    def _extract_keywords(self, inputs: Dict[str, Any]) -> List[str]:
        """从输入中提取检索关键词"""
        keywords = []
        direction = inputs.get("direction") or inputs.get("selected_direction") or ""
        if direction:
            keywords.append(str(direction)[:50])
        for rq in inputs.get("research_questions", []) or []:
            if isinstance(rq, dict):
                keywords.append(str(rq.get("text", ""))[:50])
        return keywords[:5]

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export_project(self, project_id: str, fmt: str = "md") -> Dict[str, Any]:
        """汇总导出项目（md/json 文本 + 元数据）"""
        project = self.store.get(project_id)
        if project is None:
            raise ValueError(f"项目不存在: {project_id}")

        stages_out = []
        for stage in range(1, 8):
            record = project.stages.get(str(stage))
            meta = STAGE_META.get(WorkflowStage(stage), {})
            stages_out.append({
                "stage": stage,
                "name": meta.get("name", ""),
                "icon": meta.get("icon", ""),
                "status": record.status.value if record else "pending",
                "output": record.output if record else None,
            })

        data = {
            "id": project.id,
            "title": project.title,
            "interest": project.interest,
            "current_stage": project.current_stage,
            "status": project.status,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "stages": stages_out,
            "history": project.history,
        }

        if fmt == "json":
            content = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            content = self._to_markdown(data)
        return {"project": data, "format": fmt, "content": content}

    def _to_markdown(self, data: Dict[str, Any]) -> str:
        lines = [
            f"# {data['title']}",
            "",
            f"- 初始兴趣：{data['interest']}",
            f"- 当前阶段：第 {data['current_stage']} 阶段",
            f"- 状态：{'已完成' if data['status'] == 'completed' else '进行中'}",
            f"- 创建时间：{data['created_at']}",
            "",
        ]
        for stage in data["stages"]:
            lines.append(f"## {stage['icon']} {stage['name']}（{stage['status']}）")
            output = stage["output"]
            if output:
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(output, ensure_ascii=False, indent=2)[:3000])
                lines.append("```")
            lines.append("")
        return "\n".join(lines)


# 单例
_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
