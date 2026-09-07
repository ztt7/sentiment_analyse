"""研究任务的进程内状态管理。

当前版本只解决任务身份和状态跟踪；状态还没有持久化到数据库，应用重启后会丢失。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4

from engines.common.eventing.bus import subscribe, unsubscribe
from engines.common.eventing.event import EventType


class ResearchTaskStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ResearchTask:
    task_id: str
    query: str
    status: ResearchTaskStatus = ResearchTaskStatus.RUNNING
    role_status: dict[str, str] = field(default_factory=dict)
    role_progress: dict[str, int] = field(default_factory=dict)
    error: str = ""


class ResearchTaskStore:
    """按 task_id 管理研究任务，并消费角色事件更新状态。"""

    ROLES = frozenset(("insight", "media"))

    def __init__(self) -> None:
        self.tasks: dict[str, ResearchTask] = {}
        self._subscribe()

    def _subscribe(self) -> None:
        subscribe(EventType.ROLE_PROGRESS, self._on_role_progress)
        subscribe(EventType.ROLE_RESULT, self._on_role_result)
        subscribe(EventType.ROLE_ERROR, self._on_role_error)

    def close(self) -> None:
        unsubscribe(self._on_role_progress)
        unsubscribe(self._on_role_result)
        unsubscribe(self._on_role_error)

    def create(self, query: str) -> ResearchTask:
        task = ResearchTask(task_id=f"research_{uuid4().hex}", query=query)
        self.tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> Optional[ResearchTask]:
        return self.tasks.get(task_id)

    def _find_task(self, data: dict) -> Optional[ResearchTask]:
        task_id = data.get("task_id", "")
        return self.tasks.get(task_id) if task_id else None

    def _on_role_progress(self, _event_type: EventType, data: dict) -> None:
        task = self._find_task(data)
        if not task:
            return
        role = data.get("role", "")
        task.role_status[role] = data.get("status", "running")
        task.role_progress[role] = max(
            task.role_progress.get(role, 0), data.get("progress_pct", 0)
        )

    def _on_role_result(self, _event_type: EventType, data: dict) -> None:
        task = self._find_task(data)
        if not task:
            return
        task.role_status[data["role"]] = "completed"
        task.role_progress[data["role"]] = 100
        if self.ROLES.issubset(task.role_status) and all(
            task.role_status[role] == "completed" for role in self.ROLES
        ):
            task.status = ResearchTaskStatus.COMPLETED

    def _on_role_error(self, _event_type: EventType, data: dict) -> None:
        task = self._find_task(data)
        if not task:
            return
        role = data.get("role", "unknown")
        task.role_status[role] = "error"
        task.status = ResearchTaskStatus.ERROR
        task.error = f"{role}: {data.get('error', '研究任务失败')}"
