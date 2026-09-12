import json
import sys
from functools import lru_cache

import numpy as np

from app import config
from app.bedrock import embed


@lru_cache(maxsize=2)
def _index(version: str | None = None):
    vecs = np.load(config.index_path(version))["vectors"]
    with open(config.chunks_path(version), encoding="utf8") as f:
        chunks = [json.loads(line) for line in f]
    return vecs, chunks


def search(query: str, k: int | None = None, version: str | None = None) -> list[dict]:
    vecs, chunks = _index(version)
    q = np.array(embed(query), dtype=np.float32)
    scores = vecs @ q
    top = np.argsort(-scores)[: (k or config.TOP_K)]
    return [{**chunks[i], "score": round(float(scores[i]), 4)} for i in top]


if __name__ == "__main__":
    for r in search(" ".join(sys.argv[1:]) or "operating segments"):
        print(f"[{r['score']:.3f}] page {r['page']}: {r['text'][:400]}...\n")
