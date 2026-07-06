from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Settings  # noqa: E402
from backend.policies.repository import PolicyRepository  # noqa: E402
from backend.schemas import VisitorRequest  # noqa: E402
from backend.services.reviewer import MockReviewProvider  # noqa: E402
from backend.services.workflow import WorkflowService  # noqa: E402
from backend.storage.sqlite import SQLiteStore  # noqa: E402


def main() -> None:
    settings = Settings.from_env()
    store = SQLiteStore(settings.db_path)
    service = WorkflowService(
        store=store,
        policies=PolicyRepository(settings.policy_path),
        reviewer=MockReviewProvider(),
    )
    examples = json.loads((REPO_ROOT / "data" / "synthetic_visitors.json").read_text())
    for example in examples:
        record = service.process(VisitorRequest.model_validate(example["input"]))
        print(f"{example['name']}: {record.case_id} -> {record.status.value}")


if __name__ == "__main__":
    main()
