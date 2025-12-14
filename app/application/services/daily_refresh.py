from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.application.ports import (
    AnswerPickerPort,
    AnswerSourcePort,
    DailyCachePort,
    Neighbor,
    TodayAnswerState,
    TodayAnswerStatePort,
    VectorStorePort,
)


@dataclass(frozen=True)
class DailyRefreshResult:
    state: TodayAnswerState
    topk: List[Neighbor]


def run_daily_refresh(
    *,
    date: str,
    answer_source: AnswerSourcePort,
    answer_picker: AnswerPickerPort,
    vector_store: VectorStorePort,
    state_store: TodayAnswerStatePort,
    cache: Optional[DailyCachePort] = None,
    k: int = 1000,
) -> DailyRefreshResult:
    """
    [유스케이스] 매일 1회(예: 01:00 KST) 실행될 갱신 작업

    1) 후보 로드(answer_source)
    2) 오늘 정답 선정(answer_picker)
    3) 정답 벡터 조회(vector_store.get_vector)
    4) top-k knn(vector_store.knn) + 정답 단어 제거 + 정확히 k개 맞춤
    5) (옵션) Redis 저장(cache)
    6) 메모리 상태 저장(state_store)
    """

    # 1) 후보 로드
    candidates = answer_source.list_answers()

    # 2) 오늘 정답 선정
    answer = answer_picker.pick(date, candidates).strip()

    # 3) 정답 벡터 조회 + 상태 저장(먼저 저장해두면 API에서 today 확인 가능)
    answer_vector = vector_store.get_vector(answer)
    today_state = TodayAnswerState(date=date, answer=answer, answer_vector=answer_vector)
    state_store.set(today_state)

    # 벡터가 없으면 topk는 비움(그래도 정답은 cache/state에 남길 수 있음)
    if answer_vector is None:
        topk: List[Neighbor] = []
        if cache is not None:
            prev_date = cache.get_active_date()
            cache.save_daily_answer(date, answer)
            cache.save_daily_topk(date, topk)
            cache.set_active_date(date)
            if prev_date and prev_date != date:
                cache.delete_daily(prev_date)
        return DailyRefreshResult(state=today_state, topk=topk)

    # 4) top-k knn + 정답 제거 + 정확히 k개 맞춤
    def normalize(w: str) -> str:
        return w.strip()

    def filter_and_dedupe(items: List[Neighbor]) -> List[Neighbor]:
        seen = set()
        out: List[Neighbor] = []
        for it in items:
            w = normalize(it.word)
            if not w or w == answer:
                continue
            if w in seen:
                continue
            seen.add(w)
            out.append(Neighbor(word=w, score=float(it.score)))
        return out

    # 1차: k+1 (정답이 섞일 가능성 대비)
    raw1 = vector_store.knn(answer_vector, k + 1)
    filtered = filter_and_dedupe(raw1)

    # 부족하면 2차: k+50 (예외 대비)
    if len(filtered) < k:
        raw2 = vector_store.knn(answer_vector, k + 50)
        filtered = filter_and_dedupe(raw2)

    topk = filtered[:k]

    # 5) Redis 저장(옵션)
    if cache is not None:
        prev_date = cache.get_active_date()

        cache.save_daily_answer(date, answer)
        cache.save_daily_topk(date, topk)
        cache.set_active_date(date)

        if prev_date and prev_date != date:
            cache.delete_daily(prev_date)

    return DailyRefreshResult(state=today_state, topk=topk)
