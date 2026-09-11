import json
from app import config
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
    blocks, stop = {}, "end_turn"
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
    yield ("__result__", (blocks, stop))


def run_turn(state: SessionState, user_text: str):
    state.messages.append({"role": "user", "content": [{"text": user_text}]})

    for _ in range(MAX_STEPS):
        blocks = stop = None
        for kind, payload in _stream_once(state.messages):
            if kind == "__result__":
                blocks, stop = payload
            else:
                yield (kind, payload)

        content, calls = [], []
        for i in sorted(blocks):
            b = blocks[i]
            if b["kind"] == "text":
                content.append({"text": b["text"]})
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
        state.messages.append({"role": "assistant", "content": content})

        if stop != "tool_use":
            yield ("done", None)
            return

        results = []
        for tool_id, name, args in calls:
            yield ("tool_start", name)
            out = run_tool(name, args, state) 
            yield ("tool_end", name)
            results.append({
                "toolResult": {
                    "toolUseId": tool_id,
                    "content": [{"json": out}],
                    "status": "error" if "error" in out else "success",
                }
            })
        state.messages.append({"role": "user", "content": results})

    yield ("token", "\n(Maximum execution steps reached.)")
    yield ("done", None)