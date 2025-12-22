from __future__ import annotations

import hashlib
from typing import List, Tuple

from app.application.ports import AnswerPickerPort

import random


class HashAnswerPicker(AnswerPickerPort):
    """
    날짜(date: 'YYYY-MM-DD')와 후보 리스트(candidates)로
    '오늘의 정답'을 결정적으로 뽑는 도메인 정책.

    특징
    - 같은 date + 같은 candidates면 항상 같은 정답
    - 후보 리스트의 순서가 바뀌어도 결과가 바뀌지 않음
      -> 각 후보에 대해 hash(date|candidate)를 계산하고, 가장 작은 hash를 가진 후보를 선택

    - 한글/영문 모두 utf-8로 처리
    """

    def pick(self, date: str, candidates: List[str]) -> str:
        if not candidates:
            raise ValueError("candidates is empty")

        # (hash값, 후보 문자열) 튜플 중 최소를 고름
        best: Tuple[bytes, str] | None = None

        for c in candidates:
            s = c.strip()
            if not s:
                continue

            key = f"{date}|{s}".encode("utf-8")
            h = hashlib.sha256(key).digest()

            item = (h, s)
            if best is None or item < best:
                best = item

        if best is None:
            raise ValueError("candidates contains no valid (non-empty) entries")

        return best[1]

    # def pick(self, date: str, candidates: List[str]) -> str:
    #     selected_candidate = random.choice(candidates)
    #     return selected_candidate