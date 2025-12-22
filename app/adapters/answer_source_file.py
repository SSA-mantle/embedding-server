from __future__ import annotations

from pathlib import Path
from typing import List

from app.application.ports import AnswerEntry, AnswerSourcePort


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
        p = Path(path)
        
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            p = (project_root / p).resolve()

        self.path = p
        self.encoding = encoding

    def list_answers(self) -> List[AnswerEntry]:
        if not self.path.exists():
            raise FileNotFoundError(f"answers file not found: {self.path}")

        lines = self.path.read_text(encoding=self.encoding).splitlines()

        out: List[AnswerEntry] = []
        seen = set()

        for line in lines:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue

            parts = s.split(maxsplit=1)
            word = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else None

            if word not in seen:
                seen.add(word)
                out.append(AnswerEntry(word=word, description=desc))

        return out
