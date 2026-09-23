"""
Validation and cleanup rules for patient data.

Every value is checked and normalised here BEFORE it reaches the database,
so the REST API and the voice agent share exactly the same rules.
"""
import re
from datetime import date, datetime
from typing import Annotated, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    model_validator,
)

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "PR", "VI", "GU", "AS", "MP",
}

SEX_VALUES = {
    "male": "Male",
    "female": "Female",
    "other": "Other",
    "decline to answer": "Decline to Answer",
    "decline": "Decline to Answer",
    "prefer not to say": "Decline to Answer",
}

# Letters (any language), joined by single spaces, hyphens or apostrophes.
NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")


# ---------- helper functions ----------

def clean_text(value: str) -> str:
    """Basic sanitisation: collapse whitespace, drop control chars, block < >."""
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
    if "<" in value or ">" in value:
        raise ValueError("contains invalid characters")
    return value


def validate_name(value: str) -> str:
    value = clean_text(value).replace("\u2019", "'")
    if not 1 <= len(value) <= 50:
        raise ValueError("must be 1-50 characters")
    if not NAME_RE.match(value):
        raise ValueError("may only contain letters, hyphens, apostrophes and spaces")
    if value.islower() or value.isupper():  # speech-to-text often gives lowercase
        value = value.title()
    return value


def required_text(max_len: int):
    def _validate(value: str) -> str:
        value = clean_text(value)
        if not 1 <= len(value) <= max_len:
            raise ValueError(f"must be 1-{max_len} characters")
        return value
    return _validate


def optional_text(max_len: int):
    def _validate(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = clean_text(value)
        if not value:
            return None
        if len(value) > max_len:
            raise ValueError(f"must be at most {max_len} characters")
        return value
    return _validate


def parse_dob(value) -> date:
    """Accepts MM/DD/YYYY or YYYY-MM-DD. Rejects future and impossible dates."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                value = datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("must be a valid date in MM/DD/YYYY format")
    if not isinstance(value, date):
        raise ValueError("must be a valid date in MM/DD/YYYY format")
    if value > date.today():
        raise ValueError("cannot be in the future")
    if value.year < 1900:
        raise ValueError("is too far in the past")
    return value


def validate_sex(value: str) -> str:
    canonical = SEX_VALUES.get(value.strip().lower())
    if canonical is None:
        raise ValueError("must be one of: Male, Female, Other, Decline to Answer")
    return canonical


def normalize_phone(value: str) -> str:
    """'(555) 123-4567' or '+1 555 123 4567' -> '5551234567'."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01":
        raise ValueError("must be a valid 10-digit U.S. phone number")
    return digits


def optional_phone(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return normalize_phone(value)


def validate_state(value: str) -> str:
    value = value.strip().upper()
    if value not in US_STATES:
        raise ValueError("must be a valid 2-letter U.S. state abbreviation")
    return value


def validate_zip(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"\d{5}(-\d{4})?", value):
        raise ValueError("must be a 5-digit ZIP or ZIP+4 (12345-6789)")
    return value


def validate_member_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"[\s\-]", "", value)
    if not value:
        return None
    if not re.fullmatch(r"[A-Za-z0-9]{1,50}", value):
        raise ValueError("must be letters and numbers only (max 50 characters)")
    return value.upper()


def validate_language(value: Optional[str]) -> str:
    if value is None or not value.strip():
        return "English"
    return required_text(50)(value)


def blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# ---------- field types (validation attached to each type) ----------

Name = Annotated[str, AfterValidator(validate_name)]
Sex = Annotated[str, AfterValidator(validate_sex)]
DateOfBirth = Annotated[date, BeforeValidator(parse_dob)]
Phone = Annotated[str, AfterValidator(normalize_phone)]
OptionalPhone = Annotated[Optional[str], AfterValidator(optional_phone)]
Address1 = Annotated[str, AfterValidator(required_text(200))]
City = Annotated[str, AfterValidator(required_text(100))]
State = Annotated[str, AfterValidator(validate_state)]
Zip = Annotated[str, AfterValidator(validate_zip)]
OptText100 = Annotated[Optional[str], AfterValidator(optional_text(100))]
MemberId = Annotated[Optional[str], AfterValidator(validate_member_id)]
Language = Annotated[Optional[str], AfterValidator(validate_language)]
Email = Annotated[
    Optional[EmailStr],
    BeforeValidator(blank_to_none),
    AfterValidator(lambda v: v.lower() if v else v),
]

REQUIRED_FIELDS = [
    "first_name", "last_name", "date_of_birth", "sex", "phone_number",
    "address_line_1", "city", "state", "zip_code", "preferred_language",
]


# ---------- request / response models ----------

class PatientCreate(BaseModel):
    """Body of POST /patients."""
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    date_of_birth: DateOfBirth
    sex: Sex
    phone_number: Phone
    address_line_1: Address1
    city: City
    state: State
    zip_code: Zip
    email: Email = None
    address_line_2: OptText100 = None
    insurance_provider: OptText100 = None
    insurance_member_id: MemberId = None
    preferred_language: Language = "English"
    emergency_contact_name: OptText100 = None
    emergency_contact_phone: OptionalPhone = None


class PatientUpdate(BaseModel):
    """Body of PUT /patients/:id. Every field is optional (partial update)."""
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[Name] = None
    last_name: Optional[Name] = None
    date_of_birth: Optional[DateOfBirth] = None
    sex: Optional[Sex] = None
    phone_number: Optional[Phone] = None
    address_line_1: Optional[Address1] = None
    city: Optional[City] = None
    state: Optional[State] = None
    zip_code: Optional[Zip] = None
    email: Email = None
    address_line_2: OptText100 = None
    insurance_provider: OptText100 = None
    insurance_member_id: MemberId = None
    preferred_language: Optional[Language] = None
    emergency_contact_name: OptText100 = None
    emergency_contact_phone: OptionalPhone = None

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self):
        for name in REQUIRED_FIELDS:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be empty or null")
        return self


class PatientOut(BaseModel):
    """What the API returns for a patient."""
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str]
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str]
    insurance_member_id: Optional[str]
    preferred_language: str
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    created_at: datetime
    updated_at: datetime