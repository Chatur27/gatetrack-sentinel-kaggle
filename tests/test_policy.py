from pathlib import Path

from backend.policies.repository import PolicyRepository

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_policy_search_returns_after_hours_rule():
    repo = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json")
    results = repo.search("after hours contractor")
    assert results
    assert results[0].id == "VP-4.3"


def test_restricted_area_rule_is_returned():
    repo = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json")
    results = repo.get_access_rule("server_room")
    assert results[0].id == "VP-3.2"
