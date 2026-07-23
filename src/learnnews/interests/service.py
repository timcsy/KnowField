"""興趣畫像服務（US2、FR-008/009）。明講清單優先於學習權重（憲章原則 VI）。"""

from __future__ import annotations

from ..models import InterestProfile
from ..store.repository import Repository


class InterestService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def list_topics(self) -> list[str]:
        return self.repo.get_interest_profile().explicit_topics

    def add(self, topic: str) -> list[str]:
        p = self.repo.get_interest_profile()
        if topic not in p.explicit_topics:
            p.explicit_topics.append(topic)
        self.repo.save_interest_profile(p)
        return p.explicit_topics

    def remove(self, topic: str) -> list[str]:
        p = self.repo.get_interest_profile()
        p.explicit_topics = [t for t in p.explicit_topics if t != topic]
        # 明講移除即最終：同時清掉該主題的學習權重，杜絕「學習復活」
        p.learned_weights.pop(topic, None)
        self.repo.save_interest_profile(p)
        return p.explicit_topics

    def set(self, topics: list[str]) -> list[str]:
        p = self.repo.get_interest_profile()
        p.explicit_topics = list(dict.fromkeys(topics))  # 去重保序
        # 覆寫後，僅保留仍在明講清單中的學習權重
        p.learned_weights = {
            k: v for k, v in p.learned_weights.items() if k in p.explicit_topics
        }
        self.repo.save_interest_profile(p)
        return p.explicit_topics

    def profile(self) -> InterestProfile:
        return self.repo.get_interest_profile()
