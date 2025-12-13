from fastapi import FastAPI
from pydantic import BaseModel

from .answer_manager import AnswerManager
from .vector_db import similarity

app = FastAPI()

answer_mgr = AnswerManager(answers_path="data/answers.txt")

class SimilarityRequest(BaseModel):
    word: str

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/today")
def today():
    st = answer_mgr.get_state()
    return {"date": st.date, "answer": st.answer}

@app.post("/similarity")
def get_similarity(req: SimilarityRequest):
    st = answer_mgr.get_state()
    guess = req.word.strip()
    answer = st.answer

    sim = similarity(guess, answer)

    return {
        "date": st.date,
        "answer": answer,
        "word": guess,
        "similarity": sim,
        "mode": "mock"  # 지금은 VDB_MODE 기본이 mock이라 이렇게 표시
    }