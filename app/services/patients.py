"""
Data layer: all database actions for patients.

Both the REST routes and (later) the voice-agent tools call these functions,
so there is exactly one place where patients are created or changed.
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Patient
from app.schemas import PatientCreate, PatientUpdate

logger = logging.getLogger("patients")


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
) -> list[Patient]:
    stmt = select(Patient).where(Patient.deleted_at.is_(None))  # hide soft-deleted
    if last_name:
        stmt = stmt.where(func.lower(Patient.last_name) == last_name.strip().lower())
    if date_of_birth:
        stmt = stmt.where(Patient.date_of_birth == date_of_birth)
    if phone_number:
        stmt = stmt.where(Patient.phone_number == phone_number)
    return list(db.scalars(stmt.order_by(Patient.created_at.desc())))


def get_patient(db: Session, patient_id: UUID) -> Optional[Patient]:
    stmt = select(Patient).where(
        Patient.patient_id == patient_id, Patient.deleted_at.is_(None)
    )
    return db.scalars(stmt).first()


def create_patient(db: Session, data: PatientCreate) -> Patient:
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    logger.info("Patient created: %s", patient.patient_id)
    return patient


def update_patient(db: Session, patient: Patient, data: PatientUpdate) -> Patient:
    # exclude_unset -> only change the fields the caller actually sent
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    logger.info("Patient updated: %s", patient.patient_id)
    return patient


def soft_delete_patient(db: Session, patient: Patient) -> None:
    patient.deleted_at = datetime.now(timezone.utc)  # never a hard delete
    db.commit()
    logger.info("Patient soft-deleted: %s", patient.patient_id)