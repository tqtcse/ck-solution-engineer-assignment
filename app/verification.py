import re
from dataclasses import dataclass
from datetime import date, datetime

from dateutil import parser as dtp

ANY_EMAIL = re.compile(r"[^@\s]+@[^\s]+\.[a-z]{2,}", re.I)
CK_EMAIL = re.compile(r"^[^@\s]+@ck\d+\.[a-z]{2,}$", re.I)

_DEF_A = datetime(1900, 1, 1)
_DEF_B = datetime(2001, 6, 15)


@dataclass(frozen=True)
class Ambiguous:
    first: date
    second: date


def parse_email(text: str):
    match = ANY_EMAIL.search(text or "")
    if not match:
        return None, "No email address found in that message."
    email = match.group(0).lower().rstrip(".,;:")
    if not CK_EMAIL.match(email):
        return None, (f"'{email}' is not a company address. "
                      "It must look like @ck<number>, for example user@ck1.com")
    return email, None


def parse_ssn_last4(text: str):
    digits = re.sub(r"\D", "", text or "")
    if len(digits) < 4:
        return None, "I need at least the last four digits of the SSN."
    return digits[-4:], None


def _parse_with(text: str, dayfirst: bool):
    try:
        a = dtp.parse(text, default=_DEF_A, dayfirst=dayfirst, fuzzy=True)
        b = dtp.parse(text, default=_DEF_B, dayfirst=dayfirst, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    if (a.year, a.month, a.day) != (b.year, b.month, b.day):
        return None
    return a.date()


def parse_dob(text: str, today: date | None = None):
    text = (text or "").strip()
    if not text:
        return None, "No date of birth found in that message."

    candidates = {d for d in (_parse_with(text, False), _parse_with(text, True)) if d}
    if not candidates:
        return None, ("I could not read that date. Please include day, month and "
                      "year - for example 'Jan 5 1990' or '1990-01-05'.")

    today = today or date.today()
    candidates = {d for d in candidates if d < today}
    if not candidates:
        return None, "A date of birth cannot be in the future."

    if len(candidates) == 2:
        first, second = sorted(candidates)
        return Ambiguous(first, second), None   
    return candidates.pop(), None