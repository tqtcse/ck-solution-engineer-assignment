import argparse
import hashlib
import json

import numpy as np

from app import config
from app.bedrock import embed
from ingestion.chunk import chunk_page
from ingestion.extract import pages

PDF = config.DATA / "raw" / "Company-10k-18pages.pdf"
CACHE = config.DATA / ".embed_cache.json"


def _cache_load():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def _records_v1():
    records = []
    for page_no, text in pages(PDF):
        for piece in chunk_page(text):
            records.append({"chunk_id": f"p{page_no}-{len(records)}",
                            "page": page_no, "text": piece})
    return records


def _records_v2():
    from ingestion import preprocess_v2 as pre

    cache, records, tables = pre.cache_load(), [], 0
    for doc in pre.documents(PDF):
        if doc["is_table"]:
            tables += 1
            pieces = [pre.narrate(doc["text"], cache) + "\n\n" + doc["text"]]
        else:
            pieces = chunk_page(doc["text"])
        for piece in pieces:
            records.append({"chunk_id": f"p{doc['page']}-{len(records)}",
                            "page": doc["page"], "item": doc["item"],
                            "section_title": doc["section_title"],
                            "is_table": doc["is_table"],
                            "text": pre.prefix(doc) + piece})
    pre.cache_save(cache)
    print(f"  {tables} table blocks, each as one chunk: narration + exact rows")
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1", choices=["v1", "v2"])
    args = ap.parse_args()

    records = _records_v2() if args.version == "v2" else _records_v1()
    print(f"{len(records)} chunks")

    # Cache
    cache, vectors, new = _cache_load(), [], 0
    for r in records:
        key = hashlib.sha1(r["text"].encode()).hexdigest()
        if key not in cache:
            cache[key] = embed(r["text"])
            new += 1
            if new % 20 == 0:
                print(f"  embedded {new}...")
        vectors.append(cache[key])
    CACHE.write_text(json.dumps(cache))
    print(f"embedded {new} new, {len(records) - new} from cache")

    np.savez_compressed(config.index_path(args.version),
                        vectors=np.array(vectors, dtype=np.float32))
    with open(config.chunks_path(args.version), "w", encoding="utf8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote", config.index_path(args.version).name)


if __name__ == "__main__":
    main()
