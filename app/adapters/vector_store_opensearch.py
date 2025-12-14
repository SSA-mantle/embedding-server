from __future__ import annotations

from typing import List, Optional

from app.config import settings
from app.application.ports import Neighbor, Vector, VectorStorePort


class OpenSearchVectorStore(VectorStorePort):
    """
    OpenSearch 기반 VectorStore 어댑터.

    전제:
    - 문서 _id = word
    - _source에 {"word": "...", "vector": [...]} 가 저장
    """

    def __init__(self):
        from opensearchpy import OpenSearch, RequestsHttpConnection

        cfg = settings.opensearch
        self.index = cfg.index
        self.timeout = cfg.timeout
        self.num_candidates = cfg.num_candidates

        http_auth = None
        if cfg.username and cfg.password:
            http_auth = (cfg.username, cfg.password)

        self.client = OpenSearch(
            hosts=[{"host": cfg.host, "port": cfg.port}],
            http_auth=http_auth,
            use_ssl=cfg.use_ssl,
            verify_certs=cfg.verify_certs,
            connection_class=RequestsHttpConnection,
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
            retry_on_timeout=cfg.retry_on_timeout,
        )

    def get_vector(self, word: str) -> Optional[List[float]]:
        word = word.strip()
        if not word:
            return None
        try:
            res = self.client.get(index=self.index, id=word)
            src = res.get("_source", {}) or {}
            vec = src.get("vector")
            return vec
        except Exception:
            return None

    def knn(self, vector: Vector, k: int) -> List[Neighbor]:
        v = list(vector)

        knn_field = {"vector": v, "k": k}
        if self.num_candidates is not None:
            knn_field["num_candidates"] = self.num_candidates

        body = {
            "size": k,
            "_source": ["word"],
            "query": {
                "knn": {
                    "vector": knn_field
                }
            },
        }

        res = self.client.search(
            index=self.index,
            body=body,
            request_timeout=self.timeout,
        )
        hits = res.get("hits", {}).get("hits", []) or []

        out: List[Neighbor] = []
        for h in hits:
            src = h.get("_source", {}) or {}
            w = src.get("word") or h.get("_id")
            score = h.get("_score")
            if w is not None and score is not None:
                out.append(Neighbor(word=str(w), score=float(score)))
        return out
