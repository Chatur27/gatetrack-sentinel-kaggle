from __future__ import annotations

import json
import re
from pathlib import Path

from backend.schemas import PolicyReference, RiskResult, SecurityStatus


class PolicyRepository:
    def __init__(self, policy_path: str | Path):
        self.policy_path = Path(policy_path)
        payload = json.loads(self.policy_path.read_text(encoding="utf-8"))
        self._sections = payload["sections"]
        self.operating_hours = payload.get("operating_hours", {})
        self.required_documents = payload.get("required_documents", {})

    @property
    def section_count(self) -> int:
        return len(self._sections)

    def get(self, section_id: str) -> PolicyReference | None:
        for section in self._sections:
            if section["id"].lower() == section_id.lower():
                return PolicyReference(id=section["id"], title=section["title"], rule=section["rule"])
        return None

    def search(self, query: str, *, limit: int = 5) -> list[PolicyReference]:
        tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}
        scored: list[tuple[int, dict]] = []
        for section in self._sections:
            haystack = " ".join(
                [section["id"], section["title"], section["rule"], " ".join(section.get("tags", []))]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, section))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [
            PolicyReference(id=s["id"], title=s["title"], rule=s["rule"])
            for _, s in scored[:limit]
        ]

    def select_for_case(
        self, risk: RiskResult, security_status: SecurityStatus
    ) -> list[PolicyReference]:
        codes = {factor.code for factor in risk.factors}
        priority_ids: list[str] = []

        if security_status == SecurityStatus.BLOCKED:
            priority_ids.append("SEC-1.1")
        elif "AFTER_HOURS" in codes:
            priority_ids.append("VP-4.3")
        elif "RESTRICTED_AREA" in codes:
            priority_ids.append("VP-3.2")
        elif "HOST_NOT_CONFIRMED" in codes:
            priority_ids.append("VP-2.1")
        elif "REPEATED_VISITS" in codes:
            priority_ids.append("VP-5.1")
        else:
            priority_ids.append("VP-1.1")

        if "RESTRICTED_AREA" in codes and "VP-3.2" not in priority_ids:
            priority_ids.append("VP-3.2")
        if "HOST_NOT_CONFIRMED" in codes and "VP-2.1" not in priority_ids:
            priority_ids.append("VP-2.1")

        return [policy for section_id in priority_ids if (policy := self.get(section_id))]

    def get_access_rule(self, area: str) -> list[PolicyReference]:
        if area in {"server_room", "finance_office", "control_room", "data_centre"}:
            policy = self.get("VP-3.2")
        else:
            policy = self.get("VP-1.1")
        return [policy] if policy else []

    def get_required_documents(self, visitor_type: str) -> list[str]:
        return list(self.required_documents.get(visitor_type, []))
