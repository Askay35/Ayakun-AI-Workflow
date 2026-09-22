"""Доступ к платным медиа-узлам: нужна хотя бы одна покупка пакета."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Payment, PaymentStatus, Plan
from schemas.workflow import NodeType

PAID_MEDIA_NODE_TYPES = frozenset({
    NodeType.IMAGE_GENERATION,
    NodeType.IMAGE_RECOGNITION,
    NodeType.AUDIO_TRANSCRIPTION,
})

PAID_MEDIA_REQUIRED = (
    "Генерация изображений, распознавание и расшифровка аудио доступны после покупки пакета"
)


def graph_uses_paid_media(graph) -> bool:
    return any(getattr(node, "type", None) in PAID_MEDIA_NODE_TYPES for node in getattr(graph, "nodes", ()))


async def user_has_paid_pack(db: AsyncSession, user_id: int) -> bool:
    """Успешная оплата пакета с ценой больше нуля. Стартовые credits не открывают медиа."""
    found = await db.scalar(
        select(Payment.id)
        .join(Plan, Payment.plan_id == Plan.id)
        .where(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.succeeded,
            Plan.price > 0,
        )
        .limit(1)
    )
    return found is not None
