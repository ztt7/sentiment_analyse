from typing import Any, Optional
from engines.orchestration.research import run_research
from engines.contracts.roles import role_report_dirs
from engines.common.io.report_io import latest_markdown_report
from app.services.research.research_task_store import (
    ResearchTask,
    ResearchTaskStatus,
    ResearchTaskStore,
)


class ResearchService:

    def __init__(self, task_store: ResearchTaskStore) -> None:
        self._task_store = task_store

    def start_research(self, query: str) -> dict[str, Any]:
        # 1. 引擎编排层启动两个研究Agent执行的任务
        task = self._task_store.create(query)
        try:
            run_research(query, task.task_id)
            return self._serialize_task(task)
        except Exception as e:
            task.status = ResearchTaskStatus.ERROR
            task.error = str(e)
            return self._serialize_task(task)

    def get_research_task(self, task_id: str) -> Optional[dict[str, Any]]:
        task = self._task_store.get(task_id)
        return self._serialize_task(task) if task else None

    @staticmethod
    def _serialize_task(task: ResearchTask) -> dict[str, Any]:
        return {
            "started": task.status != ResearchTaskStatus.ERROR,
            "task_id": task.task_id,
            "query": task.query,
            "status": task.status.value,
            "role_status": task.role_status,
            "role_progress": task.role_progress,
            "error": task.error,
        }

    def get_research_result(self) -> dict[str, Any]:

        research_results: dict[str, Any] = {}
        role_output_dirs = role_report_dirs(role_keys=("insight", "media"))

        for role, output_dir in role_output_dirs.items():
            latest_md = latest_markdown_report(output_dir)
            if not latest_md:
                continue
            research_results[role] = {
                "final_report": latest_md.read_text(encoding="utf-8", errors="ignore"),
                "report_file": str(latest_md),
            }
        return {"results": research_results}
