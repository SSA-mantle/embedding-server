from __future__ import annotations

from typing import List, Optional

from app.config import settings
from app.application.ports import DailyCachePort, Neighbor


class RedisDailyCache(DailyCachePort):
    """
    Redis를 DailyCachePort로 감싼 어댑터.

    키 설계(prefix=ssamentle):
      - ssamentle:active_date      (STRING) -> "YYYY-MM-DD"
      - ssamentle:{date}:answer    (STRING) -> "정답단어"
      - ssamentle:{date}:topk      (ZSET)   -> member=word, score=similarity
    """

    def __init__(self):
        import redis  # type: ignore

        cfg = settings.redis
        self.key_prefix = cfg.key_prefix

        self.client = redis.Redis(
            host=cfg.host,
            port=cfg.port,
            db=cfg.db,
            password=cfg.password,
            decode_responses=True,
        )

    # ---------- key helpers ----------
    def _k(self, suffix: str) -> str:
        return f"{self.key_prefix}:{suffix}"

    def _answer_key(self, date: str) -> str:
        return self._k(f"{date}:answer")

    def _topk_key(self, date: str) -> str:
        return self._k(f"{date}:topk")

    # ---------- port implementations ----------
    def get_active_date(self) -> Optional[str]:
        v = self.client.get(self._k("active_date"))
        return v if v else None

    def set_active_date(self, date: str) -> None:
        self.client.set(self._k("active_date"), date)

    def save_daily_answer(self, date: str, answer: str) -> None:
        self.client.set(self._answer_key(date), answer)

    def save_daily_topk(self, date: str, items: List[Neighbor]) -> None:
        """
        ZSET에 (word -> similarity score) 저장.
        """
        key = self._topk_key(date)

        pipe = self.client.pipeline()
        pipe.delete(key)

        mapping = {it.word: float(it.score) for it in items}
        if mapping:
            pipe.zadd(key, mapping)

        pipe.execute()

    def delete_daily(self, date: str) -> None:
        pipe = self.client.pipeline()
        pipe.delete(self._answer_key(date))
        pipe.delete(self._topk_key(date))
        pipe.execute()
