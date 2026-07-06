from __future__ import annotations

from pathlib import Path

from backend.policies.repository import PolicyRepository

_POLICY_PATH = Path(__file__).resolve().parent / "data" / "visitor_policy.json"
_REPOSITORY = PolicyRepository(_POLICY_PATH)


def get_visitor_policy(section_id: str) -> dict:
    """Return one fictional visitor-policy section by identifier."""
    policy = _REPOSITORY.get(section_id)
    if policy is None:
        return {"found": False, "section_id": section_id}
    return {"found": True, "policy": policy.model_dump(mode="json")}


def search_policy(query: str) -> dict:
    """Search the fictional visitor-policy corpus using keywords."""
    results = _REPOSITORY.search(query)
    return {
        "query": query,
        "count": len(results),
        "results": [result.model_dump(mode="json") for result in results],
    }


def get_access_rule(area: str) -> dict:
    """Return the fictional access rule for a requested area."""
    results = _REPOSITORY.get_access_rule(area)
    return {
        "area": area,
        "results": [result.model_dump(mode="json") for result in results],
    }


def get_operating_hours() -> dict:
    """Return the fictional organisation's operating hours."""
    return dict(_REPOSITORY.operating_hours)


def get_required_documents(visitor_type: str) -> dict:
    """Return the minimum fictional document categories for a visitor type."""
    return {
        "visitor_type": visitor_type,
        "required_documents": _REPOSITORY.get_required_documents(visitor_type),
    }
