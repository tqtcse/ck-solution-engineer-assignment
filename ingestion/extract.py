import re
import pymupdf

NOISE = re.compile(r"^\s*(Table of Contents|\d{1,3}|_{3,})\s*$")


def pages(pdf_path):
    doc = pymupdf.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        lines = [ln for ln in page.get_text().splitlines() if not NOISE.match(ln)]
        yield i, "\n".join(lines).strip()