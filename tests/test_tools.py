import json

import pytest

from app import config
from app.session import SessionState
from app.tools import run_tool

ORDERS = json.loads((config.DATA / "orders.json").read_text(encoding="utf8"))
ALICE_ORDERS = ["CK-2026-0001", "CK-2026-0007", "CK-2026-0012"]
BOBS_ORDER = "CK-2026-0021"


def fresh():
    return SessionState(session_id="t")


def verified_as(customer_id):
    return SessionState(session_id="t", verified=True, customer_id=customer_id)


def submit(state, **fields):
    return run_tool("submit_verification", fields, state)


class TestNothingLeaksBeforeVerification:
    def test_list_orders_is_refused(self):
        assert run_tool("list_orders", {}, fresh())["error"] == "NOT_VERIFIED"

    def test_order_status_is_refused(self):
        out = run_tool("get_order_status", {"order_id": ALICE_ORDERS[0]}, fresh())
        assert out["error"] == "NOT_VERIFIED"

    def test_refusal_carries_no_order_data(self):
        out = run_tool("get_order_status", {"order_id": ALICE_ORDERS[0]}, fresh())
        blob = json.dumps(out)
        for leaked in ("DELIVERED", "UPS", "1Z999AA10123456784", "Wireless Mouse"):
            assert leaked not in blob

    def test_refusal_does_not_reveal_whether_the_order_exists(self):
        real = run_tool("get_order_status", {"order_id": ALICE_ORDERS[0]}, fresh())
        fake = run_tool("get_order_status", {"order_id": "CK-9999-9999"}, fresh())
        assert real == fake


class TestOneCustomerCannotReadAnother:
    def test_other_customers_order_is_refused(self):
        out = run_tool("get_order_status", {"order_id": BOBS_ORDER}, verified_as("C001"))
        assert out["error"] == "NOT_YOUR_ORDER"

    def test_refusal_carries_no_order_data(self):
        out = run_tool("get_order_status", {"order_id": BOBS_ORDER}, verified_as("C001"))
        blob = json.dumps(out)
        for leaked in ("OUT_FOR_DELIVERY", "C002"):
            assert leaked not in blob

    def test_unknown_order_is_not_found(self):
        out = run_tool("get_order_status", {"order_id": "CK-9999-9999"}, verified_as("C001"))
        assert out["error"] == "NOT_FOUND"

    def test_listing_is_scoped_to_the_verified_customer(self):
        assert run_tool("list_orders", {}, verified_as("C002"))["order_ids"] == [BOBS_ORDER]


class TestOrderLookupForTheRightCustomer:
    def test_all_three_orders_are_listed(self):
        out = run_tool("list_orders", {}, verified_as("C001"))
        assert out["order_ids"] == ALICE_ORDERS
        assert out["count"] == 3

    def test_listing_records_what_was_offered(self):
        state = verified_as("C001")
        run_tool("list_orders", {}, state)
        assert state.orders_offered == ALICE_ORDERS

    def test_status_returns_the_shipment_details(self):
        out = run_tool("get_order_status", {"order_id": "CK-2026-0007"}, verified_as("C001"))
        assert out["status"] == "SHIPPED"
        assert out["carrier"] == "FedEx"
        assert out["eta"] == "2026-09-13"

    def test_status_never_returns_the_internal_customer_id(self):
        for order in ALICE_ORDERS:
            out = run_tool("get_order_status", {"order_id": order}, verified_as("C001"))
            assert "customer_id" not in out

    @pytest.mark.parametrize("raw", ["ck-2026-0007", "  CK-2026-0007  ", "Ck-2026-0007"])
    def test_order_id_is_accepted_in_any_casing_or_padding(self, raw):
        out = run_tool("get_order_status", {"order_id": raw}, verified_as("C001"))
        assert out["status"] == "SHIPPED"


class TestVerificationAccumulatesOneFieldAtATime:
    def test_first_field_reports_what_is_still_needed(self):
        state = fresh()
        out = submit(state, email="alice@ck1.com")
        assert out["verified"] is False
        assert set(out["still_needed"]) == {"ssn_last4", "dob"}

    def test_three_separate_calls_complete_verification(self):
        state = fresh()
        assert submit(state, email="alice@ck1.com")["verified"] is False
        assert submit(state, ssn_last4="6789")["verified"] is False
        out = submit(state, dob="January 5th, 1990")
        assert out["verified"] is True
        assert out["greeting_name"] == "Alice"
        assert state.customer_id == "C001"

    def test_all_three_at_once_also_works(self):
        state = fresh()
        out = submit(state, email="alice@ck1.com", ssn_last4="123-45-6789", dob="Jan 5 1990")
        assert out["verified"] is True

    def test_collected_fields_are_cleared_after_success(self):
        state = fresh()
        submit(state, email="alice@ck1.com", ssn_last4="6789", dob="1990-01-05")
        assert state.collected == {}


