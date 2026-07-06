from __future__ import annotations

import re

from backend.schemas import SecurityFinding, SecurityResult, SecurityStatus

_BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "PROMPT_OVERRIDE",
        re.compile(r"\b(ignore|disregard)\b.{0,40}\b(previous|prior|all|your)\b.{0,30}\b(instructions?|rules?|policies?)\b", re.I | re.S),
        "Instruction-override pattern detected.",
    ),
    (
        "SECRET_EXTRACTION",
        re.compile(r"\b(reveal|show|print|expose)\b.{0,50}\b(system prompt|credentials?|api keys?|secrets?|hidden instructions?)\b", re.I | re.S),
        "Protected-instruction or credential-extraction pattern detected.",
    ),
    (
        "CONTROL_BYPASS",
        re.compile(r"\b(bypass|override|disable)\b.{0,50}\b(policy|policies|security|controls?|approval)\b", re.I | re.S),
        "Control-bypass pattern detected.",
    ),
    (
        "DANGEROUS_COMMAND",
        re.compile(r"(<script\b|\brm\s+-rf\b|\bdrop\s+table\b|\bpowershell\s+-enc\b)", re.I),
        "Potentially dangerous command or script pattern detected.",
    ),
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{7,}\d)(?!\d)")
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return _LONG_NUMBER_RE.sub("[REDACTED_NUMBER]", text)


def scan_input(notes: str) -> SecurityResult:
    findings: list[SecurityFinding] = []

    for code, pattern, message in _BLOCK_PATTERNS:
        if pattern.search(notes):
            findings.append(SecurityFinding(code=code, severity="high", message=message))

    if _EMAIL_RE.search(notes) or _PHONE_RE.search(notes) or _LONG_NUMBER_RE.search(notes):
        findings.append(
            SecurityFinding(
                code="POSSIBLE_EXCESS_PII",
                severity="medium",
                message="Potential unnecessary personal information was detected and redacted in logs.",
            )
        )

    if any(f.severity == "high" for f in findings):
        status = SecurityStatus.BLOCKED
    elif findings:
        status = SecurityStatus.WARNING
    else:
        status = SecurityStatus.PASSED

    return SecurityResult(status=status, findings=findings, sanitized_notes=_redact(notes))
