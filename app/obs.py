import json
import re
import time
from contextvars import ContextVar

NAMESPACE = "CkAgent"

trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
session_id: ContextVar[str] = ContextVar("session_id", default="-")

SENSITIVE = {"ssn", "ssn_last4", "dob", "date_of_birth", "email", "full_name", "collected"}

_SSN = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
_EMAIL = re.compile(r"[^@\s]+@[^\s]+\.[a-z]{2,}", re.I)
_DATE = re.compile(r"\b(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|"
                   r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
                   r"\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b", re.I)
_DIGITS4 = re.compile(r"(?<![\w-])\d{4}(?![\w-])")


def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    out = _SSN.sub("***-**-****", value)
    out = _EMAIL.sub("***@***", out)
    out = _DATE.sub("****-**-**", out)
    return _DIGITS4.sub("****", out)


def log(event: str, **fields):
    record = {"ts": int(time.time() * 1000), "event": event,
              "trace_id": trace_id.get(), "session_id": session_id.get()}
    record.update(redact(fields))
    print(json.dumps(record, ensure_ascii=False, default=str), flush=True)


def metric(name: str, value, unit: str = "Count", **dims):
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": NAMESPACE,
                "Dimensions": [list(dims)] if dims else [[]],
                "Metrics": [{"Name": name, "Unit": unit}],
            }],
        },
        name: value,
        **dims,
    }), flush=True)
