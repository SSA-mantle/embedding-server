from fastapi import FastAPI

from .answer_manager import AnswerManager

app = FastAPI()

answer_mgr = AnswerManager(answers_path="data/answers.txt")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/today")
def today():
    st = answer_mgr.get_state()
    return {"date": st.date, "answer": st.answer}