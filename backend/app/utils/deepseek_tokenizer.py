"""Локальная оценка токенов DeepSeek без сетевых запросов и побочных эффектов."""

from functools import lru_cache
from pathlib import Path

from tokenizers import Tokenizer


@lru_cache(maxsize=1)
def get_tokenizer() -> Tokenizer:
    return Tokenizer.from_file(str(Path(__file__).with_name("tokenizer.json")))


def count_text_tokens(text: str) -> int:
    if not text:
        return 0
    return len(get_tokenizer().encode(text).ids)


def count_prompt_tokens(
    prompt: str,
    *,
    instructions: str | None = None,
    input_data: str | list[str] | None = None,
) -> int:
    """Консервативная оценка chat input с небольшим запасом на role-разметку."""
    parts = [instructions or ""]
    if isinstance(input_data, list):
        parts.extend(input_data)
    elif input_data:
        parts.append(input_data)
    parts.append(prompt)
    return sum(count_text_tokens(part) + 4 for part in parts if part) + 3
