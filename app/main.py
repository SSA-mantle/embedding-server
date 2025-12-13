from fastapi import FastAPI
from pydantic import BaseModel

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .answer_manager import AnswerManager
from .vector_db import get_vector_db, cosine_similarity
from .refresh_job import run_daily_refresh

KST = ZoneInfo("Asia/Seoul")

app = FastAPI()

answer_mgr = AnswerManager(answers_path="data/answers.txt")
vdb = get_vector_db()

TODAY = {
    "date": None,
    "answer": None,
    "answer_vector": None,
}

scheduler = BackgroundScheduler(timezone=KST)

class SimilarityRequest(BaseModel):
    word: str

def refresh_today_cache():
    """
    매일 1시에 실행될 작업:
    - 오늘 정답 확정
    - 정답 벡터 조회
    - top1000 계산 후 Redis 저장 (지금은 redis_client=None)
    - TODAY 캐시 갱신
    """
    result = run_daily_refresh(
        answer_mgr=answer_mgr,
        vdb=vdb,
        redis_client=None,   # 나중에 Redis 연결 시 여기만 바꾸면 됨
        k=1000,
        key_prefix="ssamentle",
    )
    TODAY["date"] = result.date
    TODAY["answer"] = result.answer
    TODAY["answer_vector"] = result.answer_vector

    print(f"[refresh] date={result.date}, answer={result.answer}, vec_ready={result.answer_vector is not None}")


def ensure_today_ready():
    # 서버 시작 직후 TODAY가 비어있으면 1번 채움
    if TODAY["date"] is None or TODAY["answer"] is None or TODAY["answer_vector"] is None:
        refresh_today_cache()


@app.on_event("startup")
def on_startup():
    # 1) 서버 켤 때 오늘 캐시를 먼저 채워둠
    ensure_today_ready()

    # 2) 매일 01:00(KST)에 캐시 갱신 작업 등록
    scheduler.add_job(
        refresh_today_cache,
        trigger=CronTrigger(hour=1, minute=0, timezone=KST),
        id="daily_refresh_1am",
        replace_existing=True,
    )

    scheduler.start()
    print("[scheduler] started")


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)
    print("[scheduler] stopped")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/today")
def today():
    _ensure_today_ready()
    return {"date": TODAY["date"], "answer": TODAY["answer"]}


@app.post("/similarity")
def get_similarity(req: SimilarityRequest):
    ensure_today_ready()

    guess = req.word.strip()
    if not guess:
        return {"similarity": None, "reason": "empty_word"}

    guess_vec = vdb.get_vector(guess)
    if guess_vec is None:
        return {
            "date": TODAY["date"],
            "answer": TODAY["answer"],
            "word": guess,
            "similarity": None,
            "reason": "guess_vector_not_found",
        }

    ans_vec = TODAY["answer_vector"]
    sim = cosine_similarity(guess_vec, ans_vec)
    return {
        "date": TODAY["date"],
        "answer": TODAY["answer"],
        "word": guess,
        "similarity": sim,
    }


# (개발 편의) 수동 갱신 엔드포인트: 테스트할 때만 사용
@app.post("/admin/refresh")
def admin_refresh():
    refresh_today_cache()
    return {"ok": True, "date": TODAY["date"], "answer": TODAY["answer"]}