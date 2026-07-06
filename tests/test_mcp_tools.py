from mcp_server.policy_tools import (
    get_access_rule,
    get_operating_hours,
    get_required_documents,
    get_visitor_policy,
    search_policy,
)


def test_read_only_policy_tools():
    assert get_visitor_policy("VP-1.1")["found"] is True
    assert search_policy("after hours contractor")["results"][0]["id"] == "VP-4.3"
    assert get_access_rule("server_room")["results"][0]["id"] == "VP-3.2"
    assert get_operating_hours()["weekdays"]["open"] == "08:00"
    assert "work order or service purpose" in get_required_documents("contractor")["required_documents"]