class TestVerificationFailure:
    def test_wrong_ssn_does_not_verify(self):
        state = fresh()
        out = submit(state, email="alice@ck1.com", ssn_last4="0000", dob="1990-01-05")
        assert out["verified"] is False
        assert state.verified is False

    def test_failure_does_not_say_which_field_was_wrong(self):
        state = fresh()
        out = submit(state, email="alice@ck1.com", ssn_last4="0000", dob="1990-01-05")
        blob = json.dumps(out).lower()
        for field in ("ssn", "email", "dob", "birth"):
            assert field not in blob

    def test_failure_clears_collected_so_fields_cannot_be_brute_forced_one_at_a_time(self):
        state = fresh()
        submit(state, email="alice@ck1.com", ssn_last4="0000", dob="1990-01-05")
        assert state.collected == {}
        assert state.failed_attempts == 1

    def test_mixing_two_customers_details_does_not_verify(self):
        state = fresh()
        out = submit(state, email="alice@ck1.com", ssn_last4="5678", dob="1990-01-05")
        assert out["verified"] is False

    def test_rejected_email_never_reaches_the_session(self):
        state = fresh()
        out = submit(state, email="attacker@gmail.com")
        assert out["verified"] is False
        assert out["problems"]
        assert "email" not in state.collected

    def test_ambiguous_dob_asks_instead_of_guessing(self):
        state = fresh()
        out = submit(state, dob="05/01/1990")
        assert out["need_clarification"] == "dob"
        assert "1990-01-05" in out["message"]
        assert "1990-05-01" in out["message"]
        assert "dob" not in state.collected


class TestToolDispatch:
    def test_unknown_tool_is_reported_not_raised(self):
        assert run_tool("drop_all_tables", {}, fresh())["error"] == "UNKNOWN_TOOL"

    def test_a_crashing_tool_becomes_an_error_result(self, monkeypatch):
        def boom(_args, _state):
            raise RuntimeError("database on fire")

        monkeypatch.setitem(__import__("app.tools", fromlist=["_DISPATCH"])._DISPATCH,
                            "list_orders", boom)
        out = run_tool("list_orders", {}, verified_as("C001"))
        assert out["error"] == "TOOL_FAILED"

    def test_missing_arguments_do_not_crash(self):
        assert "error" in run_tool("get_order_status", {}, verified_as("C001"))


class TestKnowledgeBase:
    def test_weak_matches_are_dropped_rather_than_answered(self, monkeypatch):
        monkeypatch.setattr("app.retrieval.search",
                            lambda q, **kw: [{"page": 4, "text": "unrelated", "score": 0.12}])
        out = run_tool("search_knowledge_base", {"query": "capital of France"}, fresh())
        assert out["results"] == []
        assert "note" in out

    def test_strong_matches_are_returned_with_pages(self, monkeypatch):
        monkeypatch.setattr("app.retrieval.search",
                            lambda q, **kw: [{"page": 18, "text": "Net sales 280,522", "score": 0.54}])
        out = run_tool("search_knowledge_base", {"query": "net sales"}, fresh())
        assert out["results"][0]["page"] == 18
        assert "280,522" in out["results"][0]["text"]

    def test_search_does_not_require_verification(self, monkeypatch):
        monkeypatch.setattr("app.retrieval.search",
                            lambda q, **kw: [{"page": 3, "text": "segments", "score": 0.5}])
        assert "error" not in run_tool("search_knowledge_base", {"query": "segments"}, fresh())

    @pytest.mark.aws
    def test_real_retrieval_finds_net_sales_on_page_18(self):
        out = run_tool("search_knowledge_base",
                       {"query": "What were the company's net sales in 2019?"}, fresh())
        assert 18 in [r["page"] for r in out["results"]]


class TestDataFixtures:
    def test_every_order_belongs_to_a_known_customer(self):
        customers = {c["customer_id"] for c in
                     json.loads((config.DATA / "customers.json").read_text(encoding="utf8"))}
        assert {o["customer_id"] for o in ORDERS} <= customers

    def test_the_idor_fixture_still_belongs_to_another_customer(self):
        owner = next(o["customer_id"] for o in ORDERS if o["order_id"] == BOBS_ORDER)
        assert owner == "C002"
