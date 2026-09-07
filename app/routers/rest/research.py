from fastapi import APIRouter, HTTPException

from app.dependencies import ResearchServiceDep
from app.schemas.research_schema import (
    ResearchRequest,
    ResearchResponse,
    ResearchResultsResponse,
    ResearchTaskResponse,
)

router = APIRouter(prefix="/api/research", tags=["研究路由"])


@router.post("", response_model=ResearchResponse, description="开始研究接口")
async def start_research_endpoint(payload: ResearchRequest, service: ResearchServiceDep):
    """POST /api/research 启动研究工作流。"""
    try:
        return service.start_research(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", response_model=ResearchResultsResponse, description="获取研究结果接口")
def get_research_result_endpoint(service: ResearchServiceDep):
    """获取最新研究结果。"""
    try:
        research_result = service.get_research_result()
        return ResearchResultsResponse(results=research_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=ResearchTaskResponse, description="获取研究任务状态")
def get_research_task_endpoint(task_id: str, service: ResearchServiceDep):
    """获取指定研究任务的状态、角色进度和错误信息。"""
    task = service.get_research_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="研究任务不存在")
    return task
