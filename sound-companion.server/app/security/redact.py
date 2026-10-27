"""The one function every `app_logs` row passes through (docs/SECURITY.md): long text is cut, anything
that looks like an API key is masked. Rows hold ids, names, scores and timings, so what this catches is
what leaks in by accident: an exception text that quotes a request, a tool argument."""
import re

MAX_TEXT = 300
MASK = "[redacted]"

# OpenRouter and OpenAI style keys, and bearer tokens
KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE)


def configured_secrets() -> tuple[str, ...]:
    """The key from the settings, masked by value even when it does not look like a key."""
    from app.config import settings

    return tuple(s for s in (settings.openrouter_api_key, settings.postgres_password) if len(s) >= 6)


def redact_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    # masked before cutting, so a key on the cut line is never left half visible
    for secret in secrets:
        text = text.replace(secret, MASK)
    text = KEY_PATTERN.sub(MASK, text)
    return text if len(text) <= MAX_TEXT else f"{text[:MAX_TEXT]}... [{len(text) - MAX_TEXT} more characters]"


def redact(value, secrets: tuple[str, ...] | None = None):
    """A copy of `value` (strings, numbers, lists, dicts) that is safe to store."""
    if secrets is None:
        secrets = configured_secrets()
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {str(key): redact(item, secrets) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    return value
