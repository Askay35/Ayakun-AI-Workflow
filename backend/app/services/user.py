from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.user import UserResponse
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