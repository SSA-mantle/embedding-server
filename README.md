# embedding-server 로컬 실행 가이드 (OpenSearch + Redis)

아래 명령들을 **프로젝트 루트(embedding-server)** 에서 순서대로 실행하면 로컬에서 OpenSearch/Redis를 띄우고, `.vec`를 적재한 뒤, FastAPI 서버를 실행/검증할 수 있습니다.

---

## 1) 가상환경 생성 및 의존성 설치

```powershell
conda create -n ssafy-corpus python=3.11 -y
conda activate ssafy-corpus
pip install -r requirements.txt
```

---

## 2) 컨테이너 생성 (OpenSearch + Redis)

```powershell
docker compose up -d
docker compose ps
```

---

## 3) OpenSearch(벡터 DB)로 데이터 적재 (.vec → index)

```powershell
python -m app.entrypoints.cli.load_vec_to_opensearch --vec ".\data\cc.ko.300.ssafy_v1.clean.vec" --recreate-index
```

---

## 4) 앱 실행 (FastAPI)

```powershell
uvicorn app.main:app --reload --port 8000
```

---

## 4) 앱 실행 (FastAPI)

```powershell
uvicorn app.main:app --reload --port 8000
```

---

## 5) Health 확인

```powershell
curl.exe http://127.0.0.1:8000/health
```

- 아니면 브라우저에서 `http://127.0.0.1:8000/docs`
- 정상 기대값:
  - ok = true
  - vector_store_ready = true
  - redis_cache_ready = true
 
---

## 6) Redis에 저장된 데이터 확인 (명령어 3개)

```powershell
docker exec -it ssamentle-redis redis-cli keys "ssamentle:*"
docker exec -it ssamentle-redis redis-cli get "ssamentle:active_date"
docker exec -it ssamentle-redis redis-cli zrevrange "ssamentle:2025-12-16:topk" 0 20 withscores
```
