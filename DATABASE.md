## 1) Redis (DailyCache)

### Key Prefix
- 기본 prefix: `ssamantle` (환경변수 `REDIS_KEY_PREFIX`)

### Keys & Types
- `ssamantle:active_date` (STRING)
  - 값: `"YYYY-MM-DD"`
  - 의미: 현재 서비스에서 “활성 날짜(오늘)”로 간주하는 날짜

- `ssamantle:{date}:answer` (STRING)
  - 값: `"정답단어"`
  - 예: `ssamantle:2025-12-16:answer`

- `ssamantle:{date}:topk` (ZSET)
  - member: `word` (단어)
  - score: `similarity` (유사도 점수, float)
  - 예: `ssamantle:2025-12-16:topk`

### 저장 방식
- `save_daily_topk(date, items)` 실행 시:
  1) 기존 `ssamantle:{date}:topk` 삭제(DEL)
  2) 새 ZSET으로 ZADD 삽입(덮어쓰기 방식)
- items(List[Neighbor])가 정렬되어 있지 않아도 상관 없음  
  → ZSET은 score 기준으로 정렬된 구조로 관리됨
- score 동일 시: member(문자열) 사전순으로 tie-break

### 조회 예시
- top-k (유사도 높은 순):
  - `ZREVRANGE ssamantle:{date}:topk 0 {k-1} WITHSCORES`
- 특정 단어 점수:
  - `ZSCORE ssamantle:{date}:topk {word}`
- 특정 단어 순위:
  - `ZREVRANK ssamantle:{date}:topk {word}`

### 삭제 정책
- `delete_daily(date)`:
  - `ssamantle:{date}:answer`, `ssamantle:{date}:topk`를 삭제
  - 키가 없어도 DEL은 에러 없이 무시(삭제 개수 0)
- 운영 정책(권장): “전날은 유지, 전전날(D-2)만 삭제”


---

## 2) Vector DB (OpenSearch)

### Index 개념
- OpenSearch의 `index`는 문서들을 담는 “저장 공간(테이블 유사)”  
- 기본 인덱스명: `ssamantle-words` (환경변수 `OS_INDEX`)

### 문서 스키마(전제)
- 문서 1개 = 단어 1개
- 문서 `_id` = `word`
- `_source`:
  ```json
  {
    "word": "<단어>",
    "vector": [<float>, <float>, ...]  // dimension=dim
  }