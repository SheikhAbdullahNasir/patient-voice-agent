"""REST endpoints for /patients. Thin layer: parse input, call service, wrap output."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import PatientCreate, PatientOut, PatientUpdate, normalize_phone, parse_dob
from app.services import patients as service

router = APIRouter(prefix="/patients", tags=["patients"])


def ok(data):
    """Every successful response uses the same envelope."""
    return {"data": data, "error": None}


def to_json(patient) -> dict:
    return PatientOut.model_validate(patient).model_dump(mode="json")


def parse_id(patient_id: str) -> UUID:
    try:
        return UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="patient_id must be a valid UUID")


def load_or_404(db: Session, patient_id: str):
    patient = service.get_patient(db, parse_id(patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("")
def list_patients(
    last_name: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        dob = parse_dob(date_of_birth) if date_of_birth else None
        phone = normalize_phone(phone_number) if phone_number else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {exc}")
    patients = service.list_patients(db, last_name, dob, phone)
    return ok([to_json(p) for p in patients])


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    return ok(to_json(load_or_404(db, patient_id)))


@router.post("", status_code=201)
def create_patient(body: PatientCreate, db: Session = Depends(get_db)):
    return ok(to_json(service.create_patient(db, body)))


@router.put("/{patient_id}")
def update_patient(patient_id: str, body: PatientUpdate, db: Session = Depends(get_db)):
    patient = load_or_404(db, patient_id)
    if not body.model_fields_set:
        raise HTTPException(status_code=400, detail="No fields provided to update")
    return ok(to_json(service.update_patient(db, patient, body)))


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = load_or_404(db, patient_id)
    service.soft_delete_patient(db, patient)
    return ok({"patient_id": str(patient.patient_id), "deleted": True})