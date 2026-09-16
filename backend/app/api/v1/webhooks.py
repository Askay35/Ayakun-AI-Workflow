import json

from fastapi import APIRouter, Depends, Request, status

from deps.services import get_workflow_service
from schemas.common import ApiResponse
from services.workflow import WorkflowService

router = APIRouter()

_SKIP_HEADERS = {"authorization", "cookie", "host", "content-length", "connection"}


async def _request_body(request: Request) -> object:
    content_type = (request.headers.get("content-type") or "").lower()
    raw = await request.body()
    if not raw:
        return {}
    if "application/json" in content_type:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"text": raw.decode("utf-8", "replace")}
    return {"text": raw.decode("utf-8", "replace")}


@router.api_route("/{token}", methods=["POST", "PUT", "PATCH"], status_code=status.HTTP_202_ACCEPTED)
async def inbound_webhook(
    token: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
):
    payload = {
        "method": request.method,
        "headers": {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in _SKIP_HEADERS
        },
        "query": dict(request.query_params),
        "body": await _request_body(request),
    }
    run = await service.trigger_webhook(token, payload)
    return ApiResponse(success=True, data={"run_id": str(run.id), "status": run.status})
