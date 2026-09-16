import uuid

from fastapi import APIRouter, Depends, Query

from deps.admin import AdminActor
from deps.services import get_admin_records_service, get_auth_service
from models.workflow import RunStatus, WorkflowStatus
from schemas.admin import (
    AdminPage,
    AdminPaymentResponse,
    AdminPaymentUpdate,
    AdminRunResponse,
    AdminRunUpdate,
    AdminUserResponse,
    AdminUserUpdate,
    AdminWorkflowResponse,
    AdminWorkflowUpdate,
)
from schemas.auth import TokenPair
from schemas.billing import PaymentStatus
from schemas.common import ApiResponse
from services.admin_records import AdminRecordsService
from services.auth import AuthService

router = APIRouter()


def get_records(service: AdminRecordsService = Depends(get_admin_records_service)) -> AdminRecordsService:
    return service


@router.get("/users", response_model=ApiResponse[AdminPage[AdminUserResponse]])
async def list_users(
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
    q: str | None = Query(None, max_length=200),
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ApiResponse(success=True, data=await service.list_users(
        q=q, is_active=is_active, page=page, page_size=page_size,
    ))


@router.get("/users/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def get_user(user_id: int, actor: AdminActor, service: AdminRecordsService = Depends(get_records)):
    return ApiResponse(success=True, data=await service.get_user(user_id))


@router.patch("/users/{user_id}", response_model=ApiResponse[AdminUserResponse])
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
):
    return ApiResponse(success=True, data=await service.update_user(user_id, data, actor))


@router.post("/users/{user_id}/session", response_model=ApiResponse[TokenPair])
async def login_as_user(
    user_id: int,
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
    auth: AuthService = Depends(get_auth_service),
):
    return ApiResponse(success=True, data=await service.login_as_user(user_id, actor, auth))


@router.delete("/users/{user_id}", response_model=ApiResponse[dict])
async def delete_user(
    user_id: int,
    actor: AdminActor,
    request_id: str = Query(..., min_length=8, max_length=160),
    service: AdminRecordsService = Depends(get_records),
):
    await service.delete_user(user_id, actor, request_id)
    return ApiResponse(success=True, data={"ok": True})


@router.get("/payments", response_model=ApiResponse[AdminPage[AdminPaymentResponse]])
async def list_payments(
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
    q: str | None = Query(None, max_length=200),
    status: PaymentStatus | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ApiResponse(success=True, data=await service.list_payments(
        q=q, status=status.value if status else None, user_id=user_id, page=page, page_size=page_size,
    ))


@router.get("/payments/{payment_id}", response_model=ApiResponse[AdminPaymentResponse])
async def get_payment(payment_id: uuid.UUID, actor: AdminActor, service: AdminRecordsService = Depends(get_records)):
    return ApiResponse(success=True, data=await service.get_payment(payment_id))


@router.patch("/payments/{payment_id}", response_model=ApiResponse[AdminPaymentResponse])
async def update_payment(
    payment_id: uuid.UUID,
    data: AdminPaymentUpdate,
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
):
    return ApiResponse(success=True, data=await service.update_payment(payment_id, data, actor))


@router.delete("/payments/{payment_id}", response_model=ApiResponse[dict])
async def delete_payment(
    payment_id: uuid.UUID,
    actor: AdminActor,
    request_id: str = Query(..., min_length=8, max_length=160),
    service: AdminRecordsService = Depends(get_records),
):
    await service.delete_payment(payment_id, actor, request_id)
    return ApiResponse(success=True, data={"ok": True})


@router.get("/workflows", response_model=ApiResponse[AdminPage[AdminWorkflowResponse]])
async def list_workflows(
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
    q: str | None = Query(None, max_length=200),
    status: WorkflowStatus | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ApiResponse(success=True, data=await service.list_workflows(
        q=q, status=status.value if status else None, user_id=user_id, page=page, page_size=page_size,
    ))


@router.get("/workflows/{workflow_id}", response_model=ApiResponse[AdminWorkflowResponse])
async def get_workflow(workflow_id: uuid.UUID, actor: AdminActor, service: AdminRecordsService = Depends(get_records)):
    return ApiResponse(success=True, data=await service.get_workflow(workflow_id))


@router.patch("/workflows/{workflow_id}", response_model=ApiResponse[AdminWorkflowResponse])
async def update_workflow(
    workflow_id: uuid.UUID,
    data: AdminWorkflowUpdate,
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
):
    return ApiResponse(success=True, data=await service.update_workflow(workflow_id, data, actor))


@router.delete("/workflows/{workflow_id}", response_model=ApiResponse[dict])
async def delete_workflow(
    workflow_id: uuid.UUID,
    actor: AdminActor,
    request_id: str = Query(..., min_length=8, max_length=160),
    service: AdminRecordsService = Depends(get_records),
):
    await service.delete_workflow(workflow_id, actor, request_id)
    return ApiResponse(success=True, data={"ok": True})


@router.get("/runs", response_model=ApiResponse[AdminPage[AdminRunResponse]])
async def list_runs(
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
    q: str | None = Query(None, max_length=200),
    status: RunStatus | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return ApiResponse(success=True, data=await service.list_runs(
        q=q, status=status.value if status else None, user_id=user_id, page=page, page_size=page_size,
    ))


@router.get("/runs/{run_id}", response_model=ApiResponse[AdminRunResponse])
async def get_run(run_id: uuid.UUID, actor: AdminActor, service: AdminRecordsService = Depends(get_records)):
    return ApiResponse(success=True, data=await service.get_run(run_id))


@router.patch("/runs/{run_id}", response_model=ApiResponse[AdminRunResponse])
async def update_run(
    run_id: uuid.UUID,
    data: AdminRunUpdate,
    actor: AdminActor,
    service: AdminRecordsService = Depends(get_records),
):
    return ApiResponse(success=True, data=await service.update_run(run_id, data, actor))


@router.delete("/runs/{run_id}", response_model=ApiResponse[dict])
async def delete_run(
    run_id: uuid.UUID,
    actor: AdminActor,
    request_id: str = Query(..., min_length=8, max_length=160),
    service: AdminRecordsService = Depends(get_records),
):
    await service.delete_run(run_id, actor, request_id)
    return ApiResponse(success=True, data={"ok": True})
