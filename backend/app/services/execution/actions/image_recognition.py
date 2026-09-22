import httpx

from helper import render_template
from schemas.workflow import ImageRecognitionNode
from services.deepseek_vision import DeepSeekVisionProvider
from services.execution.actions.base import NodeAction
from services.execution.context import node_type_value, parent_records
from services.gigachat import GigaChatMediaProvider
from services.media_files import load_binary, normalize_image_output
from services.media_settings import DEFAULT_VISION_PROMPT, IMAGE_MAX_BYTES, vision_provider_name


class ImageRecognitionAction(NodeAction):
    def __init__(
        self,
        media: object | None = None,
        client: httpx.AsyncClient | None = None,
        pricing: object | None = None,
    ):
        self.media = media
        self.client = client
        self.pricing = pricing

    async def _provider(self):
        if self.media is not None:
            return self.media
        if await vision_provider_name(self.pricing) == "gigachat":
            return GigaChatMediaProvider()
        return DeepSeekVisionProvider(self.client)

    async def execute(self, node: ImageRecognitionNode, context: dict) -> dict:
        records = parent_records(node, context)
        if len(records) != 1:
            raise ValueError("Распознавание изображения принимает ровно одну входящую связь")
        if node_type_value(records[0].get("type")) != "image":
            raise ValueError("Распознавание изображения должно идти сразу после узла «Изображение»")
        image = normalize_image_output(records[0].get("output"))
        variables = context.setdefault("variables", {})
        prompt = render_template(node.prompt or "", image, variables).strip() or DEFAULT_VISION_PROMPT
        if self.client is not None:
            data, mime, filename = await load_binary(image, self.client)
        else:
            async with httpx.AsyncClient(timeout=60) as client:
                data, mime, filename = await load_binary(image, client)
        if len(data) > IMAGE_MAX_BYTES:
            raise ValueError("Изображение больше 30 МБ")
        text = await (await self._provider()).recognize_image(prompt, data, mime, filename)
        return {"text": text.strip()}
