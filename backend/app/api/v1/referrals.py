from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps.auth import CurrentUser
from deps.database import get_db
from schemas.common import ApiResponse
from schemas.referrals import ReferralClaim, ReferralSummary
from services.referrals import ReferralService

router = APIRouter()


@router.get("", response_model=ApiResponse[ReferralSummary])
async def summary(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return ApiResponse(success=True, data=await ReferralService(db).summary(user))


@router.post("/claim", response_model=ApiResponse[None])
async def claim(data: ReferralClaim, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await ReferralService(db).claim(user, data.code)
    return ApiResponse(success=True)
