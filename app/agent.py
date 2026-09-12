import json
import threading
import time

from app import config, memory, obs, router
from app.bedrock import client
from app.session import SessionState
from app.tools import TOOL_SPECS, run_tool

SYSTEM = (config.ROOT / "app" / "prompts" / "system.md").read_text(encoding="utf8")
MAX_STEPS = 6


def _stream_once(messages):
    resp = client().converse_stream(
        modelId=config.CHAT_MODEL,
        system=[{"text": SYSTEM}],
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

    for _ in range(MAX_STEPS):
        blocks = stop = None
        for kind, payload in _stream_once(messages):
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
            out = run_tool(name, args, state)
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

    _finish(state, said, usage, started, routed)
    yield ("token", "\n(Maximum execution steps reached.)")
    yield ("done", None)
