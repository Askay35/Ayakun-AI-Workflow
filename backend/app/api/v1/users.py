from fastapi import APIRouter

from schemas.user import UserResponse
from schemas.common import ApiResponse
from deps.auth import CurrentUser

router = APIRouter()

@router.get("/")
async def get_users(user: CurrentUser):
    return ApiResponse[UserResponse](success=True, data=UserResponse.model_validate(user))
