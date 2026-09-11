from datetime import date

import pytest

from app.verification import Ambiguous, parse_dob, parse_email, parse_ssn_last4

TODAY = date(2026, 9, 10)


@pytest.mark.parametrize("raw,expected", [
    ("user@ck1.com", "user@ck1.com"),
    ("user@ck123.com", "user@ck123.com"),
    ("USER@CK2.COM", "user@ck2.com"),
    ("email của tôi là alice@ck1.com nhé", "alice@ck1.com"),
    ("alice@ck1.com.", "alice@ck1.com"),
])
def test_email_hop_le(raw, expected):
    assert parse_email(raw)[0] == expected


@pytest.mark.parametrize("raw", [
    "user@gmail.com",      
    "user@ck.com",         
    "user@ckabc.com",      
    "không có email",
])
def test_email_bi_tu_choi(raw):
    email, reason = parse_email(raw)
    assert email is None and reason


@pytest.mark.parametrize("raw,expected", [
    ("1234", "1234"),
    ("123-45-6789", "6789"),         
    ("my ssn is 6789", "6789"),
    ("SSN: 123 45 6789", "6789"),
])
def test_ssn(raw, expected):
    assert parse_ssn_last4(raw)[0] == expected


def test_ssn_thieu_so():
    assert parse_ssn_last4("12")[0] is None


@pytest.mark.parametrize("raw", [
    "Jan 5 1990",
    "January 5th, 1990",
    "I was born on January 5th, 1990",
    "1990-01-05",
    "5 January 1990",
])
def test_dob_ro_rang(raw):
    assert parse_dob(raw, today=TODAY)[0] == date(1990, 1, 5)


def test_dob_mo_ho_phai_hoi_lai():
    got, _ = parse_dob("05/01/1990", today=TODAY)
    assert isinstance(got, Ambiguous)
    assert {got.first, got.second} == {date(1990, 1, 5), date(1990, 5, 1)}


def test_dob_khong_mo_ho_vi_khong_co_thang_13():
    assert parse_dob("13/01/1990", today=TODAY)[0] == date(1990, 1, 13)


@pytest.mark.parametrize("raw", ["yesterday", "", "abcd", "1234", "hôm qua"])
def test_dob_khong_doc_duoc(raw):
    assert parse_dob(raw, today=TODAY)[0] is None


def test_dob_tuong_lai_bi_chan():
    assert parse_dob("2030-01-01", today=TODAY)[0] is None