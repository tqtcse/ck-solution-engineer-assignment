import argparse
import contextlib
import io
import json
import time
import uuid
from pathlib import Path

import yaml

from app import agent, session

CASES = Path(__file__).parent / "agent_set.yaml"
OUT = Path(__file__).parent


def drive(state, text: str) -> tuple[str, list[str], str]:
    buf, reply, tools = io.StringIO(), [], []
    with contextlib.redirect_stdout(buf):
        for kind, payload in agent.run_turn(state, text):
            if kind == "token":
                reply.append(payload)
            elif kind == "tool_start":
                tools.append(payload)
    return "".join(reply), tools, buf.getvalue()


def check(turn: dict, reply: str, tools: list[str], events: list[str]) -> list[str]:
    low, fails = reply.lower(), []

    missing = [t for t in turn.get("tools", []) if t not in tools]
    if missing:
        fails.append(f"never called {missing}, only {sorted(tools) or 'nothing'}")

    forbidden = [t for t in turn.get("tools_forbidden", []) if t in tools]
    if forbidden:
        fails.append(f"must not have called {forbidden}")

    for s in turn.get("contains", []):
        if s.lower() not in low:
            fails.append(f"missing {s!r}")

    for s in turn.get("excludes", []):
        if s.lower() in low:
            fails.append(f"LEAKED {s!r}")

    for e in turn.get("events", []):
        if e not in events:
            fails.append(f"observability never logged {e!r}, only {events or 'nothing'}")

    for e in turn.get("events_forbidden", []):
        if e in events:
            fails.append(f"observability logged {e!r} and must not have")

    any_of = turn.get("contains_any")
    if any_of and not any(s.lower() in low for s in any_of):
        fails.append(f"none of {any_of}")

    return fails


def run_case(case: dict) -> dict:
    sid = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    print(f"\n{case['id']}  {case['name']}")
    print(f"      covers: {case['covers']}")

    turns, passed = [], True
    for i, turn in enumerate(case["turns"], start=1):
        state = session.get(sid)
        started = time.perf_counter()
        reply, tools, logs = drive(state, turn["say"])
        records = [json.loads(ln) for ln in logs.splitlines() if ln.startswith("{")]
        events = [r["event"] for r in records if "event" in r]
        fails = check(turn, reply, tools, events)
        passed = passed and not fails

        turns.append({
            "n": i,
            "say": turn["say"],
            "reply": reply,
            "tools": tools,
            "fails": fails,
            "ms": int((time.perf_counter() - started) * 1000),
            "events": events,
            "logs": records,
        })

        mark = "OK" if not fails else "!!"
        print(f"  [{mark}] turn {i}  {turn['say'][:52]!r}")
        print(f"        tools={tools or '-'}  {turns[-1]['ms']}ms")
        for f in fails:
            print(f"        FAIL: {f}")

    return {"id": case["id"], "name": case["name"], "covers": case["covers"],
            "session_id": sid, "passed": passed, "turns": turns}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="run one scenario by id")
    args = ap.parse_args()

    cases = yaml.safe_load(CASES.read_text(encoding="utf8"))
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]

    started = time.time()
    rows = [run_case(c) for c in cases]

    path = OUT / "results_agent.json"
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf8")

    ok = sum(1 for r in rows if r["passed"])
    turns = sum(len(r["turns"]) for r in rows)
    bad = sum(1 for r in rows for t in r["turns"] if t["fails"])
    print(f"\n{ok}/{len(rows)} scenarios, {turns - bad}/{turns} turns, "
          f"{time.time() - started:.1f}s -> {path.name}")
    for r in rows:
        if not r["passed"]:
            print(f"  FAILED {r['id']} {r['name']}")


if __name__ == "__main__":
    main()
