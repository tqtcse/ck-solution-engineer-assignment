import json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent

GROUPS = {
    "fact": "prose",
    "list": "prose",
    "person": "prose",
    "risk": "prose",
    "table_number": "table",
    "table_multi": "table",
    "out_of_scope": "out of scope",
}

MARK = {True: "PASS", False: "FAIL", None: "-"}


def load(version: str) -> dict:
    path = OUT / f"results_{version}.json"
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf8"))}


def rate(rows: list[dict], field: str) -> str:
    vals = [r[field] for r in rows if r.get(field) is not None]
    return f"{sum(vals)}/{len(vals)}" if vals else "-"


def summary_table(v1: dict, v2: dict) -> list[str]:
    buckets = defaultdict(lambda: ([], []))
    for qid, row in v1.items():
        group = GROUPS[row["type"]]
        buckets[group][0].append(row)
        buckets[group][1].append(v2[qid])

    out = ["| Group | n | hit@3 v1 | hit@3 v2 | correct v1 | correct v2 | grounded v1 | grounded v2 |",
           "|---|---|---|---|---|---|---|---|"]
    for group in ("prose", "table", "out of scope"):
        if group not in buckets:
            continue
        a, b = buckets[group]
        out.append(
            f"| {group} | {len(a)} | {rate(a, 'hit3')} | {rate(b, 'hit3')} "
            f"| {rate(a, 'correct')} | {rate(b, 'correct')} "
            f"| {rate(a, 'grounded')} | {rate(b, 'grounded')} |"
        )
    return out


def detail_table(v1: dict, v2: dict) -> list[str]:
    out = ["| id | type | top1 v1 | top1 v2 | correct v1 | correct v2 | pages v1 | pages v2 |",
           "|---|---|---|---|---|---|---|---|"]
    for qid in sorted(v1):
        a, b = v1[qid], v2[qid]
        out.append(
            f"| {qid} | {a['type']} | {a['top1_score']:.3f} | {b['top1_score']:.3f} "
            f"| {MARK[a['correct']]} | {MARK[b['correct']]} "
            f"| {a['pages']} | {b['pages']} |"
        )
    return out


def threshold_gap(rows: dict, label: str) -> str:
    inside = sorted(r["top1_score"] for r in rows.values() if r["type"] != "out_of_scope")
    outside = sorted(r["top1_score"] for r in rows.values() if r["type"] == "out_of_scope")
    gap = min(inside) - max(outside)
    verdict = "separable" if gap > 0 else "OVERLAP, no threshold separates them"
    return (f"- **{label}** in scope `{inside[0]:.3f}..{inside[-1]:.3f}`, "
            f"out of scope `{outside[0]:.3f}..{outside[-1]:.3f}`, "
            f"gap `{gap:+.3f}` -> {verdict}")


def main():
    v1, v2 = load("v1"), load("v2")
    lines = ["## Summary by question group", ""]
    lines += summary_table(v1, v2)
    lines += ["", "## Per question", ""]
    lines += detail_table(v1, v2)
    lines += ["", "## Score separation (basis for the retrieval threshold)", ""]
    lines += [threshold_gap(v1, "v1"), threshold_gap(v2, "v2")]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
