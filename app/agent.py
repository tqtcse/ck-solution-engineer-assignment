import json
import threading
import time

from app import config, memory, obs, router, verification
from app.bedrock import client
from app.session import SessionState
from app.tools import TOOL_SPECS, run_tool

SYSTEM = (config.ROOT / "app" / "prompts" / "system.md").read_text(encoding="utf8")
MAX_STEPS = 6
MAX_SEARCHES = 2
SEARCH_BUDGET_NOTE = (
    "Search budget exhausted for this turn. Do not call search_knowledge_base again. "
    "Answer from what has already been retrieved; if nothing relevant was found, tell the "
    "customer the documents do not mention it."
)
STEP_LIMIT_REPLY = "I could not complete that request. Could you rephrase it, or ask something more specific?"


def _ground_truth(state: SessionState, rejected: list[str]) -> str:
    if state.verified:
        return "\n\nServer state: the customer is verified. Identity is settled; do not collect it again."
    held = sorted(state.collected) or ["none"]
    lines = [
        "",
        "",
        "Server state, authoritative and recomputed every turn:",
        "- fields the server holds: " + ", ".join(held),
        "- fields still required: " + ", ".join(state.missing()),
        "Never say or imply you hold a field that is absent from the first list. "
        "Any email address in the customer's latest message has already been submitted for you, "
        "so do not call submit_verification for an email again this turn; call it for the SSN "
        "digits and the date of birth.",
    ]
    if rejected:
        lines.append("- the server rejected this from the latest message: " + " ".join(rejected)
                     + " Relay that wording to the customer.")
    return "\n".join(lines)


def _precollect_email(state: SessionState, user_text: str) -> list[str] | None:
    if state.verified or "email" in state.collected:
        return None
    found = verification.ANY_EMAIL.search(user_text or "")
    if not found:
        return None
    started = time.perf_counter()
    out = run_tool("submit_verification", {"email": found.group(0)}, state)
    obs.log("tool", name="submit_verification", args={"email": found.group(0)},
            status="error" if "error" in out else "ok",
            ms=int((time.perf_counter() - started) * 1000))
    return list(out.get("problems") or [])


def _stream_once(messages, system_text):
    resp = client().converse_stream(
        modelId=config.CHAT_MODEL,
        system=[{"text": system_text}],
        messages=messages,
        toolConfig={"tools": TOOL_SPECS},
        inferenceConfig={"maxTokens": 1024, "temperature": 0},
    )
    blocks, stop, usage = {}, "end_turn", {}
    for ev in resp["stream"]:
        if "contentBlockStart" in ev:
            i = ev["contentBlockStart"]["contentBlockIndex"]
            start = ev["contentBlockStart"]["start"]
            if "toolUse" in start:
                blocks[i] = {
                    "kind": "tool",
                    "id": start["toolUse"]["toolUseId"],
                    "name": start["toolUse"]["name"],
                    "raw": "",
                }
        elif "contentBlockDelta" in ev:
            i = ev["contentBlockDelta"]["contentBlockIndex"]
            d = ev["contentBlockDelta"]["delta"]
            if "text" in d:
                b = blocks.setdefault(i, {"kind": "text", "text": ""})
                b["text"] += d["text"]
                yield ("token", d["text"])
            elif "toolUse" in d:
                blocks[i]["raw"] += d["toolUse"]["input"]
        elif "messageStop" in ev:
            stop = ev["messageStop"]["stopReason"]
        elif "metadata" in ev:
            usage = ev["metadata"].get("usage", {})
    yield ("__result__", (blocks, stop, usage))


