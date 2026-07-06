from backend.rules.risk import calculate_risk
from backend.rules.security import scan_input
from backend.schemas import RiskRoute


def test_routine_case_is_low_risk(make_request):
    request = make_request()
    result = calculate_risk(request, scan_input(request.additional_notes))
    assert result.score == 0
    assert result.route == RiskRoute.LOW_RISK


def test_after_hours_case_needs_review(make_request):
    request = make_request(arrival_time="18:30")
    result = calculate_risk(request, scan_input(request.additional_notes))
    assert result.score == 2
    assert result.route == RiskRoute.HUMAN_REVIEW


def test_after_hours_restricted_case_is_escalated(make_request):
    request = make_request(arrival_time="18:30", requested_area="server_room")
    result = calculate_risk(request, scan_input(request.additional_notes))
    assert result.score == 5
    assert result.route == RiskRoute.ESCALATED_REVIEW
