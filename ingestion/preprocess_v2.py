import hashlib
import json
import re

import pymupdf

from app import config
from app.bedrock import client

ITEM = re.compile(r"^\s*(Item\s+\d+[A-B]?)\.\s*(.*)$", re.I)
NOISE = re.compile(r"^(Table of Contents|_{3,})$")
YEAR = re.compile(r"^(\d{4})(?:\s*\(\d+\))?$")
VALUE = re.compile(r"^\(?\$?\s*[\d,]+(?:\.\d+)?\)?%?$")
MONEY = re.compile(r"^\$$")
DASH = re.compile(r"^[—–-]$")

NARRATE = (
    "Below is a table from a 10-K filing, one row per line, each figure already paired with its year. "
    "Write 1-3 plain English sentences stating the key figures. Every figure must keep the year it "
    "belongs to. No preamble, no bullet points."
)

_CACHE = config.DATA / ".narrate_cache.json"


def _is_toc(lines: list[str]) -> bool:
    return sum(1 for ln in lines if ITEM.match(ln)) >= 5


def _split_table_rows(lines: list[str]) -> tuple[list[str], list[str]]:
    rows, prose, years, label, values = [], [], [], None, []
    header = ""

    def flush():
        nonlocal label, values, header
        if label and values and years:
            pairs = [f"{y} {v}" for y, v in zip(years, values)]
            name = f"{header} - {label}" if header else label
            rows.append(f"{name}: " + "; ".join(pairs))
        elif label:
            if label.endswith(":"):
                header = label.rstrip(":")
            prose.append(label)
        label, values = None, []

    i = 0
    while i < len(lines):
        run, j = [], i
        while j < len(lines) and YEAR.match(lines[j]):
            run.append(YEAR.match(lines[j]).group(1))
            j += 1
        if len(run) >= 3:
            flush()
            years, i = run, j
            continue

        line = lines[i]
        if MONEY.match(line):
            i += 1
            continue
        if years and (VALUE.match(line) or DASH.match(line)):
            values.append(line)
            i += 1
            continue

        flush()
        label = line
        i += 1

    flush()
    return rows, prose


def documents(pdf_path):
    doc = pymupdf.open(pdf_path)
    item, title = "", ""

    for page_no, page in enumerate(doc, start=1):
        lines = [ln.strip() for ln in page.get_text().splitlines()]
        lines = [ln for ln in lines if ln and not NOISE.match(ln)]
        if lines and lines[-1] == str(page_no):
            lines.pop()
        if _is_toc(lines):
            print(f"  skipped page {page_no}: table of contents")
            continue

        rows, prose = _split_table_rows(lines)

        buffer = []
        for line in prose:
            match = ITEM.match(line)
            if match:
                if buffer:
                    yield {"page": page_no, "item": item, "section_title": title,
                           "is_table": False, "text": "\n".join(buffer)}
                    buffer = []
                item, title = match.group(1), match.group(2).strip()
            buffer.append(line)
        if buffer:
            yield {"page": page_no, "item": item, "section_title": title,
                   "is_table": False, "text": "\n".join(buffer)}

        if rows:
            yield {"page": page_no, "item": item, "section_title": title,
                   "is_table": True, "text": "\n".join(rows)}


def cache_load() -> dict:
    return json.loads(_CACHE.read_text()) if _CACHE.exists() else {}


def cache_save(cache: dict) -> None:
    _CACHE.write_text(json.dumps(cache))


def narrate(text: str, cache: dict) -> str:
    key = hashlib.sha1(text.encode()).hexdigest()
    if key not in cache:
        resp = client().converse(
            modelId=config.CHAT_MODEL,
            system=[{"text": NARRATE}],
            messages=[{"role": "user", "content": [{"text": text}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0},
        )
        cache[key] = resp["output"]["message"]["content"][0]["text"].strip()
    return cache[key]


def prefix(record: dict) -> str:
    bits = [f"page {record['page']}"]
    if record["item"]:
        bits.append(record["item"])
    if record["section_title"]:
        bits.append(record["section_title"])
    if record["is_table"]:
        bits.append("financial table")
    return "[" + " | ".join(bits) + "]\n"
