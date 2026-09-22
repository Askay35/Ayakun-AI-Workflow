from helper import render_template
from schemas.workflow import ImageGenerationNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload
from services.gigachat import GigaChatMediaProvider, MediaModelProvider
from services.media_files import image_payload, write_temp_bytes


class ImageGenerationAction(NodeAction):
    def __init__(self, media: MediaModelProvider | None = None):
        self.media = media or GigaChatMediaProvider()

    async def execute(self, node: ImageGenerationNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        prompt = render_template(node.prompt or "", payload, variables).strip()
        if not prompt:
            raise ValueError("Генерация изображения: укажите промпт")
        data = await self.media.generate_image(prompt)
        path = write_temp_bytes(data, ".jpg")
        # Байты остаются во временном файле: в выход узла base64 не кладём.
        return image_payload(
            source="generated",
            mime="image/jpeg",
            filename="image.jpg",
            path=path,
        )
