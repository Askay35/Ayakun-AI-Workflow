from yookassa import Configuration

from core.config import settings
from services.billing.service import BillingService

Configuration.account_id = settings.yookassa_account_id
Configuration.secret_key = settings.yookassa_secret_key

__all__ = ["BillingService"]
