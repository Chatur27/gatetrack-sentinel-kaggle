from __future__ import annotations

from datetime import time

from backend.schemas import (
    RequestedArea,
    RiskFactor,
    RiskResult,
    RiskRoute,
    SecurityResult,
    SecurityStatus,
    VisitorRequest,
)

RESTRICTED_AREAS = {
    RequestedArea.SERVER_ROOM,
    RequestedArea.FINANCE_OFFICE,
    RequestedArea.CONTROL_ROOM,
    RequestedArea.DATA_CENTRE,
}
OPEN_TIME = time(8, 0)
CLOSE_TIME = time(17, 30)


def calculate_risk(request: VisitorRequest, security: SecurityResult) -> RiskResult:
    if security.status == SecurityStatus.BLOCKED:
        return RiskResult(
            score=10,
            route=RiskRoute.BLOCKED,
            factors=[
                RiskFactor(
                    code="SECURITY_ATTACK_DETECTED",
                    points=10,
                    description="Unsafe or manipulative input was detected before model review.",
                )
            ],
        )

    factors: list[RiskFactor] = []

    if not request.host_confirmed:
        factors.append(
            RiskFactor(
                code="HOST_NOT_CONFIRMED",
                points=3,
                description="The named host has not been confirmed.",
            )
        )

    if request.arrival_time < OPEN_TIME or request.arrival_time > CLOSE_TIME:
        factors.append(
            RiskFactor(
                code="AFTER_HOURS",
                points=2,
                description="The visit is outside normal operating hours.",
            )
        )

    if request.requested_area in RESTRICTED_AREAS:
        factors.append(
            RiskFactor(
                code="RESTRICTED_AREA",
                points=3,
                description="The requested area is classified as restricted in the demo policy.",
            )
        )

    if request.expected_duration_minutes > 240:
        factors.append(
            RiskFactor(
                code="LONG_DURATION",
                points=1,
                description="The expected visit duration exceeds four hours.",
            )
        )

    if request.visits_last_30_days >= 3:
        factors.append(
            RiskFactor(
                code="REPEATED_VISITS",
                points=2,
                description="The visitor has three or more visits in the last 30 days.",
            )
        )

    score = sum(f.points for f in factors)
    if score <= 1:
        route = RiskRoute.LOW_RISK
    elif score <= 4:
        route = RiskRoute.HUMAN_REVIEW
    else:
        route = RiskRoute.ESCALATED_REVIEW

    return RiskResult(score=score, route=route, factors=factors)
