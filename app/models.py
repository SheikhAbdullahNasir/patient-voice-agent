import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Patient(Base):
    __tablename__ = "patients"

    # --- Identity ---
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Required fields ---
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    date_of_birth: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(20))
    phone_number: Mapped[str] = mapped_column(String(10))  # stored as 10 digits
    address_line_1: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))  # 12345 or 12345-6789

    # --- Optional fields ---
    email: Mapped[str | None] = mapped_column(String(254))
    address_line_2: Mapped[str | None] = mapped_column(String(100))
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_id: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(
        String(50), default="English", server_default="English"
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))

    # --- Timestamps (UTC) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # soft delete

    __table_args__ = (
        CheckConstraint(
            "sex IN ('Male', 'Female', 'Other', 'Decline to Answer')", name="ck_sex"
        ),
        CheckConstraint("phone_number ~ '^[0-9]{10}$'", name="ck_phone_10_digits"),
        CheckConstraint(
            "emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^[0-9]{10}$'",
            name="ck_emergency_phone_10_digits",
        ),
        CheckConstraint("state ~ '^[A-Z]{2}$'", name="ck_state_2_letters"),
        CheckConstraint("zip_code ~ '^[0-9]{5}(-[0-9]{4})?$'", name="ck_zip_format"),
        # Not unique on purpose: family members can share a phone number.
        # The app checks for duplicates and asks the caller what to do.
        Index("ix_patients_phone_number", "phone_number"),
        Index("ix_patients_last_name", "last_name"),
    )