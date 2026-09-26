from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from helper import utcnow
from schemas.user import OnboardingComplete, OnboardingResult, UserResponse
from models.user import User


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(self):
        result = await self.db.execute(
            select(User)
        )
        users = result.scalars().all()
        return [UserResponse.model_validate(user) for user in users]

    async def get_user_by_chat_id(self, chat_id: int):
        result = await self.db.execute(
            select(User).where(User.chat_id == chat_id)
        )
        user = result.scalar_one_or_none()
        return UserResponse.model_validate(user) if user else None

async def complete_onboarding(db: AsyncSession, user: User, data: OnboardingComplete) -> OnboardingResult:
    """Сохраняет ответы опроса и копирует подобранный шаблон с расписанием под выбранную частоту."""
    from services.templates import use_template

    workflow_id: str | None = None
    if data.template_slug:
        workflow = await use_template(
            db,
            user,
            data.template_slug,
            mobile=data.mobile,
            schedule_slots=data.schedule_slots,
            schedule_timezone=data.schedule_timezone,
            search_period=data.search_period,
        )
        workflow_id = str(workflow.id)
    user.onboarding_answers = data.answers
    user.onboarded_at = utcnow()
    await db.commit()
    return OnboardingResult(workflow_id=workflow_id)
