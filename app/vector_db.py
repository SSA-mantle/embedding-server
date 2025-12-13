from __future__ import annotations

import os
import math
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple


# =========================================
# 0) 설정: 나중에 Docker/AWS에서 환경변수로 변경 가능
# =========================================
@dataclass(frozen=True)
class VectorDBConfig:
    # 기본은 mock. OpenSearch 붙일 때 "opensearch"로 변경
    mode: str = os.getenv("VDB_MODE", "mock")  # "mock" | "opensearch"

    # OpenSearch 연결 정보(나중에만 사용)
    host: str = os.getenv("OS_HOST", "localhost")
    port: int = int(os.getenv("OS_PORT", "9200"))
    index: str = os.getenv("OS_INDEX", "ssamentle-words")


# =========================================
# 1) 공통 유틸: 코사인 유사도
# =========================================
def cosine_similarity(a: List[float], b: List[float]) -> Optional[float]:
    """a, b 벡터의 코사인 유사도(0~1 근처)를 반환. 계산 불가면 None."""
    if len(a) != len(b) or len(a) == 0:
        return None

    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y

    if na == 0.0 or nb == 0.0:
        return None

    return dot / (math.sqrt(na) * math.sqrt(nb))


# =========================================
# 2) 인터페이스: "벡터를 가져오는 방법"만 구현하면 나머지는 공통 처리 가능
# =========================================
class VectorDB:
    def get_vector(self, word: str) -> Optional[List[float]]:
        """단어 -> 벡터. 없으면 None."""
        raise NotImplementedError

    def similarity(self, guess: str, answer: str) -> Optional[float]:
        """guess vs answer 유사도"""
        v1 = self.get_vector(guess.strip())
        v2 = self.get_vector(answer.strip())
        if v1 is None or v2 is None:
            return None
        return cosine_similarity(v1, v2)

    def neighbors(self, answer: str, k: int = 1000) -> List[Tuple[str, float]]:
        """정답 기준 top-k 이웃 (단어, 점수). 나중에 worker에서 사용."""
        raise NotImplementedError


# =========================================
# 3) MOCK 구현: 지금(OpenSearch 안 띄운 상태) 서버 테스트용
# =========================================
class MockVectorDB(VectorDB):
    """
    실제 의미 있는 유사도가 아니라,
    "서버가 동작하는지" 확인하기 위한 결정적(deterministic) 가짜 벡터 생성기.
    한글 단어도 utf-8로 해시하므로 문제 없음.
    """

    def get_vector(self, word: str) -> Optional[List[float]]:
        if not word:
            return None

        # 단어를 sha256으로 해싱해서 300차원처럼 보이는 가짜 벡터 생성
        h = hashlib.sha256(word.encode("utf-8")).digest()  # 32 bytes
        base = [(b - 128) / 128.0 for b in h]              # 32 floats-ish
        vec = (base * (300 // len(base) + 1))[:300]        # 300 dims
        return vec

    def neighbors(self, answer: str, k: int = 1000) -> List[Tuple[str, float]]:
        # 테스트용: word_0001 ~ word_1000
        out = []
        for i in range(1, k + 1):
            w = f"word_{i:04d}"
            sim = 1.0 - (i - 1) / k
            out.append((w, sim))
        return out


# =========================================
# 4) OpenSearch 구현: 나중에 OpenSearch 띄우고 .vec 적재되면 활성화
# =========================================
class OpenSearchVectorDB(VectorDB):
    """
    전제(강력 추천):
      - OpenSearch에 벡터를 넣을 때 문서의 _id 를 단어(word)로 저장해라.
        그래야 get_vector가 'GET index/_doc/{word}' 한 방으로 끝난다.

    지금은 OpenSearch를 안 띄운다고 했으니, 실제 사용은 나중에!
    """

    def __init__(self, cfg: VectorDBConfig):
        # VDB_MODE=opensearch 일 때만 opensearch-py가 필요하도록 '지연 import'
        from opensearchpy import OpenSearch

        self.cfg = cfg
        self.client = OpenSearch(hosts=[{"host": cfg.host, "port": cfg.port}])

    def get_vector(self, word: str) -> Optional[List[float]]:
        if not word:
            return None
        try:
            # _id = word 로 저장했다는 가정
            res = self.client.get(index=self.cfg.index, id=word)
            src = res.get("_source", {})
            vec = src.get("vector")
            return vec
        except Exception:
            return None

    def neighbors(self, answer: str, k: int = 1000) -> List[Tuple[str, float]]:
        # answer의 벡터로 kNN 검색
        v = self.get_vector(answer.strip())
        if v is None:
            return []

        body = {
            "size": k,
            "_source": ["word"],
            "query": {
                "knn": {
                    "vector": {
                        "vector": v,
                        "k": k
                    }
                }
            }
        }

        res = self.client.search(index=self.cfg.index, body=body)
        hits = res.get("hits", {}).get("hits", [])

        out: List[Tuple[str, float]] = []
        for h in hits:
            w = h.get("_source", {}).get("word")
            score = h.get("_score")  # OpenSearch 점수(코사인과 동일 스케일일 수도/아닐 수도 있음)
            if w is not None and score is not None:
                out.append((w, float(score)))
        return out


# =========================================
# 5) 팩토리 + 함수 래퍼: main.py에서 "from .vector_db import similarity" 그대로 쓰게 맞춤
# =========================================
def get_vector_db(cfg: Optional[VectorDBConfig] = None) -> VectorDB:
    cfg = cfg or VectorDBConfig()
    if cfg.mode == "mock":
        return MockVectorDB()
    if cfg.mode == "opensearch":
        return OpenSearchVectorDB(cfg)
    raise RuntimeError(f"Unknown VDB_MODE={cfg.mode}")


# 앱 전체에서 하나만 쓰는 인스턴스(싱글톤처럼)
_vdb = get_vector_db()


def similarity(guess: str, answer: str) -> Optional[float]:
    """
    main.py에서 호출할 함수.
    - guess: 입력 단어
    - answer: 오늘 정답 단어
    """
    return _vdb.similarity(guess, answer)


def neighbors(answer: str, k: int = 1000) -> List[Tuple[str, float]]:
    """
    나중에 하루 1번 작업에서 사용할 함수.
    - answer 기준 top-k 이웃 반환
    """
    return _vdb.neighbors(answer, k)
