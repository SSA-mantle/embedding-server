from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Protocol


# -----------------------------
# 이 파일이 기대하는 "의존성(인터페이스)"
# - AnswerManager: refresh_today() / get_state()
# - VectorDB: get_vector() / neighbors()
# - Redis: get/set/delete/zadd/pipeline
# -----------------------------

class AnswerManagerLike(Protocol):
    def refresh_today(self): ...
    def get_state(self): ...


class VectorDBLike(Protocol):
    def get_vector(self, word: str) -> Optional[List[float]]: ...
    def neighbors(self, answer: str, k: int = 1000) -> List[Tuple[str, float]]: ...


@dataclass
class RefreshResult:
    date: str
    answer: str
    answer_vector: Optional[List[float]]
    topk: List[Tuple[str, float]]  # (word, score)


def _key_active_date(prefix: str) -> str:
    return f"{prefix}:active_date"


def _key_answer(prefix: str, date: str) -> str:
    return f"{prefix}:{date}:answer"


def _key_topk(prefix: str, date: str) -> str:
    return f"{prefix}:{date}:top1000"  # zset (member=word, score=similarity)


def run_daily_refresh(
    *,
    answer_mgr: AnswerManagerLike,
    vdb: VectorDBLike,
    redis_client=None,
    k: int = 1000,
    key_prefix: str = "ssamentle",
) -> RefreshResult:
    """
    매일 1번(예: 새벽 1시)에 호출될 갱신 작업.

    1) 오늘 정답 단어 확정 (answer_mgr)
    2) 정답 벡터 조회 (vdb.get_vector)  -> 메인에서 메모리로 들고 있으려고 반환
    3) 정답 기준 top-k 이웃 조회 (vdb.neighbors)
    4) redis_client가 있으면 Redis에 저장 + 이전 날짜 키 삭제

    반환값(RefreshResult)은 main에서 메모리 캐시(정답 단어/벡터) 업데이트에 사용.
    """

    # 1) 오늘 정답 확정
    state = answer_mgr.refresh_today()  # "스케줄러가 호출하는 순간" 갱신시키는 의도
    date = state.date
    answer = state.answer

    # 2) 정답 벡터(메모리에 저장할 값)
    answer_vector = vdb.get_vector(answer)

    # 3) top-k 계산 (Redis에 저장할 값)
    topk = vdb.neighbors(answer, k)

    # 4) Redis 저장(있을 때만)
    if redis_client is not None:
        active_key = _key_active_date(key_prefix)
        new_answer_key = _key_answer(key_prefix, date)
        new_topk_key = _key_topk(key_prefix, date)

        prev_date = redis_client.get(active_key)
        prev_answer_key = _key_answer(key_prefix, prev_date) if prev_date else None
        prev_topk_key = _key_topk(key_prefix, prev_date) if prev_date else None

        pipe = redis_client.pipeline(transaction=True)

        # (중요) 새 날짜 키 먼저 완성 → 마지막에 active_date 스위치
        pipe.set(new_answer_key, answer)
        pipe.delete(new_topk_key)

        # zset 저장: member=word, score=similarity
        # (topk가 비어도 저장은 진행)
        mapping: Dict[str, float] = {}
        for w, score in topk:
            mapping[w] = float(score)
        if mapping:
            pipe.zadd(new_topk_key, mapping)

        pipe.set(active_key, date)
        pipe.execute()

        # 이전 날짜 키 삭제 (요구사항 4번)
        if prev_date and prev_date != date:
            redis_client.delete(prev_answer_key)
            redis_client.delete(prev_topk_key)

    return RefreshResult(date=date, answer=answer, answer_vector=answer_vector, topk=topk)
