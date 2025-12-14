from __future__ import annotations

import argparse
import os
from typing import Iterator, Optional, Tuple

from opensearchpy import OpenSearch, RequestsHttpConnection, helpers


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def build_client() -> OpenSearch:
    """
    환경변수 기반으로 OpenSearch 클라이언트 생성.

    - OS_HOST (default: localhost)
    - OS_PORT (default: 9200)
    - OS_USER / OS_PASSWORD (optional)
    - OS_USE_SSL (default: false)
    - OS_VERIFY_CERTS (default: true if ssl else false)
    """
    host = os.getenv("OS_HOST", "localhost")
    port = int(os.getenv("OS_PORT", "9200"))
    user = os.getenv("OS_USER")
    password = os.getenv("OS_PASSWORD")

    use_ssl = _env_bool("OS_USE_SSL", False)
    verify_certs = _env_bool("OS_VERIFY_CERTS", use_ssl)  # ssl이면 기본 True

    http_auth = None
    if user and password:
        http_auth = (user, password)

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=http_auth,
        use_ssl=use_ssl,
        verify_certs=verify_certs,
        connection_class=RequestsHttpConnection,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )


def ensure_index(
    client: OpenSearch,
    index: str,
    dim: int,
    shards: int = 1,
    replicas: int = 0,
    recreate: bool = False,
) -> None:
    """
    kNN 벡터 인덱스를 보장한다.
    - settings.index.knn = true
    - mappings: vector=knn_vector(dimension=300), word=keyword

    OpenSearch k-NN 인덱스/knn_vector 타입은 공식 문서 기반. :contentReference[oaicite:0]{index=0}
    """
    if recreate and client.indices.exists(index=index):
        print(f"[index] delete: {index}")
        client.indices.delete(index=index)

    if client.indices.exists(index=index):
        print(f"[index] exists: {index}")
        return

    body = {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": shards,
                "number_of_replicas": replicas,
            }
        },
        "mappings": {
            "properties": {
                "word": {"type": "keyword"},
                "vector": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                        "parameters": {
                            "ef_construction": 128,
                            "m": 16,
                        },
                    },
                },
            }
        },
    }

    print(f"[index] create: {index} (dim={dim})")
    client.indices.create(index=index, body=body)


def parse_vec_file(path: str, dim: int) -> Iterator[Tuple[str, list[float]]]:
    """
    .vec 파일을 스트리밍 파싱한다.
    fastText .vec는 보통 첫 줄이 "vocab_size dim" 헤더일 수 있음.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first = f.readline()
        if not first:
            return

        parts = first.strip().split()
        # 헤더(예: "2000000 300")면 건너뜀
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            header_dim = int(parts[1])
            if header_dim != dim:
                raise ValueError(f"vec header dim({header_dim}) != expected dim({dim})")
        else:
            # 헤더가 아니면 첫 줄도 데이터로 처리
            maybe = _parse_vec_line(first, dim)
            if maybe is not None:
                yield maybe

        for line in f:
            maybe = _parse_vec_line(line, dim)
            if maybe is not None:
                yield maybe


def _parse_vec_line(line: str, dim: int) -> Optional[Tuple[str, list[float]]]:
    s = line.strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) < dim + 1:
        return None

    word = parts[0]
    try:
        vec = [float(x) for x in parts[1 : dim + 1]]
    except ValueError:
        return None

    if len(vec) != dim:
        return None
    return word, vec


def iter_actions(index: str, items: Iterator[Tuple[str, list[float]]]):
    """
    bulk 인덱싱 action 생성기.
    - _id = word 로 저장 (get_vector가 GET /{index}/_doc/{word} 로 바로 되도록)
    """
    for word, vec in items:
        yield {
            "_op_type": "index",
            "_index": index,
            "_id": word,
            "_source": {"word": word, "vector": vec},
        }


def main():
    parser = argparse.ArgumentParser(description="Load .vec into OpenSearch (knn_vector).")
    parser.add_argument("--vec", required=True, help="path to .vec file")
    parser.add_argument("--index", default=os.getenv("OS_INDEX", "ssamentle-words"))
    parser.add_argument("--dim", type=int, default=300)
    parser.add_argument("--chunk-size", type=int, default=int(os.getenv("OS_BULK_CHUNK", "1000")))
    parser.add_argument("--recreate-index", action="store_true", help="delete & recreate index")
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--replicas", type=int, default=0)

    args = parser.parse_args()

    client = build_client()
    ensure_index(
        client=client,
        index=args.index,
        dim=args.dim,
        shards=args.shards,
        replicas=args.replicas,
        recreate=args.recreate_index,
    )

    items = parse_vec_file(args.vec, dim=args.dim)
    actions = iter_actions(args.index, items)

    ok_count = 0
    fail_count = 0

    print(f"[bulk] start: index={args.index}, chunk_size={args.chunk_size}")
    for ok, _ in helpers.streaming_bulk(
        client,
        actions,
        chunk_size=args.chunk_size,
        request_timeout=120,
    ):
        if ok:
            ok_count += 1
            if ok_count % 50000 == 0:
                print(f"[bulk] indexed: {ok_count}")
        else:
            fail_count += 1

    client.indices.refresh(index=args.index)
    print(f"[done] indexed={ok_count}, failed={fail_count}, index={args.index}")


if __name__ == "__main__":
    main()
