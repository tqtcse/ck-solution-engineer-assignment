import json

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse

from app import config, retrieval
from app.agent import run_turn
from app.session import get

app = FastAPI(title="CK Agent")
INDEX = config.ROOT / "app" / "static" / "index.html"
retrieval._index() 

@app.get("/")
def home():
    return FileResponse(INDEX)


@app.get("/health")
def health():
    return {"ok": True, "model": config.CHAT_MODEL, "index": config.INDEX_VER}


@app.post("/chat/stream")
async def chat_stream(req: Request):
    body = await req.json()
    state = get(body.get("session_id", "anon"))
    text = (body.get("message") or "").strip()

    def gen():
        try:
            for kind, payload in run_turn(state, text):
                yield f"data: {json.dumps({'type': kind, 'data': payload}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)[:200]})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})