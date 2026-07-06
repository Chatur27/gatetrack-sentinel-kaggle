from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from backend.policies.repository import PolicyRepository
from backend.schemas import VisitorRequest
from backend.services.reviewer import MockReviewProvider
from backend.services.workflow import WorkflowService
from backend.storage.sqlite import SQLiteStore

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def base_payload() -> dict:
    return {
        "visitor_name": "Alex Morgan",
        "visitor_type": "guest",
        "host_name": "Jordan Lee",
        "host_confirmed": True,
        "organisation": "Demo Consulting Ltd",
        "visit_purpose": "Project meeting",
        "visit_date": "2026-06-28",
        "arrival_time": "10:00",
        "expected_duration_minutes": 60,
        "requested_area": "meeting_room",
        "identity_document_type": "passport",
        "visits_last_30_days": 0,
        "additional_notes": "Reception meeting only.",
    }


@pytest.fixture
def make_request(base_payload):
    def factory(**overrides) -> VisitorRequest:
        payload = deepcopy(base_payload)
        payload.update(overrides)
        return VisitorRequest.model_validate(payload)
    return factory


@pytest.fixture
def service() -> WorkflowService:
    store = SQLiteStore(":memory:")
    return WorkflowService(
        store=store,
        policies=PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json"),
        reviewer=MockReviewProvider(),
    )
