from pydantic import BaseModel


class TemplateStep(BaseModel):
    type: str
    label: str


class TemplateSummary(BaseModel):
    slug: str
    category: str
    name: str
    description: str
    name_en: str
    description_en: str
    node_types: list[str]
    steps: list[TemplateStep]
    variables: dict[str, str]
