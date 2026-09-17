import base64
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
_PLACEHOLDER_RE = re.compile(r"\{\{\$([^}]*)\}\}")
_VAR_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*)\}\}")
_FOR_BLOCK_RE = re.compile(
    r"\{%\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(\$[^\s%]*|[A-Za-z_][A-Za-z0-9_.\[\]]*)\s*%\}(.*?)\{\%\s*endfor\s*%\}",
    re.DOTALL,
)
_NUMERIC_STRING_RE = re.compile(r"-?\d+(?:\.\d+)?")
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


def _secret_fernet():
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _secret_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _secret_fernet().decrypt(value.encode()).decode()


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
    if raw.startswith("$"):
        raw = raw[1:]
    if raw.startswith("."):
        raw = raw[1:]
    if not raw:
        return []
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
    if not parts:
        return current
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


def _missing_variable_error(name: str) -> ValueError:
    return ValueError(f"Переменная {name} пока не определена")


def _lookup_variable(name: str, variables: dict | None, *, missing_as_null: bool = False) -> Any:
    vars_map = variables if isinstance(variables, dict) else {}
    if "." in name or "[" in name:
        resolved = _resolve_json_path(vars_map, name)
        if resolved is not _MISSING:
            return resolved
        root_name = name.split(".", 1)[0].split("[", 1)[0]
        if root_name not in vars_map:
            if missing_as_null:
                return None
            raise _missing_variable_error(root_name)
        if missing_as_null:
            return None
        raise _missing_expression_error(name)
    if name in vars_map:
        return vars_map[name]
    if missing_as_null:
        return None
    raise _missing_variable_error(name)


def _resolve_loop_source(source: str, json_root: Any, variables: dict | None) -> Any:
    token = source.strip()
    if token.startswith("$"):
        resolved = _resolve_json_path(json_root, token[1:])
        if resolved is _MISSING:
            raise _missing_expression_error(token[1:] or ".")
        return resolved
    return _lookup_variable(token, variables)


def _loop_items(source: Any) -> list[Any]:
    if source is None:
        return []
    if isinstance(source, list):
        return source
    if isinstance(source, dict):
        return [source]
    return [source]


def _scoped_variables(variables: dict | None, name: str, item: Any) -> dict:
    scoped = dict(variables or {})
    scoped[name] = item
    return scoped


def _expand_for_loops(text: str, json_root: Any, variables: dict | None, stringify: Any | None) -> str:
    def replace_block(match: re.Match[str]) -> str:
        item_name, source, body = match.group(1), match.group(2), match.group(3)
        items = _loop_items(_resolve_loop_source(source, json_root, variables))
        chunks: list[str] = []
        for item in items:
            scoped = _scoped_variables(variables, item_name, item)
            inner = _expand_for_loops(body, json_root, scoped, stringify)
            rendered = _substitute_placeholders(inner, json_root, scoped, stringify)
            chunks.append("" if rendered is None else (rendered if isinstance(rendered, str) else str(rendered)))
        return "".join(chunks)

    return _FOR_BLOCK_RE.sub(replace_block, text)


