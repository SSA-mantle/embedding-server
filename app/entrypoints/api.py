# app/entrypoints/api.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.similarity import cosine_similarity
from app.application.ports import TodayAnswerStatePort, VectorStorePort, DailyCachePort


class SimilarityRequest(BaseModel):
    word: str


@dataclass(frozen=True)
class ApiDeps:
    """
    API 라우터가 필요한 의존성 묶음(조립은 main.py에서).
    - entrypoints는 '호출'만 하고, 구현체 생성/결정은 main이 한다.
    """
    state_store: TodayAnswerStatePort
    vector_store: Optional[VectorStorePort]
    daily_cache: Optional[DailyCachePort]

    # main에서 만들어서 넘겨줄 콜백들
    ensure_ready: Callable[[], None]
    refresh_today_job: Callable[[], None]


def create_router(deps: ApiDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        return {
            "ok": True,
            "vector_store_ready": deps.vector_store is not None,
            "redis_cache_ready": deps.daily_cache is not None,
        }

    @router.get("/today")
    def today():
        deps.ensure_ready()
        st = deps.state_store.get()
        if st is None:
            return {"date": None, "answer": None}
        return {"date": st.date, "answer": st.answer}

    @router.post("/similarity")
    def similarity_api(req: SimilarityRequest):
        deps.ensure_ready()
        st = deps.state_store.get()

        if st is None:
            return {"similarity": None, "reason": "today_not_ready"}

        guess = req.word.strip()
        if not guess:
            return {"similarity": None, "reason": "empty_word"}

        if deps.vector_store is None:
            return {
                "date": st.date,
                "answer": st.answer,
                "word": guess,
                "similarity": None,
                "reason": "vector_store_not_ready",
            }

        guess_vec = deps.vector_store.get_vector(guess)
        if guess_vec is None:
            return {
                "date": st.date,
                "answer": st.answer,
                "word": guess,
                "similarity": None,
                "reason": "guess_vector_not_found",
            }

        if st.answer_vector is None:
            return {
                "date": st.date,
                "answer": st.answer,
                "word": guess,
                "similarity": None,
                "reason": "answer_vector_not_ready",
            }

        sim = cosine_similarity(guess_vec, st.answer_vector)
        return {"date": st.date, "answer": st.answer, "word": guess, "similarity": sim}

    @router.post("/admin/refresh")
    def admin_refresh():
        deps.refresh_today_job()
        st = deps.state_store.get()
        if st is None:
            return {"ok": False}
        return {"ok": True, "date": st.date, "answer": st.answer}

    return router
