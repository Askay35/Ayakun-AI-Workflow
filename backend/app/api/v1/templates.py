from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from deps.auth import CurrentUser
from deps.database import get_db
from schemas.common import ApiResponse
from schemas.templates import TemplateStep, TemplateSummary
from schemas.workflow import WorkflowResponse
from services.templates import TEMPLATES, use_template

router = APIRouter()


@router.get("", response_model=ApiResponse[list[TemplateSummary]])
async def list_templates():
    return ApiResponse(success=True, data=[
        TemplateSummary(
            slug=item.slug,
            category=item.category,
            name=item.name,
            description=item.description,
            name_en=item.name_en,
            description_en=item.description_en,
            node_types=item.node_types(),
            steps=[TemplateStep(type=node["type"], label=node["label"]) for node in item.nodes],
            variables=item.variables,
        )
        for item in TEMPLATES
    ])


@router.post("/{slug}/use", response_model=ApiResponse[WorkflowResponse], status_code=status.HTTP_201_CREATED)
async def use(slug: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return ApiResponse(success=True, data=await use_template(db, user, slug))
