from app.obs import redact


def test_masks_email():
    assert "alice@ck1.com" not in redact("my email is alice@ck1.com")


def test_masks_full_ssn():
    assert "123-45-6789" not in redact("ssn 123-45-6789")


def test_masks_by_field_name():
    out = redact({"ssn_last4": "1234", "dob": "1990-01-05", "order_id": "CK-2026-0007"})
    assert out["ssn_last4"] == "***"
    assert out["dob"] == "***"
    assert out["order_id"] == "CK-2026-0007"


def test_field_name_catches_what_regex_cannot():
    assert redact({"dob": "January 5th"})["dob"] == "***"


def test_keeps_financial_figures():
    assert "280,522" in redact("net sales were $280,522 million")


def test_keeps_order_ids():
    assert "CK-2026-0007" in redact("status of CK-2026-0007")


def test_recurses_into_nested_structures():
    out = redact({"tool": "submit_verification", "args": {"email": "a@ck1.com"}})
    assert out["args"]["email"] == "***"
    out = redact({"results": [{"page": 18, "text": "reach bob@ck2.com"}]})
    assert "bob@ck2.com" not in out["results"][0]["text"]


def test_leaves_non_strings_alone():
    out = redact({"page": 18, "score": 0.54, "hit": True, "note": None})
    assert out == {"page": 18, "score": 0.54, "hit": True, "note": None}


def test_conversation_store_keeps_what_the_agent_needs_next_turn():
    import inspect

    from app import memory

    source = inspect.getsource(memory.append_message)
    assert "redact" not in source, (
        "Redacting message content destroys the context the agent reads back on the "
        "next turn: the customer's email becomes ***@***, a bare SSN becomes ****, "
        "and a clarifying question about a date becomes unanswerable. Redaction "
        "belongs to obs.log and obs.metric, not to the conversation store."
    )


def test_masks_bare_four_digits_even_when_it_is_a_year():
    assert redact("net sales in 2019") == "net sales in ****"
