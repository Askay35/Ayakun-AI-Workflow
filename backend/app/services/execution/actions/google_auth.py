import json

from helper import render_template


def google_service_account_token(raw: str, scopes: list[str]) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        raise ValueError("Авторизация Google недоступна") from exc
    try:
        info = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError("JSON сервисного аккаунта некорректен") from exc
    if not isinstance(info, dict):
        raise ValueError("JSON сервисного аккаунта должен быть объектом")
    try:
        credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        credentials.refresh(Request())
    except Exception:
        raise ValueError("Не удалось авторизоваться в Google") from None
    token = getattr(credentials, "token", None)
    if not token:
        raise ValueError("Не удалось авторизоваться в Google")
    return str(token)


def rendered_secret(template: str, payload: object, variables: dict) -> str:
    text = (template or "").strip()
    if not text:
        return ""
    return str(render_template(text, payload, variables)).strip()
