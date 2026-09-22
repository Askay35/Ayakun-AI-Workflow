import httpx

from helper import render_template
from schemas.workflow import ImageRecognitionNode
from services.execution.actions.base import NodeAction
from services.execution.context import node_type_value, parent_records
from services.gigachat import GigaChatMediaProvider, MediaModelProvider
from services.media_files import load_binary, normalize_image_output


class ImageRecognitionAction(NodeAction):
    def __init__(self, media: MediaModelProvider | None = None, client: httpx.AsyncClient | None = None):
        self.media = media or GigaChatMediaProvider()
        self.client = client

    async def execute(self, node: ImageRecognitionNode, context: dict) -> dict:
        records = parent_records(node, context)
        if len(records) != 1:
            raise ValueError("Распознавание изображения принимает ровно одну входящую связь")
        if node_type_value(records[0].get("type")) != "image":
            raise ValueError("Распознавание изображения должно идти сразу после узла «Изображение»")
        image = normalize_image_output(records[0].get("output"))
        variables = context.setdefault("variables", {})
        prompt = render_template(node.prompt or "", image, variables).strip()
        if not prompt:
            raise ValueError("Распознавание изображения: укажите промпт")
        if self.client is not None:
            data, mime, filename = await load_binary(image, self.client)
        else:
            async with httpx.AsyncClient(timeout=60) as client:
                data, mime, filename = await load_binary(image, client)
        text = await self.media.recognize_image(prompt, data, mime, filename)
        return {"text": text.strip()}
