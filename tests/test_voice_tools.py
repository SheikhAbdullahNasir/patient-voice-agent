import re
import uuid

from app.config import settings
from app.services import patients as patient_service


def call_tool(client, name, args, headers):
    body = {"message": {"type": "tool-calls",
                        "toolCallList": [{"id": "call_1", "name": name, "arguments": args}]}}
    return client.post("/vapi/tools", json=body, headers=headers)


def result_of(response):
    assert response.status_code == 200
    item = response.json()["results"][0]
    assert item["toolCallId"] == "call_1"
    return item["result"]


def test_lookup_finds_nobody_for_unused_number(client, auth_headers):
    text = result_of(call_tool(client, "lookup_patient", {"phone_number": "555-010-0999"}, auth_headers))
    assert text.startswith("No existing patient")


def test_save_lookup_and_duplicate_flow(client, payload, auth_headers):
    assert result_of(call_tool(client, "save_patient", payload, auth_headers)).startswith("Saved successfully")
    found = result_of(call_tool(client, "lookup_patient", {"phone_number": payload["phone_number"]}, auth_headers))
    assert payload["last_name"] in found
    assert result_of(call_tool(client, "save_patient", payload, auth_headers)).startswith("Already registered")


def test_bad_date_names_the_field(client, payload, auth_headers):
    payload["date_of_birth"] = "01/01/2099"
    text = result_of(call_tool(client, "save_patient", payload, auth_headers))
    assert text.startswith("NOT SAVED") and "date_of_birth" in text and "future" in text


def test_missing_field_is_listed(client, payload, auth_headers):
    del payload["city"]
    text = result_of(call_tool(client, "save_patient", payload, auth_headers))
    assert text.startswith("NOT SAVED") and "city" in text


def test_numeric_zip_is_accepted(client, payload, auth_headers):
    payload["zip_code"] = 78701
    assert result_of(call_tool(client, "save_patient", payload, auth_headers)).startswith("Saved successfully")


def test_update_changes_city(client, payload, auth_headers):
    saved = result_of(call_tool(client, "save_patient", payload, auth_headers))
    pid = re.search(r"patient_id=([0-9a-f-]{36})", saved).group(1)
    updated = result_of(call_tool(client, "update_patient", {"patient_id": pid, "city": "Dallas"}, auth_headers))
    assert updated.startswith("Updated successfully")
    assert client.get(f"/patients/{pid}").json()["data"]["city"] == "Dallas"


def test_update_unknown_patient(client, auth_headers):
    text = result_of(call_tool(client, "update_patient", {"patient_id": str(uuid.uuid4())}, auth_headers))
    assert "No patient found" in text


def test_unknown_tool(client, auth_headers):
    assert "Unknown tool" in result_of(call_tool(client, "does_not_exist", {}, auth_headers))


def test_database_failure_gives_a_spoken_fallback(client, payload, auth_headers, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(patient_service, "create_patient", boom)
    text = result_of(call_tool(client, "save_patient", payload, auth_headers))
    assert text.startswith("NOT SAVED") and "temporary system problem" in text


def test_secret_is_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "vapi_secret", "s3cret")
    args = {"phone_number": "5550100999"}
    assert call_tool(client, "lookup_patient", args, {}).status_code == 401
    assert call_tool(client, "lookup_patient", args, {"Authorization": "Bearer s3cret"}).status_code == 200
    assert call_tool(client, "lookup_patient", args, {"x-vapi-secret": "s3cret"}).status_code == 200


def test_other_message_types_are_ignored(client, auth_headers):
    r = client.post("/vapi/tools", json={"message": {"type": "status-update"}}, headers=auth_headers)
    assert r.status_code == 200 and r.json() == {"results": []}


def test_events_endpoint_accepts_end_of_call_report(client, auth_headers):
    body = {"message": {"type": "end-of-call-report", "endedReason": "customer-ended-call",
                        "call": {"id": "abc"}, "artifact": {"transcript": "AI: Hi\nUser: Hello"}}}
    assert client.post("/vapi/events", json=body, headers=auth_headers).status_code == 200