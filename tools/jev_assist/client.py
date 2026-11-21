"""jev.ai assistant client with a local answer cache.

The key comes from the environment only (`JEV_API_KEY`) and is never printed, logged, or
written to the cache. The jev.ai request shape is not confirmed, so the endpoint and the
field names are configurable. Defaults are a common chat-style JSON call and must be checked
against the jev.ai documentation before relying on them.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "jev"

GAME_CONTEXT = (
    "You assist engineers exploring a Rules of Survival style battle royale server written in "
    "Python (FastAPI). Rules live in app/game (rules.py, items.py, simulate.py). Numbers are "
    "this project's independent design, not original game values. Answer briefly and name the "
    "file or test to check."
)


class JevError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevConfig:
    api_key: str
    base_url: str
    path: str = "/v1/chat"
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    prompt_field: str = "prompt"
    answer_field: str = "answer"
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "JevConfig":
        env = os.environ if env is None else env
        key = env.get("JEV_API_KEY", "").strip()
        if not key:
            raise JevError("JEV_API_KEY is not set. Put it in .env; never commit it.")
        base = env.get("JEV_BASE_URL", "").strip().rstrip("/")
        if not base:
            raise JevError("JEV_BASE_URL is not set. Take it from the jev.ai documentation.")
        return cls(
            api_key=key,
            base_url=base,
            path=env.get("JEV_PATH", cls.path),
            auth_header=env.get("JEV_AUTH_HEADER", cls.auth_header),
            auth_scheme=env.get("JEV_AUTH_SCHEME", cls.auth_scheme),
            prompt_field=env.get("JEV_PROMPT_FIELD", cls.prompt_field),
            answer_field=env.get("JEV_ANSWER_FIELD", cls.answer_field),
        )


def cache_key(question: str, context: str) -> str:
    return hashlib.sha256(f"{context}\n---\n{question.strip().lower()}".encode()).hexdigest()[:32]


def read_cache(key: str, directory: Path = CACHE_DIR) -> dict | None:
    path = directory / f"{key}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(key: str, question: str, answer: str, directory: Path = CACHE_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{key}.json").write_text(
        json.dumps({"question": question, "answer": answer}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _extract(payload: object, field: str) -> str:
    node = payload
    for part in field.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            raise JevError(f"Response has no field {field!r}. Set JEV_ANSWER_FIELD.")
    if not isinstance(node, str):
        raise JevError(f"Field {field!r} is not text.")
    return node


def ask(
    question: str,
    *,
    context: str = GAME_CONTEXT,
    config: JevConfig | None = None,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, bool]:
    """Return (answer, from_cache). A cached answer needs no key."""
    key = cache_key(question, context)
    if not refresh:
        cached = read_cache(key, cache_dir)
        if cached is not None:
            return cached["answer"], True
    config = config or JevConfig.from_env()
    headers = {config.auth_header: f"{config.auth_scheme} {config.api_key}".strip()}
    body = {config.prompt_field: f"{context}\n\n{question}"}
    try:
        with httpx.Client(timeout=config.timeout, transport=transport) as client:
            response = client.post(config.base_url + config.path, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise JevError(f"jev.ai request failed: {type(exc).__name__}") from None
    if response.status_code >= 400:
        raise JevError(f"jev.ai answered HTTP {response.status_code}")
    try:
        answer = _extract(response.json(), config.answer_field)
    except ValueError:
        raise JevError("jev.ai answer was not JSON") from None
    write_cache(key, question, answer, cache_dir)
    return answer, False
