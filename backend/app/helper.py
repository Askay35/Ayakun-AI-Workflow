import datetime
import hashlib
import json
import re
import secrets
from typing import Any

from fastapi import HTTPException
import jwt
from pwdlib import PasswordHash

from core.config import settings

password_hash = PasswordHash.recommended()
_PLACEHOLDER_RE = re.compile(r"\{\{\$([^}]+)\}\}")
_MISSING = object()
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_PATH_TOKEN_RE = re.compile(r"\[(-?\d+)\]|([A-Za-z_][\w]*)|(\d+)")


def generate_login_code() -> str:
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


def generate_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": now + datetime.timedelta(minutes=settings.access_token_minutes),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, token_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истек")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")


def create_purpose_token(user_id: int, purpose: str, minutes: int = 30) -> str:
    now = datetime.datetime.now(datetime.UTC)
    return jwt.encode(
        {"sub": str(user_id), "type": purpose, "iat": now, "exp": now + datetime.timedelta(minutes=minutes)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def try_parse_json(text: str) -> Any:
    raw = _FENCE_RE.sub("", text.strip()).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


_OUTPUT_ENVELOPE_KEYS = frozenset({
    "text", "usage", "provider", "model", "truncated", "citations", "answer", "content",
})


def structured_root(output: Any) -> Any | None:
    """JSON на входе узла или None, если это обычный текст."""
    if output is None:
        return None
    if isinstance(output, str):
        return try_parse_json(output)
    if isinstance(output, list):
        return output
    if isinstance(output, dict):
        text = output.get("text")
        if isinstance(text, str) and text.strip():
            parsed = try_parse_json(text)
            if parsed is not None:
                return parsed
            if set(output) <= _OUTPUT_ENVELOPE_KEYS:
                return None
        return output
    return None


def json_root_from_output(output: Any) -> Any:
    """Корень для {{$path}}: dict/list узла или JSON, разобранный из поля text."""
    if output is None:
        return {}
    structured = structured_root(output)
    if structured is not None:
        return structured
    if isinstance(output, str):
        return {"text": output}
    if isinstance(output, dict):
        return output
    return output


def parse_expression_path(path: str) -> list[str | int]:
    raw = path.strip()
    if raw.startswith("."):
        raw = raw[1:]
    if not raw:
        raise ValueError("Пустое выражение {{$}}")
    parts: list[str | int] = []
    index = 0
    while index < len(raw):
        if raw[index] == ".":
            index += 1
            continue
        match = _PATH_TOKEN_RE.match(raw, index)
        if not match:
            raise ValueError(f"Некорректный путь в выражении {{${path}}}")
        index, number, name, dotted_index = match.end(), match.group(1), match.group(2), match.group(3)
        if number is not None:
            parts.append(int(number))
        elif dotted_index is not None:
            parts.append(int(dotted_index))
        else:
            parts.append(name)
    return parts


def _walk_path(data: Any, parts: list[str | int]) -> Any:
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
                continue
            if isinstance(part, int) and str(part) in current:
                current = current[str(part)]
                continue
            return _MISSING
        if isinstance(current, list) and isinstance(part, int):
            if -len(current) <= part < len(current):
                current = current[part]
                continue
            return _MISSING
        return _MISSING
    return current


def _resolve_json_path(data: Any, path: str) -> Any:
    parts = parse_expression_path(path)
    resolved = _walk_path(data, parts)
    if resolved is not _MISSING:
        return resolved
    if parts and parts[0] == "json":
        return _walk_path(data, parts[1:])
    return _MISSING


def _missing_expression_error(path: str) -> ValueError:
    return ValueError(
        f"В данных предыдущего узла нет поля {path} ({{{{${path}}}}})"
    )


def _substitute_placeholders(value: Any, json_root: Any) -> Any:
    if isinstance(value, dict):
        return {key: _substitute_placeholders(item, json_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute_placeholders(item, json_root) for item in value]
    if not isinstance(value, str):
        return value

    full_match = _PLACEHOLDER_RE.fullmatch(value.strip())
    if full_match:
        path = full_match.group(1).strip()
        resolved = _resolve_json_path(json_root, path)
        if resolved is _MISSING:
            raise _missing_expression_error(path)
        return resolved

    def replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        resolved = _resolve_json_path(json_root, path)
        if resolved is _MISSING:
            raise _missing_expression_error(path)
        if resolved is None:
            return ""
        return str(resolved)

    return _PLACEHOLDER_RE.sub(replace, value)


def render_template(template: str, data: Any) -> str:
    """Подставляет {{$path}} в строку. path считается от корня входных данных."""
    result = _substitute_placeholders(template, data)
    return "" if result is None else str(result)


def _parse_request_template(body: str | dict) -> dict:
    if isinstance(body, dict):
        return body
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Данные запроса должны быть JSON-объектом")
    try:
        template = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Данные запроса содержат некорректный JSON: {exc.msg}") from exc
    if not isinstance(template, dict):
        raise ValueError("Данные запроса должны быть JSON-объектом")
    return template


def _parse_request_input(value: str | dict | list | None) -> Any:
    if value is None or value == "":
        return {}
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Входные данные узла содержат некорректный JSON: {exc.msg}") from exc


def form_request_body(body: str | dict, input: str | dict | list | None = None) -> dict:
    """Подставляет {{$path}} из input в JSON-шаблон body и возвращает dict."""
    template = _parse_request_template(body)
    payload = _parse_request_input(input)
    result = _substitute_placeholders(template, payload)
    if not isinstance(result, dict):
        raise ValueError("Данные запроса должны быть JSON-объектом")
    return result


def expression_root(output: Any) -> Any:
    return json_root_from_output(output)


def _parse_literal(token: str) -> Any:
    raw = token.strip()
    if not raw:
        raise ValueError("IF ELSE: некорректное условие")
    lowered = raw.lower()
    if lowered == "null" or lowered == "undefined":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def resolve_operand(token: str, json_root: Any, *, missing_as_null: bool = False) -> Any:
    stripped = token.strip()
    full_match = _PLACEHOLDER_RE.fullmatch(stripped)
    if full_match:
        path = full_match.group(1).strip()
        resolved = _resolve_json_path(json_root, path)
        if resolved is _MISSING:
            if missing_as_null:
                return None
            raise _missing_expression_error(path)
        return resolved
    if _PLACEHOLDER_RE.search(stripped):
        substituted = _substitute_placeholders(stripped, json_root)
        return _parse_literal(str(substituted))
    return _parse_literal(stripped)


def _split_condition(expression: str) -> tuple[str, str, str] | None:
    in_quote: str | None = None
    index = 0
    operators = ("===", "!==", ">=", "<=", "==", "!=", ">", "<")
    while index < len(expression):
        char = expression[index]
        if in_quote:
            if char == "\\" and index + 1 < len(expression):
                index += 2
                continue
            if char == in_quote:
                in_quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            in_quote = char
            index += 1
            continue
        for operator in operators:
            if expression.startswith(operator, index):
                if operator in {"===", "!=="}:
                    raise ValueError("IF ELSE: некорректное условие")
                left = expression[:index].strip()
                right = expression[index + len(operator):].strip()
                if not left or not right:
                    raise ValueError("IF ELSE: некорректное условие")
                return left, operator, right
        index += 1
    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _values_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) and isinstance(right, bool):
        return left is right
    if _is_number(left) and _is_number(right):
        return float(left) == float(right)
    return left == right


def _as_number(value: Any, operator: str) -> float:
    if _is_number(value):
        return float(value)
    raise ValueError(f"IF ELSE: нельзя сравнить значение {value!r} через {operator}")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if _is_number(value):
        return value != 0
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return bool(value)
    return bool(value)


def evaluate_condition(condition: str, json_root: Any) -> bool:
    expression = (condition or "").strip()
    if not expression:
        raise ValueError("IF ELSE: условие не задано")
    try:
        parts = _split_condition(expression)
        if parts is None:
            return _as_bool(resolve_operand(expression, json_root, missing_as_null=True))
        left_token, operator, right_token = parts
        left = resolve_operand(left_token, json_root, missing_as_null=True)
        right = resolve_operand(right_token, json_root, missing_as_null=True)
        if operator == "==":
            return _values_equal(left, right)
        if operator == "!=":
            return not _values_equal(left, right)
        left_number = _as_number(left, operator)
        right_number = _as_number(right, operator)
        if operator == ">":
            return left_number > right_number
        if operator == "<":
            return left_number < right_number
        if operator == ">=":
            return left_number >= right_number
        if operator == "<=":
            return left_number <= right_number
        raise ValueError("IF ELSE: некорректное условие")
    except ValueError as exc:
        message = str(exc)
        if message.startswith("IF ELSE:"):
            raise
        raise ValueError(f"IF ELSE: {message}") from exc

def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)