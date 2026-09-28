from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LeakFinding:
    kind: str
    value: str
    suggestion: str


LEAK_SCANNERS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("api_key", re.compile(r"sk-[A-Za-z0-9]{20,}"), "process.env.OPENAI_API_KEY"),
    ("api_key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "process.env.OPENAI_API_KEY"),
    ("api_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "process.env.ANTHROPIC_API_KEY"),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{36,}"), "process.env.GITHUB_TOKEN"),
    ("github_token", re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "process.env.GITHUB_TOKEN"),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), "process.env.AWS_ACCESS_KEY_ID"),
    ("bearer_token", re.compile(r"Bearer\\s+[A-Za-z0-9._~+/-]{20,}=*", re.IGNORECASE), "process.env.AUTH_TOKEN"),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\\.eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]{20,}"), "process.env.JWT"),
    ("password_assignment", re.compile(r"password[=:]\\s*[\"']?[^\\s\"',;)}\\]]{6,}[\"']?", re.IGNORECASE), "process.env.PASSWORD"),
    ("secret_assignment", re.compile(r"secret[=:]\\s*[\"']?[A-Za-z0-9._~+/-]{10,}[\"']?", re.IGNORECASE), "process.env.SECRET"),
    ("private_key_block", re.compile(r"-----BEGIN\\s+(?:RSA\\s+|EC\\s+|DSA\\s+|OPENSSH\\s+)?PRIVATE\\s+KEY-----"), "process.env.PRIVATE_KEY_PATH"),
    ("db_url", re.compile(r"(?:mongodb|postgres|postgresql|mysql|redis|amqp)://[^\\s\"',;)}\\]]{10,}", re.IGNORECASE), "process.env.DATABASE_URL"),
    ("discord_token", re.compile(r"\\b[MNO][A-Za-z0-9_-]{23,}\\.[A-Za-z0-9_-]{6}\\.[A-Za-z0-9_-]{27,}\\b"), "process.env.DISCORD_TOKEN"),
    ("slack_token", re.compile(r"xox[baprsv]-[A-Za-z0-9-]{10,}"), "process.env.SLACK_TOKEN"),
    ("npm_token", re.compile(r"npm_[A-Za-z0-9]{36,}"), "process.env.NPM_TOKEN"),
    ("basic_auth_url", re.compile(r"://[^@\\s:]+:[^@\\s]+@"), "process.env.SERVICE_URL"),
    ("local_path", re.compile(r"/home/[A-Za-z0-9_.-]+/"), "process.env.HOME"),
    ("local_path", re.compile(r"/Users/[A-Za-z0-9_.-]+/"), "process.env.HOME"),
    ("local_path", re.compile(r"[A-Z]:\\\\Users\\\\[A-Za-z0-9_.-]+\\\\"), "process.env.USERPROFILE"),
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"), "use redacted_email@example.invalid"),
)


def _clip(text: str, limit: int = 80) -> str:
    value = str(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def scan_text_for_leaks(content: str) -> tuple[LeakFinding, ...]:
    text = str(content or "")
    findings: list[LeakFinding] = []
    seen: set[str] = set()
    for kind, pattern, suggestion in LEAK_SCANNERS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            key = kind + ":" + raw
            if key in seen:
                continue
            seen.add(key)
            findings.append(LeakFinding(kind=kind, value=_clip(raw), suggestion=suggestion))
            if len(findings) >= 100:
                return tuple(findings)
    return tuple(findings)


def redact_sensitive_text(content: str, replacement: str = "[REDACTED]") -> str:
    text = str(content or "")
    redacted = text
    for _, pattern, _ in LEAK_SCANNERS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
