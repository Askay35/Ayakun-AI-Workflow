"""Загруженные картинки блоков «Изображение» лежат в JSON цепочки (черновик и снимок публикации)."""

from __future__ import annotations

MAX_USER_IMAGE_FILES = 50
MAX_USER_IMAGE_BYTES = 250 * 1024 * 1024
IMAGE_NODE_RATE_LIMIT = 60
IMAGE_NODE_RATE_WINDOW_SECONDS = 60

IMAGE_QUOTA_MESSAGE = (
    "Слишком много загруженных изображений. "
    f"На аккаунт не больше {MAX_USER_IMAGE_FILES} файлов и 100 МБ."
)
IMAGE_RATE_MESSAGE = "Слишком много новых блоков «Изображение»: не больше 60 в минуту."


def _type_name(node: object) -> str:
    if isinstance(node, dict):
        value = node.get("type")
    else:
        value = getattr(node, "type", None)
    if hasattr(value, "value"):
        value = value.value
    return str(value or "")


def _node_id(node: object) -> str:
    if isinstance(node, dict):
        return str(node.get("id") or "")
    return str(getattr(node, "id", "") or "")


def _file_base64(node: object) -> str:
    if isinstance(node, dict):
        source = node.get("source") or "file"
        raw = node.get("file_base64") or ""
    else:
        source = getattr(node, "source", "file") or "file"
        raw = getattr(node, "file_base64", "") or ""
    if source != "file":
        return ""
    return str(raw).strip()


def decoded_base64_size(encoded: str) -> int:
    payload = encoded.split(",")[-1].strip()
    if not payload:
        return 0
    pad = 2 if payload.endswith("==") else 1 if payload.endswith("=") else 0
    return max((len(payload) * 3) // 4 - pad, 0)


def image_node_ids(nodes: object) -> set[str]:
    items = getattr(nodes, "nodes", nodes)
    if not isinstance(items, (list, tuple)):
        return set()
    return {_node_id(node) for node in items if _type_name(node) == "image" and _node_id(node)}


def uploaded_images(nodes: object) -> list[tuple[str, int]]:
    items = getattr(nodes, "nodes", nodes)
    if not isinstance(items, (list, tuple)):
        return []
    found: list[tuple[str, int]] = []
    for node in items:
        if _type_name(node) != "image":
            continue
        encoded = _file_base64(node)
        if not encoded:
            continue
        found.append((_node_id(node), decoded_base64_size(encoded)))
    return found


def strip_stored_images(snapshot: dict) -> bool:
    """Убирает байты загруженных картинок из снимка. True, если что-то стёрли."""
    nodes = snapshot.get("nodes") if isinstance(snapshot, dict) else None
    if not isinstance(nodes, list):
        return False
    changed = False
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "image":
            continue
        if node.get("file_base64"):
            node["file_base64"] = ""
            changed = True
    return changed


async def consume_image_node_budget(redis, user_id: int, added: int) -> None:
    from fastapi import HTTPException

    if added <= 0 or redis is None:
        return
    key = f"image_node_add:{user_id}"
    current = int(await redis.incrby(key, added))
    if current == added:
        await redis.expire(key, IMAGE_NODE_RATE_WINDOW_SECONDS)
    if current > IMAGE_NODE_RATE_LIMIT:
        await redis.decrby(key, added)
        raise HTTPException(429, IMAGE_RATE_MESSAGE)
