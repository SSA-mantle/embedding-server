from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence


# ===== 공통 타입 =====
Vector = Sequence[float]


@dataclass(frozen=True)
class Neighbor:
    """
    kNN 결과 한 항목.
    - word: 이웃 단어
    - score: 유사도/점수 (정규화 여부는 어댑터 정책에 따름)
    """
    word: str
    score: float


@dataclass
class TodayAnswerState:
    """
    파이썬 서버가 메모리에 들고 있을 '오늘 정답' 상태.
    - date: YYYY-MM-DD (KST 기준)
    - answer: 정답 단어
    - answer_vector: 정답 벡터 (매 요청마다 DB에서 다시 안 가져오려고 캐시)
    """
    date: str
    answer: str
    answer_vector: Optional[List[float]]


# ===== Ports (인터페이스) =====

class AnswerSourcePort(Protocol):
    """
    정답 후보 리스트를 어디서 가져오는지(파일/DB/HTTP 등)는 어댑터가 책임.
    유스케이스는 '정답 후보 문자열 리스트'만 받는다.
    """
    def list_answers(self) -> List[str]:
        ...


class AnswerPickerPort(Protocol):
    """
    '오늘의 정답을 어떻게 뽑는가'는 정책(도메인 규칙)에 해당.
    - 예: 날짜 해시 기반(결정적), 랜덤(시드 고정), 특정 룰 기반 등
    """
    def pick(self, date: str, candidates: List[str]) -> str:
        ...


class VectorStorePort(Protocol):
    """
    벡터 저장소(OpenSearch 등) 접근 Port.
    유스케이스는 '벡터를 얻는다', 'kNN을 한다'만 원한다.
    """
    def get_vector(self, word: str) -> Optional[List[float]]:
        ...

    def knn(self, vector: Vector, k: int) -> List[Neighbor]:
        ...


class DailyCachePort(Protocol):
    """
    Top-1000과 오늘 정답을 저장하는 캐시(Redis) Port.
    키 설계/파이프라인/삭제 전략 등은 Redis 어댑터가 책임.
    """
    def get_active_date(self) -> Optional[str]:
        ...

    def set_active_date(self, date: str) -> None:
        ...

    def save_daily_answer(self, date: str, answer: str) -> None:
        ...

    def save_daily_topk(self, date: str, items: List[Neighbor]) -> None:
        ...

    def delete_daily(self, date: str) -> None:
        ...


class TodayAnswerStatePort(Protocol):
    """
    파이썬 서버 프로세스 메모리에 들고 있는 '오늘 정답 상태' 접근 Port.
    """
    def get(self) -> Optional[TodayAnswerState]:
        ...

    def set(self, state: TodayAnswerState) -> None:
        ...
