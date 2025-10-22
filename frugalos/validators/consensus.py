from __future__ import annotations
import json
from collections import Counter
from typing import List, Tuple

def _normalize(s: str) -> str:
    s = s.strip()
    try:
        obj = json.loads(s)
        return json.dumps(obj, sort_keys=True, separators=(",",":"))
    except Exception:
        return " ".join(s.split())

def majority_vote(cands: List[str], threshold: float = 0.67) -> Tuple[str, float]:
    normed = [_normalize(c) for c in cands]
    counts = Counter(normed)
    best, cnt = counts.most_common(1)[0]
    agree = cnt / max(1, len(cands))
    # return original candidate matching best
    for c in cands:
        if _normalize(c) == best:
            return c, agree
    return cands[0], agree