def _stringify_resolved(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


_TELEGRAM_MARKDOWN_SPECIALS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_telegram_markdown(value: Any) -> str:
    """Экранирует динамическое значение для Telegram MarkdownV2, не трогая разметку шаблона."""
    return _TELEGRAM_MARKDOWN_SPECIALS.sub(r"\\\1", _stringify_resolved(value))


_TELEGRAM_UNESCAPE_RE = re.compile(r"\\([_*\[\]()~`>#+\-=|{}.!\\])")


def unescape_telegram_markdown(value: str) -> str:
    """Убирает экранирование MarkdownV2 для показа текста пользователю."""
    return _TELEGRAM_UNESCAPE_RE.sub(r"\1", value)


def display_telegram_output(output: dict | list | None) -> dict | list | None:
    """Копия output telegram_send без MarkdownV2-экранирования в text."""
    if not isinstance(output, dict):
        return output
    text = output.get("text")
    if not isinstance(text, str) or "\\" not in text:
        return output
    return {**output, "text": unescape_telegram_markdown(text)}


def _substitute_placeholders(
    value: Any,
    json_root: Any,
    variables: dict | None = None,
    stringify: Any | None = None,
) -> Any:
    format_value = stringify or _stringify_resolved
    if isinstance(value, dict):
        return {
            key: _substitute_placeholders(item, json_root, variables, stringify)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_substitute_placeholders(item, json_root, variables, stringify) for item in value]
    if not isinstance(value, str):
        return value

    if "{%" in value:
        value = _expand_for_loops(value, json_root, variables, stringify)

    stripped = value.strip()
    if stripped == value:
        full_match = _PLACEHOLDER_RE.fullmatch(stripped)
        if full_match:
            path = full_match.group(1).strip()
            resolved = _resolve_json_path(json_root, path)
            if resolved is _MISSING:
                raise _missing_expression_error(path)
            return resolved
        var_match = _VAR_PLACEHOLDER_RE.fullmatch(stripped)
        if var_match:
            return _lookup_variable(var_match.group(1), variables)

    def replace_path(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        resolved = _resolve_json_path(json_root, path)
        if resolved is _MISSING:
            raise _missing_expression_error(path)
        return format_value(resolved)

    def replace_var(match: re.Match[str]) -> str:
        return format_value(_lookup_variable(match.group(1), variables))

    replaced = _PLACEHOLDER_RE.sub(replace_path, value)
    return _VAR_PLACEHOLDER_RE.sub(replace_var, replaced)


def render_template(
    template: str,
    data: Any,
    variables: dict | None = None,
    *,
    stringify: Any | None = None,
) -> str:
    """Подставляет {{$path}} и {{variable}} в строку."""
    result = _substitute_placeholders(template, data, variables, stringify)
    if result is None:
        return ""
    if stringify is not None:
        return result if isinstance(result, str) else stringify(result)
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


_TELEGRAM_TOKEN_RE = re.compile(
    r"```[\s\S]*?```"
    r"|`[^`]+`"
    r"|\[[^]]*\]\([^)]*\)"
    r"|\|\|.+?\|\|"
    r"|__.+?__"
    r"|\*.+?\*"
    r"|_.+?_"
    r"|~.+?~"
    r"|\{\{\$[^}]*\}\}"
    r"|\{\{[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*\}\}"
)
_TELEGRAM_PLACEHOLDER_RE = re.compile(
    r"\{\{\$[^}]*\}\}|\{\{[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*\}\}"
)


def _escape_telegram_link_url(value: Any) -> str:
    return _stringify_resolved(value).replace("\\", "\\\\").replace(")", "\\)")


def _render_telegram_url(segment: str, data: Any, variables: dict | None) -> str:
    parts: list[str] = []
    last = 0
    for match in _TELEGRAM_PLACEHOLDER_RE.finditer(segment):
        if match.start() > last:
            parts.append(_escape_telegram_link_url(segment[last:match.start()]))
        parts.append(_escape_telegram_link_url(render_template(match.group(0), data, variables)))
        last = match.end()
    if last < len(segment):
        parts.append(_escape_telegram_link_url(segment[last:]))
    return "".join(parts)


def _render_telegram_token(token: str, data: Any, variables: dict | None) -> str:
    if token.startswith("{{"):
        return escape_telegram_markdown(render_template(token, data, variables))
    if token.startswith("```") and token.endswith("```"):
        return "```" + render_template(token[3:-3], data, variables) + "```"
    if token.startswith("`") and token.endswith("`"):
        return "`" + render_template(token[1:-1], data, variables) + "`"
    if token.startswith("[") and "](" in token and token.endswith(")"):
        label, url = token[1:-1].split("](", 1)
        return (
            f"[{_render_telegram_segment(label, data, variables)}]"
            f"({_render_telegram_url(url, data, variables)})"
        )
    for opener in ("||", "__"):
        if token.startswith(opener) and token.endswith(opener) and len(token) >= 2 * len(opener):
            inner = token[len(opener):-len(opener)]
            return opener + _render_telegram_segment(inner, data, variables) + opener
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "*_~":
        return token[0] + _render_telegram_segment(token[1:-1], data, variables) + token[0]
    return escape_telegram_markdown(token)


def _render_telegram_segment(segment: str, data: Any, variables: dict | None) -> str:
    parts: list[str] = []
    last = 0
    for match in _TELEGRAM_TOKEN_RE.finditer(segment):
        if match.start() > last:
            parts.append(escape_telegram_markdown(segment[last:match.start()]))
        parts.append(_render_telegram_token(match.group(0), data, variables))
        last = match.end()
    if last < len(segment):
        parts.append(escape_telegram_markdown(segment[last:]))
    return "".join(parts)


def render_telegram_message(template: str, data: Any, variables: dict | None = None) -> str:
    """Подставляет переменные и экранирует MarkdownV2, сохраняя разметку шаблона."""
    expanded = _expand_for_loops(template, data, variables, stringify=_stringify_resolved)
    if "{{" not in expanded and "{%" not in expanded:
        return _escape_telegram_keeping_markup(expanded)
    return _render_telegram_segment(expanded, data, variables)


_TELEGRAM_MARKUP_RE = re.compile(
    r"```[\s\S]*?```"
    r"|`[^`]+`"
    r"|\[[^]]*\]\([^)]*\)"
    r"|\|\|.+?\|\|"
    r"|__.+?__"
    r"|\*.+?\*"
    r"|_.+?_"
    r"|~.+?~"
)


def _escape_telegram_keeping_markup(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in _TELEGRAM_MARKUP_RE.finditer(text):
        if match.start() > last:
            parts.append(escape_telegram_markdown(text[last:match.start()]))
        token = match.group(0)
        if token.startswith("```") and token.endswith("```"):
            parts.append("```" + token[3:-3] + "```")
        elif token.startswith("`") and token.endswith("`"):
            parts.append("`" + token[1:-1] + "`")
        elif token.startswith("[") and "](" in token and token.endswith(")"):
            label, url = token[1:-1].split("](", 1)
            parts.append(f"[{escape_telegram_markdown(label)}]({url.replace(')', '\\)')})")
        else:
            for opener in ("||", "__"):
                if token.startswith(opener) and token.endswith(opener) and len(token) >= 2 * len(opener):
                    inner = token[len(opener):-len(opener)]
                    parts.append(opener + inner + opener)
                    break
            else:
                if len(token) >= 2 and token[0] == token[-1] and token[0] in "*_~":
                    parts.append(token[0] + token[1:-1] + token[0])
                else:
                    parts.append(escape_telegram_markdown(token))
        last = match.end()
    if last < len(text):
        parts.append(escape_telegram_markdown(text[last:]))
    return "".join(parts)


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


def form_request_body(
    body: str | dict,
    input: str | dict | list | None = None,
    variables: dict | None = None,
) -> dict:
    """Подставляет {{$path}} и {{variable}} в JSON-шаблон body и возвращает dict."""
    template = _parse_request_template(body)
    payload = _parse_request_input(input)
    result = _substitute_placeholders(template, payload, variables)
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


def resolve_operand(
    token: str,
    json_root: Any,
    *,
    missing_as_null: bool = False,
    variables: dict | None = None,
) -> Any:
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
    var_match = _VAR_PLACEHOLDER_RE.fullmatch(stripped)
    if var_match:
        return _lookup_variable(var_match.group(1), variables, missing_as_null=missing_as_null)
    if _PLACEHOLDER_RE.search(stripped) or _VAR_PLACEHOLDER_RE.search(stripped):
        substituted = _substitute_placeholders(stripped, json_root, variables)
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


def _coerce_number(value: Any) -> float | None:
    if _is_number(value):
        return float(value)
    if isinstance(value, str) and _NUMERIC_STRING_RE.fullmatch(value.strip()):
        return float(value.strip())
    return None


def _values_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) and isinstance(right, bool):
        return left is right
    left_number = _coerce_number(left)
    right_number = _coerce_number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return left == right


def _as_number(value: Any, operator: str) -> float:
    coerced = _coerce_number(value)
    if coerced is not None:
        return coerced
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


def evaluate_condition(condition: str, json_root: Any, variables: dict | None = None) -> bool:
    expression = (condition or "").strip()
    if not expression:
        raise ValueError("IF ELSE: условие не задано")
    try:
        parts = _split_condition(expression)
        if parts is None:
            return _as_bool(resolve_operand(expression, json_root, missing_as_null=True, variables=variables))
        left_token, operator, right_token = parts
        left = resolve_operand(left_token, json_root, missing_as_null=True, variables=variables)
        right = resolve_operand(right_token, json_root, missing_as_null=True, variables=variables)
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


def resolve_assignment_value(raw: str, json_root: Any, variables: dict | None = None) -> Any:
    stripped = (raw or "").strip()
    if not stripped:
        return ""
    if _PLACEHOLDER_RE.search(stripped) or _VAR_PLACEHOLDER_RE.search(stripped):
        return _substitute_placeholders(stripped, json_root, variables)
    return _parse_literal(stripped)


def apply_variable_assignments(assignments: Any, output: Any, context: dict) -> None:
    items: list[tuple[str, str]] = []
    if not assignments:
        return
    if isinstance(assignments, dict):
        items = [(str(key), "" if value is None else str(value)) for key, value in assignments.items()]
    else:
        for item in assignments:
            if hasattr(item, "key"):
                items.append((str(item.key), "" if item.value is None else str(item.value)))
            elif isinstance(item, dict) and item.get("key"):
                items.append((str(item["key"]), "" if item.get("value") is None else str(item.get("value"))))
    variables = context.setdefault("variables", {})
    if not isinstance(variables, dict):
        variables = {}
        context["variables"] = variables
    root = expression_root(output)
    for key, raw in items:
        name = key.strip()
        if not name:
            continue
        variables[name] = resolve_assignment_value(raw, root, variables)

def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)