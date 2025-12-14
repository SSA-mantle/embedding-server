from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Optional

from app.application.ports import TodayAnswerState, TodayAnswerStatePort


class InMemoryTodayAnswerStateStore(TodayAnswerStatePort):
    """
    프로세스 메모리에 '오늘 정답 상태'를 저장하는 어댑터.

    - FastAPI 프로세스가 1개일 때 가장 단순하고 빠름
    - 나중에 멀티 인스턴스/스케일아웃하면
      이 저장소는 각 인스턴스마다 따로 존재하므로
      '정답 캐시'는 Redis/DB로 옮기거나 다른 전략이 필요함
    """

    def __init__(self):
        self._lock = RLock()
        self._state: Optional[TodayAnswerState] = None

    def get(self) -> Optional[TodayAnswerState]:
        with self._lock:
            return self._state

    def set(self, state: TodayAnswerState) -> None:
        with self._lock:
            self._state = state
