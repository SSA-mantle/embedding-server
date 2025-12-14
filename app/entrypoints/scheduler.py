# app/entrypoints/scheduler.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SchedulerDeps:
    """
    스케줄러 엔트리포인트가 필요한 의존성.
    - 실제 작업 함수(refresh_today_job)는 main에서 만들어 주입한다.
    """
    timezone: ZoneInfo
    refresh_today_job: Callable[[], None]


class SchedulerRunner:
    """
    APScheduler를 감싸서
    - startup 시 start()
    - shutdown 시 stop()
    을 main에서 호출할 수 있게 해주는 얇은 래퍼.
    """

    def __init__(self, deps: SchedulerDeps):
        self.deps = deps
        self.scheduler = BackgroundScheduler(timezone=deps.timezone)
        self._registered = False

    def register_jobs(self) -> None:
        if self._registered:
            return

        self.scheduler.add_job(
            self.deps.refresh_today_job,
            trigger=CronTrigger(hour=1, minute=0, timezone=self.deps.timezone),
            id="daily_refresh_1am",
            replace_existing=True,
        )
        self._registered = True

    def start(self) -> None:
        self.register_jobs()
        self.scheduler.start()
        print("[scheduler] started")

    def stop(self) -> None:
        # APScheduler가 이미 종료된 상태일 수도 있으니 예외 없이 종료
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass
        print("[scheduler] stopped")
