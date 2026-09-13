import argparse
import json
import time
from pathlib import Path

import yaml

from app import config, retrieval
from app.bedrock import client

GOLDEN = Path(__file__).parent / "golden_set.yaml"
OUT = Path(__file__).parent

SYSTEM = (
    "You answer strictly from the provided excerpts of a company 10-K filing. "
    "If the excerpts do not contain the answer, say plainly that you cannot find it "
    "in the documents and do not guess. Always cite the page you used as (page N)."
)

JUDGE = (
    "A user asked: {q}\n\n"
    "An assistant replied: {a}\n\n"
    "Does the reply state that the information is NOT available in the provided "
    "documents? Reply with exactly one word: YES or NO."
)


def _say(prompt: str, system: str, max_tokens: int = 400) -> str:
    resp = client().converse(
        modelId=config.CHAT_MODEL,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
    )
    return resp["output"]["message"]["content"][0]["text"]


def answer(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[page {h['page']}]\n{h['text']}" for h in hits)
    return _say(f"Excerpts:\n{context}\n\nQuestion: {question}", SYSTEM)


def is_refusal(question: str, reply: str) -> bool:
    verdict = _say(JUDGE.format(q=question, a=reply), "You are a strict grader.", 5)
    return verdict.strip().upper().startswith("YES")


def evidence(case: dict, hits: list[dict]) -> bool:
    context = " ".join(h["text"] for h in hits).lower()
    return all(s.lower() in context for s in case["expected_answer_contains"])


def grade(case: dict, hits: list[dict], reply: str) -> dict:
    row = {
        "id": case["id"],
        "type": case["type"],
        "top1_score": round(hits[0]["score"], 3) if hits else 0.0,
        "pages": sorted({h["page"] for h in hits}),
    }
    if case.get("must_refuse"):
        row["hit3"] = None
        row["evidence"] = None
        row["grounded"] = None
        row["correct"] = is_refusal(case["question"], reply)
    else:
        low = reply.lower()
        row["hit3"] = case["expected_page"] in row["pages"]
        row["evidence"] = evidence(case, hits)
        row["correct"] = all(s.lower() in low for s in case["expected_answer_contains"])
        row["grounded"] = f"page {case['expected_page']}" in low
    return row


def run(version: str, retrieval_only: bool) -> list[dict]:
    cases = yaml.safe_load(GOLDEN.read_text(encoding="utf8"))
    rows = []
    for case in cases:
        hits = retrieval.search(case["question"], k=3, version=version)
        reply = "" if retrieval_only else answer(case["question"], hits)
        row = grade(case, hits, reply) if not retrieval_only else {
            "id": case["id"], "type": case["type"],
            "top1_score": round(hits[0]["score"], 3) if hits else 0.0,
            "pages": sorted({h["page"] for h in hits}),
            "hit3": None if case.get("must_refuse") else case["expected_page"] in {h["page"] for h in hits},
            "evidence": None if case.get("must_refuse") else evidence(case, hits),
            "correct": None, "grounded": None,
        }
        row["reply"] = reply
        rows.append(row)
        mark = {True: "OK", False: "..", None: "--"}[row["hit3"]]
        ev = {True: "E", False: "-", None: " "}[row["evidence"]]
        print(f"  [{mark}{ev}] {row['id']} {row['type']:<14} top1={row['top1_score']:.3f}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--retrieval-only", action="store_true",
                    help="chỉ đo retrieval, không gọi model — nhanh và miễn phí")
    args = ap.parse_args()

    print(f"eval {args.version} ({'retrieval only' if args.retrieval_only else 'full'})")
    started = time.time()
    rows = run(args.version, args.retrieval_only)

    path = OUT / f"results_{args.version}.json"
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf8")
    print(f"\n{len(rows)} câu trong {time.time() - started:.1f}s -> {path.name}")


if __name__ == "__main__":
    main()