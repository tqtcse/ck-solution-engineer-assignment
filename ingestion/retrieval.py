import json, sys
from functools import lru_cache
import numpy as np
from app import config
from app.bedrock import embed


@lru_cache(maxsize=1)
def _index():
    vecs = np.load(config.index_path())["vectors"]
    chunks = [json.loads(l) for l in open(config.chunks_path(), encoding="utf8")]
    return vecs, chunks


def search(query: str, k: int | None = None) -> list[dict]:
    vecs, chunks = _index()
    q = np.array(embed(query), dtype=np.float32)
    scores = vecs @ q                      
    top = np.argsort(-scores)[: (k or config.TOP_K)]
    return [{**chunks[i], "score": round(float(scores[i]), 4)} for i in top]


if __name__ == "__main__":
    for r in search(" ".join(sys.argv[1:]) or "operating segments"):
        print(f"[{r['score']:.3f}] trang {r['page']}: {r['text'][:150]}...\n")