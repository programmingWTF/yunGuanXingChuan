"""
科研项目持久化与状态管理

研究项目以 JSON 文件形式持久化到 data/projects/{project_id}.json，
保存 7 阶段状态机（StageRecord）与各阶段产出物，供前端科研工作台轮询/恢复。
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.schemas import ResearchProject, StageRecord, StageStatus

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).parent.parent.parent / "data" / "projects"

# 阶段总数（与 STAGE_META 对应）
TOTAL_STAGES = 7


class ProjectStore:
    """科研项目存储（JSON 文件 + 内存缓存 + 线程锁）"""

    def __init__(self, base_dir: Path = PROJECTS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # 路径与 IO
    # ------------------------------------------------------------------
    def _path(self, project_id: str) -> Path:
        # 防路径穿越：project_id 只允许字母数字与下划线
        safe_id = "".join(c for c in project_id if c.isalnum() or c == "_")
        return self.base_dir / f"{safe_id}.json"

    def _read(self, project_id: str) -> Optional[ResearchProject]:
        path = self._path(project_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return ResearchProject.model_validate(json.load(f))
        except Exception as e:
            logger.error(f"[ProjectStore] 读取项目失败 {project_id}: {e}")
            return None

    def _write(self, project: ResearchProject) -> None:
        with self._lock:
            project.updated_at = datetime.now().isoformat(timespec="seconds")
            with open(self._path(project.id), "w", encoding="utf-8") as f:
                json.dump(project.model_dump(), f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create(self, title: str = "", interest: str = "") -> ResearchProject:
        """创建研究项目（初始化 7 个阶段记录）"""
        now = datetime.now().isoformat(timespec="seconds")
        project = ResearchProject(
            id=f"proj_{uuid4().hex[:8]}",
            title=title or interest or "未命名研究项目",
            interest=interest,
            created_at=now,
            updated_at=now,
        )
        for stage in range(1, TOTAL_STAGES + 1):
            project.stages[str(stage)] = StageRecord(stage=stage, updated_at=now)
        self._write(project)
        logger.info(f"[ProjectStore] 创建项目 {project.id}: {project.title}")
        return project

    def get(self, project_id: str) -> Optional[ResearchProject]:
        return self._read(project_id)

    def list(self) -> List[ResearchProject]:
        """按创建时间倒序返回全部项目"""
        projects = []
        for path in sorted(self.base_dir.glob("proj_*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    projects.append(ResearchProject.model_validate(json.load(f)))
            except Exception as e:
                logger.warning(f"[ProjectStore] 跳过损坏项目文件 {path.name}: {e}")
        return projects

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # 阶段状态更新
    # ------------------------------------------------------------------
    def update_stage(self, project_id: str, stage: int,
                     status: Optional[StageStatus] = None,
                     output: Optional[Dict] = None,
                     error: Optional[str] = None,
                     append_history: Optional[Dict] = None) -> Optional[ResearchProject]:
        """更新某阶段状态并写盘，返回更新后的项目"""
        project = self.get(project_id)
        if project is None:
            return None
        key = str(stage)
        record = project.stages.get(key)
        if record is None:
            record = StageRecord(stage=stage)
            project.stages[key] = record

        now = datetime.now().isoformat(timespec="seconds")
        if status is not None:
            record.status = status
        if output is not None:
            record.output = output
        if error is not None:
            record.error = error
        record.updated_at = now
        if append_history:
            item = dict(append_history)
            item.setdefault("timestamp", now)
            project.history.append(item)

        # 推进当前阶段：完成 stage 后解锁下一阶段
        if status == StageStatus.COMPLETED and stage == project.current_stage:
            project.current_stage = min(stage + 1, TOTAL_STAGES)
            if project.current_stage >= TOTAL_STAGES:
                project.status = "completed"

        self._write(project)
        return project


# 单例
_store: Optional[ProjectStore] = None
_store_lock = threading.Lock()


def get_project_store() -> ProjectStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ProjectStore()
    return _store
