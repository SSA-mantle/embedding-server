from __future__ import annotations

from pathlib import Path
from typing import List

from app.application.ports import AnswerSourcePort


class FileAnswerSource(AnswerSourcePort):
    """
    정답 후보를 파일에서 읽어오는 어댑터.

    - 기본: UTF-8 텍스트 파일
    - 빈 줄 무시
    - 주석(# ...) 무시
    - 중복 제거(등장 순서 유지)
    - 한글/영문 모두 OK
    """

    def __init__(self, path: str, encoding: str = "utf-8"):
        self.path = Path(path)
        self.encoding = encoding

    def list_answers(self) -> List[str]:
        if not self.path.exists():
            raise FileNotFoundError(f"answers file not found: {self.path}")

        lines = self.path.read_text(encoding=self.encoding).splitlines()

        out: List[str] = []
        seen = set()

        for line in lines:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue

            if s not in seen:
                seen.add(s)
                out.append(s)

        return out
