from backend.rules.validation import validate_operational_fields


def test_complete_request_is_valid(make_request):
    result = validate_operational_fields(make_request())
    assert result.valid is True
    assert result.missing_fields == []


def test_missing_operational_fields_are_returned(make_request):
    result = validate_operational_fields(
        make_request(host_name=None, visit_purpose=None, identity_document_type=None)
    )
    assert result.valid is False
    assert set(result.missing_fields) == {"host_name", "visit_purpose", "identity_document_type"}
