from fastapi import Request
from fastapi.responses import JSONResponse

async def http_exception_handler(
    request: Request,
    exc,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "HTTP_ERROR",
                "message": ", ".join(exc.detail) if isinstance(exc.detail, list) else str(exc.detail),
           
            },
        },
    )