from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

KST = ZoneInfo("Asia/Seoul")

@dataclass
class AnswerState:
    date: str
    answer: str

class AnswerManager:
    """
    '오늘의 정답 단어'를 관리하는 클래스.

    - 후보 단어 목록(answers.txt)을 읽는다
    - 오늘 날짜(KST)를 기준으로 '항상 같은 정답'이 나오도록 결정한다
      (서버를 재시작해도 오늘 정답이 바뀌지 않게 하기 위함)
    """

    def __init__(self, answers_path: str):
        self.answers_path = Path(answers_path)
        self._state: AnswerState | None = None

    def _load_answers(self) -> list[str]:
        if not self.answers_path.exists():
            raise FileNotFoundError(f"answers file not found: {self.answers_path}")

        lines = self.answers_path.read_text(encoding="utf-8").splitlines()
        answers = [x.strip() for x in lines if x.strip()]

        if not answers:
            raise RuntimeError("answers file is empty")

        return answers

    def _today_str(self) -> str:
        # 한국 기준 날짜(YYYY-MM-DD)
        return datetime.now(KST).strftime("%Y-%m-%d")

    def _pick_deterministic(self, date_str: str, answers: list[str]) -> str:
        # 날짜 문자열을 해시해서 인덱스로 사용 → 오늘은 항상 같은 정답
        h = hashlib.sha256(date_str.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % len(answers)
        return answers[idx]

    def refresh_today(self) -> AnswerState:
        date_str = self._today_str()
        answers = self._load_answers()
        answer = self._pick_deterministic(date_str, answers)
        self._state = AnswerState(date=date_str, answer=answer)
        return self._state

    def get_state(self) -> AnswerState:
        today = self._today_str()
        if self._state is None or self._state.date != today:
            return self.refresh_today()
        return self._state