def _history(session_id: str) -> list[dict]:
    out = []
    for m in memory.load_recent(session_id):
        if out and out[-1]["role"] == m["role"]:
            out[-1]["content"][0]["text"] += "\n" + m["content"]
        else:
            out.append({"role": m["role"], "content": [{"text": m["content"]}]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _route_async(user_text: str, mid_verification: bool) -> dict:
    box = {"label": "UNKNOWN", "by": "timeout"}

    def work():
        box["label"], box["by"] = router.route(user_text, mid_verification)

    box["thread"] = threading.Thread(target=work, daemon=True)
    box["thread"].start()
    return box


def _finish(state: SessionState, said: list[str], usage: dict, started: float,
            routed: dict):
    memory.append_message(
        state.session_id, "assistant", "".join(said),
        model=config.CHAT_MODEL,
        tokens_in=usage.get("inputTokens"),
        tokens_out=usage.get("outputTokens"),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    state.save()
    routed["thread"].join(timeout=2.0)
    obs.log("routed", label=routed["label"], by=routed["by"])
    obs.metric("LatencyMs", int((time.perf_counter() - started) * 1000), "Milliseconds")
    if usage:
        obs.metric("TokensIn", usage.get("inputTokens", 0))
        obs.metric("TokensOut", usage.get("outputTokens", 0))


def run_turn(state: SessionState, user_text: str):
    routed = _route_async(user_text, bool(state.collected) and not state.verified)
    messages = _history(state.session_id)
    messages.append({"role": "user", "content": [{"text": user_text}]})
    memory.append_message(state.session_id, "user", user_text)

    started, said, usage = time.perf_counter(), [], {}
    ttft = None
    searches = 0

    rejected = _precollect_email(state, user_text)
    if rejected is not None:
        yield ("tool_start", "submit_verification")
        yield ("tool_end", "submit_verification")
    system_text = SYSTEM + _ground_truth(state, rejected or [])

    for _ in range(MAX_STEPS):
        blocks = stop = None
        for kind, payload in _stream_once(messages, system_text):
            if kind == "__result__":
                blocks, stop, step_usage = payload
                for key in ("inputTokens", "outputTokens"):
                    usage[key] = usage.get(key, 0) + step_usage.get(key, 0)
                continue
            if kind == "token" and ttft is None:
                ttft = int((time.perf_counter() - started) * 1000)
                obs.metric("TtftMs", ttft, "Milliseconds")
            yield (kind, payload)

        content, calls = [], []
        for i in sorted(blocks):
            b = blocks[i]
            if b["kind"] == "text":
                content.append({"text": b["text"]})
                said.append(b["text"])
            else:
                args = json.loads(b["raw"] or "{}")
                content.append({
                    "toolUse": {
                        "toolUseId": b["id"],
                        "name": b["name"],
                        "input": args,
                    }
                })
                calls.append((b["id"], b["name"], args))
        messages.append({"role": "assistant", "content": content})

        if stop != "tool_use":
            _finish(state, said, usage, started, routed)
            yield ("done", None)
            return

        results = []
        for tool_id, name, args in calls:
            yield ("tool_start", name)
            tool_started = time.perf_counter()
            if name == "search_knowledge_base" and searches >= MAX_SEARCHES:
                out = {"results": [], "note": SEARCH_BUDGET_NOTE}
                obs.metric("SearchBudgetHit", 1)
            else:
                out = run_tool(name, args, state)
            if name == "search_knowledge_base":
                searches += 1
            obs.log("tool", name=name, args=args,
                    status="error" if "error" in out else "ok",
                    ms=int((time.perf_counter() - tool_started) * 1000))
            yield ("tool_end", name)
            results.append({
                "toolResult": {
                    "toolUseId": tool_id,
                    "content": [{"json": out}],
                    "status": "error" if "error" in out else "success",
                }
            })
        state.save()
        messages.append({"role": "user", "content": results})

    said.append(STEP_LIMIT_REPLY)
    obs.log("step_limit", steps=MAX_STEPS)
    obs.metric("StepLimitHit", 1)
    _finish(state, said, usage, started, routed)
    yield ("token", STEP_LIMIT_REPLY)
    yield ("done", None)
