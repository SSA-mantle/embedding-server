from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Optional

from app.application.ports import TodayAnswerState, TodayAnswerStatePort


class InMemoryTodayAnswerStateStore(TodayAnswerStatePort):
    """
    프로세스 메모리에 '오늘 정답 상태'를 저장하는 어댑터.
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
