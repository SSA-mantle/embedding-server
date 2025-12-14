from __future__ import annotations

import math
from typing import Optional, Sequence

Vector = Sequence[float]


def cosine_similarity(a: Vector, b: Vector) -> Optional[float]:
    """
    코사인 유사도 계산.
    - 길이가 다르거나, 영벡터면 None 반환
    - 반환 범위는 일반적인 cosine: [-1, 1]
    """
    if len(a) != len(b) or len(a) == 0:
        return None

    dot = 0.0
    na = 0.0
    nb = 0.0

    for x, y in zip(a, b):
        dot += float(x) * float(y)
        na += float(x) * float(x)
        nb += float(y) * float(y)

    if na == 0.0 or nb == 0.0:
        return None

    return dot / (math.sqrt(na) * math.sqrt(nb))
