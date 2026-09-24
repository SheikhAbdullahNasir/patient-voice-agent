from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import PatientCreate, normalize_phone, parse_dob, validate_state, validate_zip

BASE = {
    "first_name": "jane", "last_name": "o'neil-smith", "date_of_birth": "03/15/1990",
    "sex": "decline", "phone_number": "555.123.4567", "address_line_1": "1 Main St",
    "city": "Austin", "state": "tx", "zip_code": "78701",
}


def test_phone_is_normalised():
    assert normalize_phone("(555) 123-4567") == "5551234567"


def test_phone_strips_country_code():
    assert normalize_phone("+1 555 123 4567") == "5551234567"


@pytest.mark.parametrize("bad", ["123", "555123456", "0551234567", "abcdefghij"])
def test_bad_phone_is_rejected(bad):
    with pytest.raises(ValueError):
        normalize_phone(bad)


def test_dob_accepts_us_format():
    assert parse_dob("03/15/1990") == date(1990, 3, 15)


def test_dob_rejects_future():
    future = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")
    with pytest.raises(ValueError):
        parse_dob(future)


def test_dob_rejects_impossible_date():
    with pytest.raises(ValueError):
        parse_dob("02/30/1990")


def test_state_is_uppercased_and_checked():
    assert validate_state(" tx ") == "TX"
    with pytest.raises(ValueError):
        validate_state("ZZ")


def test_zip_formats():
    assert validate_zip("78701") == "78701"
    assert validate_zip("78701-1234") == "78701-1234"
    with pytest.raises(ValueError):
        validate_zip("1234")


def test_patient_create_cleans_input():
    p = PatientCreate(**BASE)
    assert p.first_name == "Jane"
    assert p.last_name == "O'Neil-Smith"
    assert p.sex == "Decline to Answer"
    assert p.phone_number == "5551234567"
    assert p.state == "TX"
    assert p.preferred_language == "English"


def test_digits_in_name_are_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(**{**BASE, "first_name": "J4ne"})