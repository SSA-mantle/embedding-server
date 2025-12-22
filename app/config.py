from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass(frozen=True)
class OpenSearchSettings:
    host: str
    port: int
    index: str

    use_ssl: bool
    verify_certs: bool

    # 둘 다 허용: OS_USERNAME / OS_USER
    username: Optional[str]
    password: Optional[str]

    num_candidates: Optional[int]
    timeout: int
    max_retries: int
    retry_on_timeout: bool


@dataclass(frozen=True)
class RedisSettings:
    host: str
    port: int
    db: int
    password: Optional[str]
    key_prefix: str


@dataclass(frozen=True)
class AppSettings:
    timezone: str
    answers_path: str
    opensearch: OpenSearchSettings
    redis: RedisSettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    # ---- app ---- 
    timezone = os.getenv("APP_TZ", "Asia/Seoul")
    answers_path = os.getenv("ANSWERS_PATH", "data/answers.txt")

    # ---- opensearch ----
    os_host = os.getenv("OS_HOST", "localhost")
    os_port = int(os.getenv("OS_PORT", "9200"))
    os_index = os.getenv("OS_INDEX", "ssamantle-words")

    os_use_ssl = _env_bool("OS_USE_SSL", False)
    os_verify = _env_bool("OS_VERIFY_CERTS", os_use_ssl)

    os_username = os.getenv("OS_USERNAME") or os.getenv("OS_USER")
    os_password = os.getenv("OS_PASSWORD")

    os_num_candidates = os.getenv("OS_NUM_CANDIDATES")
    num_candidates = int(os_num_candidates) if os_num_candidates else None

    os_timeout = int(os.getenv("OS_TIMEOUT", "60"))
    os_max_retries = int(os.getenv("OS_MAX_RETRIES", "3"))
    os_retry_on_timeout = _env_bool("OS_RETRY_ON_TIMEOUT", True)

    opensearch = OpenSearchSettings(
        host=os_host,
        port=os_port,
        index=os_index,
        use_ssl=os_use_ssl,
        verify_certs=os_verify,
        username=os_username,
        password=os_password,
        num_candidates=num_candidates,
        timeout=os_timeout,
        max_retries=os_max_retries,
        retry_on_timeout=os_retry_on_timeout,
    )

    # ---- redis ----
    redis = RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        key_prefix=os.getenv("REDIS_KEY_PREFIX", "ssamantle"),
    )

    return AppSettings(
        timezone=timezone,
        answers_path=answers_path,
        opensearch=opensearch,
        redis=redis,
    )


# 편하게 쓰려고 모듈 전역으로 하나 만들어둠
settings = get_settings()