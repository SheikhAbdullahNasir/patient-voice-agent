"""
Voice-agent tool endpoint.

Vapi POSTs here whenever the assistant calls a tool (lookup / save / update).
This file is a thin adapter: it translates Vapi's message format into calls to
the SAME service layer and validation rules the REST API uses.

Vapi protocol rules (from the Vapi docs):
  * Always answer HTTP 200 - other status codes are ignored by Vapi.
  * Echo back each call's `toolCallId`.
  * `result` must be a single-line string. Errors go in the result text,
    written as instructions the assistant can act on ("ask the caller again for X").
"""
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import PatientCreate, PatientUpdate, normalize_phone
from app.services import patients as service

router = APIRouter(prefix="/vapi", tags=["voice"])
logger = logging.getLogger("vapi")


# ---------- helpers ----------

def _parse_call(call: dict) -> tuple[str | None, dict]:
    """Vapi sends slightly different shapes over time; accept both."""
    fn = call.get("function") or {}
    name = call.get("name") or fn.get("name")
    args = (
        call.get("arguments") or call.get("parameters")
        or fn.get("arguments") or fn.get("parameters") or {}
    )
    if isinstance(args, str):  # sometimes arrives as a JSON string
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return name, args


def _clean_args(args: dict, model) -> dict:
    """Keep only known fields, drop empty values, turn numbers into text."""
    allowed = set(model.model_fields)
    cleaned = {}
    for key, value in args.items():
        if key not in allowed or value in (None, ""):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)  # e.g. zip code 78701 arrives as a number
        cleaned[key] = value
    return cleaned


def _validation_message(exc: ValidationError) -> str:
    """Turn validation errors into an instruction the assistant can act on."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"]) or "value"
        if err["type"] == "missing":
            message = "is required but missing"
        else:
            message = err["msg"].removeprefix("Value error, ")
        parts.append(f"{field} {message}")
    return (
        "NOT SAVED. Invalid or missing data: " + "; ".join(parts)
        + ". Ask the caller again for only these fields, then retry."
    )


# ---------- tools ----------

def tool_lookup_patient(db: Session, args: dict) -> str:
    try:
        phone = normalize_phone(str(args.get("phone_number", "")))
    except ValueError as exc:
        return f"Invalid phone number: {exc}. Ask the caller to repeat it."
    matches = service.list_patients(db, phone_number=phone)
    if not matches:
        return "No existing patient found with this phone number."
    people = "; ".join(
        f"{p.first_name} {p.last_name} (patient_id={p.patient_id})" for p in matches
    )
    return (
        f"Existing record(s) found: {people}. Ask the caller whether they are one of "
        "these people and want to update their information instead of registering again."
    )


def tool_save_patient(db: Session, args: dict) -> str:
    try:
        payload = PatientCreate(**_clean_args(args, PatientCreate))
    except ValidationError as exc:
        return _validation_message(exc)

    # Idempotency: if the assistant retries, don't create a second identical record.
    for p in service.list_patients(db, phone_number=payload.phone_number):
        if (p.first_name.lower(), p.last_name.lower(), p.date_of_birth) == (
            payload.first_name.lower(), payload.last_name.lower(), payload.date_of_birth
        ):
            return (
                f"Already registered. patient_id={p.patient_id}. "
                "Tell the caller they are all set."
            )

    try:
        patient = service.create_patient(db, payload)
    except Exception:
        db.rollback()
        logger.exception("Database write failed while saving patient")
        return (
            "NOT SAVED because of a temporary system problem. Apologize briefly to the "
            "caller and offer to try saving again."
        )

    # Observability: log the final collected payload (required by the assignment).
    logger.info("FINAL PAYLOAD: %s", json.dumps(payload.model_dump(mode="json")))
    return (
        f"Saved successfully. patient_id={patient.patient_id}. "
        f"Tell the caller they are all set, {patient.first_name}."
    )


def tool_update_patient(db: Session, args: dict) -> str:
    try:
        patient_id = UUID(str(args.get("patient_id", "")))
    except ValueError:
        return "Invalid patient_id. Use the patient_id returned by lookup_patient."
    patient = service.get_patient(db, patient_id)
    if patient is None:
        return "No patient found with that patient_id."

    try:
        payload = PatientUpdate(**_clean_args(args, PatientUpdate))
    except ValidationError as exc:
        return _validation_message(exc)
    if not payload.model_fields_set:
        return "No changes were provided. Ask the caller what they would like to update."

    try:
        service.update_patient(db, patient, payload)
    except Exception:
        db.rollback()
        logger.exception("Database write failed while updating patient")
        return (
            "NOT UPDATED because of a temporary system problem. Apologize briefly and "
            "offer to try again."
        )
    logger.info("UPDATED %s: %s", patient_id, json.dumps(payload.model_dump(mode="json", exclude_unset=True)))
    return "Updated successfully. Tell the caller their information has been updated."


TOOLS = {
    "lookup_patient": tool_lookup_patient,
    "save_patient": tool_save_patient,
    "update_patient": tool_update_patient,
}


# ---------- endpoint ----------

@router.post("/tools")
def handle_tool_calls(body: dict = Body(default={}), db: Session = Depends(get_db)):
    message = body.get("message") or {}
    if message.get("type") != "tool-calls":
        return {"results": []}

    results = []
    for call in message.get("toolCallList") or []:
        name, args = _parse_call(call)
        logger.info("Tool call: %s", name)
        handler = TOOLS.get(name)
        if handler is None:
            result = f"Unknown tool '{name}'."
        else:
            try:
                result = handler(db, args)
            except Exception:  # never let an exception turn into silence on the phone
                db.rollback()
                logger.exception("Tool %s crashed", name)
                result = "A system error occurred. Apologize briefly and offer to try again."
        # Vapi wants a single-line string.
        results.append({"toolCallId": call.get("id"), "result": " ".join(str(result).split())})
    return {"results": results}