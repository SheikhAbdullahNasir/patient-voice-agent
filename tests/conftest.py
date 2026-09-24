import random
import string

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import Patient
from app.config import settings


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def last_name():
    """A unique, letters-only last name so every test owns its data."""
    return "Test" + "".join(random.choices(string.ascii_lowercase, k=10))


@pytest.fixture
def payload(last_name):
    """A valid patient body. Rows with this last name are removed after the test."""
    yield {
        "first_name": "jane",
        "last_name": last_name,
        "date_of_birth": "03/15/1990",
        "sex": "female",
        "phone_number": "(555) 123-4567",
        "address_line_1": "123 Main St",
        "city": "Austin",
        "state": "tx",
        "zip_code": "78701",
    }
    with SessionLocal() as db:
        db.execute(delete(Patient).where(Patient.last_name == last_name))
        db.commit()

@pytest.fixture
def auth_headers():
    """The header the real app expects on every /vapi/* call, when a secret is configured."""
    if settings.vapi_secret:
        return {"Authorization": f"Bearer {settings.vapi_secret}"}
    return {}        