"""Регистрация только с доменов из списка популярных почтовых сервисов."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

EMAIL_DOMAIN_DENIED = "Регистрация с этой почты недоступна. Используйте адрес популярного почтового сервиса."


def _allowlist_path() -> Path | None:
    env = (os.getenv("EMAIL_ALLOWLIST_PATH") or "").strip()
    candidates = [Path(env)] if env else []
    here = Path(__file__).resolve()
    candidates.append(here.parents[1] / "email_allowlist.txt")
    for parent in here.parents:
        candidates.append(parent / "docs" / "email-allowlist.txt")
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def allowed_email_domains() -> frozenset[str]:
    path = _allowlist_path()
    if path is None:
        return frozenset()
    domains: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        domain = line.strip().lower().lstrip("@")
        if domain and not domain.startswith("#"):
            domains.add(domain)
    return frozenset(domains)


def email_domain(email: str) -> str:
    cleaned = (email or "").strip().lower()
    name, separator, domain = cleaned.rpartition("@")
    if not separator or not name or not domain or "." not in domain:
        return ""
    return domain


def email_domain_allowed(email: str) -> bool:
    domain = email_domain(email)
    return bool(domain) and domain in allowed_email_domains()
