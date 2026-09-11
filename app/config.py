import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

AWS_REGION  = os.getenv("AWS_REGION", "us-east-1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "amazon.titan-embed-text-v2:0")
CHAT_MODEL  = os.getenv("CHAT_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
INDEX_VER   = os.getenv("INDEX_VERSION", "v1")
TOP_K       = int(os.getenv("TOP_K", "3"))
EMBED_DIM   = 1024
CONV_TABLE    = os.getenv("CONV_TABLE", "ck-agent-dev-conversations")
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "12"))

def index_path(ver=None):  return DATA / f"index_{ver or INDEX_VER}.npz"
def chunks_path(ver=None): return DATA / f"chunks_{ver or INDEX_VER}.jsonl"
