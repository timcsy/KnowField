"""行為訊號擷取（US3、FR-012）。"""

from __future__ import annotations

from datetime import datetime

from ..models import BehaviorSignal
from ..store.repository import Repository


class BehaviorRecorder:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def record(self, item_id: int, action: str, at: datetime | None = None) -> None:
        self.repo.add_behavior(
            BehaviorSignal(item_id=item_id, action=action, at=at or datetime(2026, 7, 23))
        )
