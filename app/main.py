from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from app.config import settings

from app.domain.answer_picker_hash import HashAnswerPicker

from app.adapters.answer_cache_memory import InMemoryTodayAnswerStateStore
from app.adapters.answer_source_file import FileAnswerSource
from app.adapters.vector_store_opensearch import OpenSearchVectorStore
from app.adapters.cache_redis import RedisDailyCache

from app.application.services.daily_refresh import run_daily_refresh

from app.entrypoints.api import ApiDeps, create_router
from app.entrypoints.scheduler import SchedulerDeps, SchedulerRunner

KST = ZoneInfo(settings.timezone)


def _today_str_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def create_app() -> FastAPI:
    """
    Composition Root (조립 전용)
    - 구현체(adapters) 생성
    - 정책(domain) 생성
    - 유스케이스(application) 실행 함수 준비
    - entrypoints(api/scheduler)에 의존성 주입
    """
    app = FastAPI()

    # ===== Adapters / Domain policy =====
    state_store = InMemoryTodayAnswerStateStore()
    answer_source = FileAnswerSource(path=settings.answers_path)
    answer_picker = HashAnswerPicker()

    # OpenSearch
    try:
        vector_store = OpenSearchVectorStore()
    except Exception as e:
        print(f"[warn] OpenSearchVectorStore init failed: {e}")
        vector_store = None  # type: ignore

    # Redis
    try:
        daily_cache = RedisDailyCache()
    except Exception as e:
        print(f"[warn] RedisDailyCache init failed: {e}")
        daily_cache = None  # type: ignore

    # ===== Use-case runner callbacks =====
    def refresh_today_job() -> None:
        if vector_store is None:
            print("[refresh] skipped (vector_store not ready)")
            return

        result = run_daily_refresh(
            date=_today_str_kst(),
            answer_source=answer_source,
            answer_picker=answer_picker,
            vector_store=vector_store,
            state_store=state_store,
            cache=daily_cache,
            k=1000,
        )
        print(
            f"[refresh] date={result.state.date}, answer={result.state.answer}, "
            f"vec_ready={result.state.answer_vector is not None}, topk={len(result.topk)}, "
            f"redis={'on' if daily_cache is not None else 'off'}"
        )

    def ensure_ready() -> None:
        if state_store.get() is None:
            refresh_today_job()

    # ===== Entrypoints: API Router =====
    router = create_router(
        ApiDeps(
            state_store=state_store,
            vector_store=vector_store,
            daily_cache=daily_cache,
            ensure_ready=ensure_ready,
            refresh_today_job=refresh_today_job,
        )
    )
    app.include_router(router)

    # ===== Entrypoints: Scheduler =====
    scheduler_runner = SchedulerRunner(
        SchedulerDeps(
            timezone=KST,
            refresh_today_job=refresh_today_job,
        )
    )

    @app.on_event("startup")
    def on_startup():
        ensure_ready()
        scheduler_runner.start()

    @app.on_event("shutdown")
    def on_shutdown():
        scheduler_runner.stop()

    return app


# uvicorn app.main:app 을 그대로 쓰기 위해 모듈 레벨 app 제공
app = create_app()
