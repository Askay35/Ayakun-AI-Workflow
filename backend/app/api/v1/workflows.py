import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from deps.auth import CurrentUser
from deps.services import get_workflow_service
from models.workflow import RunStatus
from schemas.common import ApiResponse
from schemas.workflow import (
    RunCreate,
    RunResponse,
    RunStepResponse,
    SoloNodeRunCreate,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowUpdate,
)
from services.workflow import WorkflowService

router = APIRouter()


@router.post("", response_model=ApiResponse[WorkflowResponse], status_code=status.HTTP_201_CREATED)
async def create(data: WorkflowCreate, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.create(data, user))


@router.get("", response_model=ApiResponse[list[WorkflowResponse]])
async def list_workflows(user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.list(user))


@router.get("/runs", response_model=ApiResponse[list[RunResponse]])
async def list_runs(user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.list_runs(user))


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def get(workflow_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.get(workflow_id, user))


@router.patch("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def update(
    workflow_id: uuid.UUID, data: WorkflowUpdate, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)
):
    return ApiResponse(success=True, data=await service.update(workflow_id, data, user))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(workflow_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    await service.delete(workflow_id, user)


@router.post("/{workflow_id}/validate", response_model=ApiResponse[dict])
async def validate(workflow_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    errors = await service.validate(workflow_id, user)
    return ApiResponse(success=not errors, data={"valid": not errors, "errors": errors})


@router.post("/{workflow_id}/publish", response_model=ApiResponse[WorkflowResponse])
async def publish(workflow_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.publish(workflow_id, user))


@router.post("/{workflow_id}/runs", response_model=ApiResponse[RunResponse], status_code=status.HTTP_202_ACCEPTED)
async def run(
    workflow_id: uuid.UUID, data: RunCreate, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)
):
    return ApiResponse(success=True, data=await service.run(workflow_id, user, data.input))


@router.post(
    "/{workflow_id}/nodes/{node_id}/runs",
    response_model=ApiResponse[RunResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_node(
    workflow_id: uuid.UUID,
    node_id: str,
    user: CurrentUser,
    data: SoloNodeRunCreate = SoloNodeRunCreate(),
    service: WorkflowService = Depends(get_workflow_service),
):
    return ApiResponse(success=True, data=await service.run_node(workflow_id, node_id, user, data.input))


@router.get("/runs/{run_id}", response_model=ApiResponse[RunResponse])
async def run_status(run_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.get_run(run_id, user))


@router.get("/runs/{run_id}/nodes", response_model=ApiResponse[list[RunStepResponse]])
async def run_nodes(run_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.list_run_steps(run_id, user))


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse[RunResponse])
async def cancel(run_id: uuid.UUID, user: CurrentUser, service: WorkflowService = Depends(get_workflow_service)):
    return ApiResponse(success=True, data=await service.cancel(run_id, user))


@router.get("/runs/{run_id}/events")
async def events(
    run_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    service: WorkflowService = Depends(get_workflow_service),
):
    run = await service.get_run(run_id, user)

    async def stream():
        last = None
        while not await request.is_disconnected():
            await service.db.refresh(run)
            payload = RunResponse.model_validate(run).model_dump(mode="json")
            # Шаги входят в payload, чтобы прогресс узлов тоже стримился, а не только статус run.
            payload["steps"] = [
                step.model_dump(mode="json")
                for step in await service.list_run_steps(run_id, user)
            ]
            encoded = json.dumps(payload)
            if encoded != last:
                yield f"event: run\ndata: {encoded}\n\n"
                last = encoded
            if run.status in {RunStatus.succeeded, RunStatus.failed, RunStatus.cancelled}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")
