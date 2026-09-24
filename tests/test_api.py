import uuid

import pytest

from app.db import SessionLocal
from app.models import Patient


def create(client, payload):
    response = client.post("/patients", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_health(client):
    assert client.get("/health").json() == {"data": {"status": "ok"}, "error": None}


def test_create_returns_201_and_clean_data(client, payload):
    r = client.post("/patients", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    assert data["patient_id"]
    assert (data["first_name"], data["sex"], data["state"]) == ("Jane", "Female", "TX")
    assert data["phone_number"] == "5551234567"


def test_list_filters_by_last_name(client, payload):
    create(client, payload)
    r = client.get("/patients", params={"last_name": payload["last_name"]})
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


def test_list_filters_by_phone_and_dob(client, payload):
    create(client, payload)
    r = client.get("/patients", params={"phone_number": "555-123-4567", "date_of_birth": "03/15/1990"})
    assert r.status_code == 200
    assert payload["last_name"] in [p["last_name"] for p in r.json()["data"]]


def test_bad_filter_is_400(client):
    assert client.get("/patients", params={"phone_number": "12"}).status_code == 400


def test_get_by_id(client, payload):
    pid = create(client, payload)["patient_id"]
    r = client.get(f"/patients/{pid}")
    assert r.status_code == 200
    assert r.json()["data"]["patient_id"] == pid


def test_unknown_id_is_404(client):
    r = client.get(f"/patients/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["data"] is None


def test_malformed_id_is_400(client):
    assert client.get("/patients/not-a-uuid").status_code == 400


def test_partial_update_changes_only_sent_fields(client, payload):
    pid = create(client, payload)["patient_id"]
    r = client.put(f"/patients/{pid}", json={"city": "Dallas"})
    assert r.status_code == 200
    assert (r.json()["data"]["city"], r.json()["data"]["first_name"]) == ("Dallas", "Jane")


def test_empty_update_is_400(client, payload):
    pid = create(client, payload)["patient_id"]
    assert client.put(f"/patients/{pid}", json={}).status_code == 400


def test_required_field_cannot_be_nulled(client, payload):
    pid = create(client, payload)["patient_id"]
    assert client.put(f"/patients/{pid}", json={"first_name": None}).status_code == 422


def test_delete_is_soft(client, payload):
    pid = create(client, payload)["patient_id"]
    assert client.delete(f"/patients/{pid}").status_code == 200
    assert client.get(f"/patients/{pid}").status_code == 404
    listed = client.get("/patients", params={"last_name": payload["last_name"]}).json()["data"]
    assert listed == []
    with SessionLocal() as db:  # the row still exists, just marked deleted
        row = db.get(Patient, uuid.UUID(pid))
        assert row is not None and row.deleted_at is not None


@pytest.mark.parametrize("field,value", [
    ("phone_number", "123"),
    ("date_of_birth", "01/01/2099"),
    ("state", "ZZ"),
    ("zip_code", "1234"),
    ("first_name", "J4ne"),
    ("email", "not-an-email"),
    ("sex", "robot"),
])
def test_invalid_input_is_422_and_names_the_field(client, payload, field, value):
    payload[field] = value
    r = client.post("/patients", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert body["data"] is None
    assert body["error"]["fields"][0]["field"] == field


def test_missing_required_field_is_422(client, payload):
    del payload["city"]
    assert client.post("/patients", json=payload).status_code == 422


def test_unknown_field_is_422(client, payload):
    payload["nickname"] = "JD"
    assert client.post("/patients", json=payload).status_code == 422


def test_invalid_json_is_400(client):
    r = client.post("/patients", content="{bad", headers={"Content-Type": "application/json"})
    assert r.status_code == 400