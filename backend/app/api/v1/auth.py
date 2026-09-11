from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status

from deps.auth import CurrentUser
from deps.services import get_auth_service
from schemas.auth import (
    EmailLoginRequest,
    EmailRegisterRequest,
    GoogleAuthorizeRequest,
    GoogleCodeRequest,
    PurposeTokenRequest,
    RefreshRequest,
    ResetConfirmRequest,
    ResetRequest,
    TelegramCodeRequest,
    TokenPair,
)
from schemas.common import ApiResponse
from schemas.user import UserResponse
from services.auth import AuthService
from core.config import settings

router = APIRouter()


@router.post("/register", response_model=ApiResponse[TokenPair], status_code=status.HTTP_201_CREATED)
async def register(data: EmailRegisterRequest, service: AuthService = Depends(get_auth_service)):
    return ApiResponse(
        success=True,
        data=await service.register_email(data.email, data.password, data.name),
    )


@router.post("/login", response_model=ApiResponse[TokenPair])
async def login(data: EmailLoginRequest, service: AuthService = Depends(get_auth_service)):
    return ApiResponse(success=True, data=await service.login_email(data.email, data.password))


@router.post("/login/telegram", response_model=ApiResponse[TokenPair])
async def telegram_login(data: TelegramCodeRequest, service: AuthService = Depends(get_auth_service)):
    return ApiResponse(success=True, data=await service.telegramLoginByCode(data.code))


@router.post("/google/code", response_model=ApiResponse[TokenPair])
async def google_code(data: GoogleCodeRequest, service: AuthService = Depends(get_auth_service)):
    return ApiResponse(
        success=True,
        data=await service.google_login(
            data.code,
            data.code_verifier,
            data.state,
            data.redirect_uri,
        ),
    )


@router.post("/google/authorize", response_model=ApiResponse[dict])
async def google_authorize(
    data: GoogleAuthorizeRequest,
    service: AuthService = Depends(get_auth_service),
):
    if not settings.google_client_id:
        raise HTTPException(503, "Google OAuth не настроен")
    state, nonce = await service.create_google_state(data.redirect_uri)
    query = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": data.redirect_uri or settings.google_redirect_uri or "",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": data.code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
    })
    return ApiResponse(
        success=True,
        data={
            "authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}",
            "state": state,
        },
    )


@router.post("/refresh", response_model=ApiResponse[TokenPair])
async def refresh(data: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    return ApiResponse(success=True, data=await service.refresh(data.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    await service.revoke_refresh(data.refresh_token)


@router.post("/verify-email", response_model=ApiResponse[None])
async def verify_email(data: PurposeTokenRequest, service: AuthService = Depends(get_auth_service)):
    await service.verify_email(data.token)
    return ApiResponse(success=True)


@router.post("/password-reset/request", response_model=ApiResponse[dict])
async def request_reset(data: ResetRequest, service: AuthService = Depends(get_auth_service)):
    await service.request_password_reset(data.email)
    return ApiResponse(success=True, data={})


@router.post("/password-reset/confirm", response_model=ApiResponse[None])
async def confirm_reset(data: ResetConfirmRequest, service: AuthService = Depends(get_auth_service)):
    await service.reset_password(data.token, data.password)
    return ApiResponse(success=True)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def me(user: CurrentUser):
    return ApiResponse(success=True, data=UserResponse.model_validate(user))
