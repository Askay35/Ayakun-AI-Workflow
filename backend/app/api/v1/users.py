from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.user import OnboardingComplete, OnboardingResult, UserResponse
from schemas.common import ApiResponse
from deps.auth import CurrentUser
from deps.database import get_db
from services.user import complete_onboarding

router = APIRouter()

@router.get("/")
async def get_users(user: CurrentUser):
    return ApiResponse[UserResponse](success=True, data=UserResponse.model_validate(user))


@router.post("/me/onboarding", response_model=ApiResponse[OnboardingResult])
async def onboarding(data: OnboardingComplete, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return ApiResponse(success=True, data=await complete_onboarding(db, user, data))
