"""Regex-based scrubber applied to anything captured in a trace or persisted
debug record (``generation_attempts``, ``generation_metadata``) before it is
stored or served through the API. Traces exist to help debug the pipeline —
they should never become a second place secrets or PII leak out through.
"""

import re
from typing import Any

_PATTERNS = [
    # DB connection strings with embedded credentials — must run before the
    # email pattern below, which would otherwise partially match the
    # "user:password@host" segment and leave the scheme/host exposed.
    (
        re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^:\s]+:[^@\s]+@[^\s\"']+"),
        "[REDACTED_CONNECTION_STRING]",
    ),
    # bearer tokens / raw Authorization header values
    (re.compile(r"[Bb]earer\s+[A-Za-z0-9\-_.]+"), "Bearer [REDACTED_TOKEN]"),
    # API-key-shaped tokens: our own ipk_..., OpenAI-style sk-..., Mistral-style keys
    (re.compile(r"\b(ipk_|sk-)[A-Za-z0-9\-_]{16,}"), "[REDACTED_API_KEY]"),
    # email addresses
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
]


def redact_string(value: str) -> str:
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact_value(value: Any) -> Any:
    """Recursively redact every string found in a JSON-like structure."""
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, dict):
        return {key: redact_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value
