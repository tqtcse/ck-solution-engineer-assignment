import re

from app import config
from app.bedrock import client

ORDER = re.compile(
    r"\b(order|orders|shipment|shipping|tracking|package|parcel|courier|carrier|"
    r"deliver\w*|refund|return|returns|ck-\d{4}-\d{4})\b",
    re.I,
)
IDENTITY = re.compile(
    r"[^@\s]+@[^\s]+\.[a-z]{2,}|\bssn\b|social security|date of birth|born on|"
    r"\b\d{3}[- ]\d{2}[- ]\d{4}\b",
    re.I,
)

LABELS = ("KNOWLEDGE", "ORDER_WORKFLOW", "OTHER")

CLASSIFY = (
    "You are a classifier. Read the user message and reply with exactly one word, "
    "nothing else, chosen from KNOWLEDGE, ORDER_WORKFLOW, OTHER.\n"
    "KNOWLEDGE - about company policy, business, segments, risks, or figures in the annual report\n"
    "ORDER_WORKFLOW - about their own orders, shipping, returns, or identity verification\n"
    "OTHER - anything else, including greetings and small talk"
)


def route(text: str, mid_verification: bool = False) -> tuple[str, str]:
    if mid_verification:
        return "ORDER_WORKFLOW", "state"
    if ORDER.search(text) or IDENTITY.search(text):
        return "ORDER_WORKFLOW", "rule"
    if len(text.split()) <= 3:
        return "OTHER", "rule"

    try:
        resp = client().converse(
            modelId=config.ROUTER_MODEL,
            system=[{"text": CLASSIFY}],
            messages=[{"role": "user", "content": [{"text": text}]}],
            inferenceConfig={"maxTokens": 8, "temperature": 0},
        )
    except Exception:
        return "KNOWLEDGE", "error"

    reply = resp["output"]["message"]["content"][0]["text"].upper()
    for label in LABELS:
        if label in reply:
            return label, "model"
    return "KNOWLEDGE", "model_unparsed"
