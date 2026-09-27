"""Загруженные файлы блоков «Изображение», «Файл» и «Расшифровка аудио» лежат в JSON цепочки (черновик и снимок публикации)."""

from __future__ import annotations

# Лимиты хранилища без платного тарифа; у тарифов свои лимиты в plans.limits.
MAX_USER_IMAGE_FILES = 20
MAX_USER_IMAGE_BYTES = 100 * 1024 * 1024
STORED_FILE_NODE_TYPES = frozenset({"image", "file", "audio_transcription"})
IMAGE_NODE_RATE_LIMIT = 60
IMAGE_NODE_RATE_WINDOW_SECONDS = 60


def _format_size(nbytes: int) -> str:
    gigabytes = nbytes / (1024 ** 3)
    if gigabytes >= 1:
        return f"{gigabytes:g} ГБ"
    return f"{nbytes // (1024 * 1024)} МБ"


def storage_quota_message(max_files: int, max_bytes: int) -> str:
    return (
        "Превышен лимит хранилища тарифа: "
        f"не больше {max_files} файлов и {_format_size(max_bytes)} на аккаунт. "
        "Удалите лишние файлы или перейдите на тариф выше."
    )


IMAGE_QUOTA_MESSAGE = storage_quota_message(MAX_USER_IMAGE_FILES, MAX_USER_IMAGE_BYTES)
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
        source = getattr(node, "source", None) or "file"
        raw = getattr(node, "file_base64", "") or ""
    if source != "file":
        return ""
    return str(raw).strip()


def _stored_key_and_size(node: object) -> tuple[str, int] | None:
    if isinstance(node, dict):
        key, size = node.get("s3_key"), node.get("file_size")
    else:
        key, size = getattr(node, "s3_key", None), getattr(node, "file_size", None)
    if key and isinstance(size, int) and size >= 0:
        return str(key), size
    return None


def decoded_base64_size(encoded: str) -> int:
    payload = encoded.split(",")[-1].strip()
    if not payload:
        return 0
    pad = 2 if payload.endswith("==") else 1 if payload.endswith("=") else 0
    return max((len(payload) * 3) // 4 - pad, 0)


def _node_items(nodes: object) -> object:
    if isinstance(nodes, dict):
        return nodes.get("nodes")
    return getattr(nodes, "nodes", nodes)


def image_node_ids(nodes: object) -> set[str]:
    items = _node_items(nodes)
    if not isinstance(items, (list, tuple)):
        return set()
    return {_node_id(node) for node in items if _type_name(node) == "image" and _node_id(node)}


def uploaded_images(nodes: object) -> list[tuple[str, int]]:
    items = _node_items(nodes)
    if not isinstance(items, (list, tuple)):
        return []
    found: list[tuple[str, int]] = []
    for node in items:
        if _type_name(node) not in STORED_FILE_NODE_TYPES:
            continue
        stored = _stored_key_and_size(node)
        if stored is not None:
            found.append((_node_id(node), stored[1]))
            continue
        encoded = _file_base64(node)
        if not encoded:
            continue
        found.append((_node_id(node), decoded_base64_size(encoded)))
    return found


def stored_file_keys(nodes: object) -> set[str]:
    items = _node_items(nodes)
    if not isinstance(items, (list, tuple)):
        return set()
    keys: set[str] = set()
    for node in items:
        if _type_name(node) not in STORED_FILE_NODE_TYPES:
            continue
        stored = _stored_key_and_size(node)
        if stored is not None:
            keys.add(stored[0])
    return keys


def strip_stored_images(snapshot: dict, keep_keys: frozenset[str] = frozenset()) -> tuple[bool, list[str]]:
    """Убирает байты и ссылку на S3 у загруженных файлов снимка, кроме тех, что ещё используются (keep_keys)."""
    nodes = snapshot.get("nodes") if isinstance(snapshot, dict) else None
    if not isinstance(nodes, list):
        return False, []
    changed = False
    removed: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") not in STORED_FILE_NODE_TYPES:
            continue
        key = node.get("s3_key")
        if key and key in keep_keys:
            continue
        if node.get("file_base64") or key:
            if key:
                removed.append(str(key))
            node["file_base64"] = ""
            node["s3_key"] = None
            node["file_size"] = None
            node["file_hash"] = None
            changed = True
    return changed, removed


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
