from backend.schemas import ValidationResult, VisitorRequest

MANDATORY_OPERATIONAL_FIELDS = (
    "host_name",
    "visit_purpose",
    "identity_document_type",
)


def validate_operational_fields(request: VisitorRequest) -> ValidationResult:
    missing: list[str] = []
    notes: list[str] = []

    for field_name in MANDATORY_OPERATIONAL_FIELDS:
        value = getattr(request, field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field_name)

    if request.expected_duration_minutes < 15:
        notes.append("Expected duration is unusually short and should be confirmed.")
    if request.expected_duration_minutes > 720:
        notes.append("Expected duration exceeds the demonstration's normal one-day range.")

    return ValidationResult(valid=not missing, missing_fields=missing, notes=notes)
