"""
科研项目持久化与状态管理

研究项目以 JSON 文件形式持久化到 data/projects/{project_id}.json，
保存 7 阶段状态机（StageRecord）与各阶段产出物，供前端科研工作台轮询/恢复。
"""
import json
import logging
import os
import threading
import time
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
            project.updated_at = datetime.now().isoformat(timespec="microseconds")
            path = self._path(project.id)
            # 原子写盘：先写临时文件再 os.replace，避免崩溃留下损坏 JSON
            tmp_path = path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(project.model_dump(), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create(self, title: str = "", interest: str = "", owner_id: str = "") -> ResearchProject:
        """创建研究项目（初始化 7 个阶段记录；id 用微秒时间戳保证单调递增）"""
        now = datetime.now().isoformat(timespec="microseconds")
        project = ResearchProject(
            # 微秒时间戳 id：单调递增（Windows 时钟分辨率 ~15ms，uuid 不保证可排序）
            id=f"proj_{int(time.time() * 1_000_000)}",
            owner_id=owner_id or None,
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

    def list(self, owner_id: Optional[str] = None) -> List[ResearchProject]:
        """按创建顺序倒序返回项目。owner_id 为空 = 全部（admin 视角）；否则只返回该用户的项目。"""
        projects = []
        for path in sorted(self.base_dir.glob("proj_*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    projects.append(ResearchProject.model_validate(json.load(f)))
            except Exception as e:
                logger.warning(f"[ProjectStore] 跳过损坏项目文件 {path.name}: {e}")
        # 按 id（微秒时间戳）倒序：后创建在前；兼容旧 uuid id 项目（排最前/最后无妨）
        projects.sort(key=lambda p: p.id, reverse=True)
        if owner_id:
            projects = [p for p in projects if p.owner_id == owner_id]
        return projects

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def claim_ownerless(self, owner_id: str) -> int:
        """把无主（legacy）项目认领给指定用户。返回认领数量。"""
        claimed = 0
        with self._lock:
            for p in self.list():
                if not p.owner_id:
                    p.owner_id = owner_id
                    self._write(p)
                    claimed += 1
        if claimed:
            logger.info(f"[ProjectStore] 认领 {claimed} 个无主项目 → {owner_id}")
        return claimed

    def delete_by_owner(self, owner_id: str) -> int:
        """删除某用户全部项目（级联删除，删除用户时用）。返回删除数量。"""
        deleted = 0
        with self._lock:
            for p in self.list():
                if p.owner_id == owner_id and self.delete(p.id):
                    deleted += 1
        return deleted

    # ------------------------------------------------------------------
    # 阶段状态更新
    # ------------------------------------------------------------------
    def update_stage(self, project_id: str, stage: int,
                     status: Optional[StageStatus] = None,
                     output: Optional[Dict] = None,
                     error: Optional[str] = None,
                     clear_output: bool = False,
                     increment_run_count: bool = False,
                     append_history: Optional[Dict] = None) -> Optional[ResearchProject]:
        """更新某阶段状态并写盘（read-modify-write 整体持锁，返回更新后的项目）"""
        with self._lock:
            project = self.get(project_id)
            if project is None:
                return None
            key = str(stage)
            record = project.stages.get(key)
            if record is None:
                record = StageRecord(stage=stage)
                project.stages[key] = record

            now = datetime.now().isoformat(timespec="microseconds")
            if status is not None:
                record.status = status
                # 成功状态清除历史失败信息：否则阶段"失败→重跑成功"后
                # error 字段残留，前端会继续展示陈旧错误
                if status in (StageStatus.AWAITING_REVIEW, StageStatus.COMPLETED):
                    record.error = None
            if clear_output:
                record.output = None
            if output is not None:
                record.output = output
            if error is not None:
                record.error = error
            if increment_run_count:
                record.run_count += 1
            record.updated_at = now
            if append_history:
                item = dict(append_history)
                item.setdefault("timestamp", now)
                project.history.append(item)

            # 推进当前阶段：仅在阶段 == 当前阶段且确认完成时推进
            if status == StageStatus.COMPLETED and stage == project.current_stage:
                if stage >= TOTAL_STAGES:
                    project.current_stage = TOTAL_STAGES
                    project.status = "completed"
                else:
                    project.current_stage = stage + 1

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
