import pytest

from app.router import route


@pytest.mark.parametrize("text", [
    "Where is my order?",
    "CK-2026-0007",
    "when will my package be delivered",
    "I want a refund",
    "my email is alice@ck1.com",
    "Last 4 digits of SSN: 6789",
    "my date of birth is January 5th, 1990",
])
def test_order_workflow_by_rule(text):
    assert route(text) == ("ORDER_WORKFLOW", "rule")


@pytest.mark.parametrize("text", ["hi", "thanks", "hello there"])
def test_short_message_by_rule(text):
    assert route(text) == ("OTHER", "rule")


def test_mid_verification_wins_over_every_rule():
    assert route("1990-01-05", mid_verification=True) == ("ORDER_WORKFLOW", "state")
    assert route("hi", mid_verification=True) == ("ORDER_WORKFLOW", "state")


def test_bare_date_of_birth_needs_state():
    assert route("1990-01-05") == ("OTHER", "rule")


def test_model_is_never_called_on_the_rule_path(monkeypatch):
    def boom():
        raise AssertionError("router called Bedrock on the rule path")

    monkeypatch.setattr("app.router.client", boom)
    assert route("Where is my order?")[1] == "rule"
    assert route("hi")[1] == "rule"
    assert route("anything at all", mid_verification=True)[1] == "state"


@pytest.mark.aws
@pytest.mark.parametrize("text,expected", [
    ("What are the company's three reportable segments?", "KNOWLEDGE"),
    ("What is the weather in Hanoi today?", "OTHER"),
    ("I want to check the status of something I bought last week", "ORDER_WORKFLOW"),
])
def test_model_path(text, expected):
    label, how = route(text)
    assert how == "model"
    assert label == expected
