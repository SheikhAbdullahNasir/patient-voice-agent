"""Adds two demo patients (fictional data). Safe to run more than once."""
from app.db import SessionLocal
from app.schemas import PatientCreate
from app.services import patients as service

SEED = [
    {"first_name": "Maria", "last_name": "Gonzalez", "date_of_birth": "08/22/1979", "sex": "Female",
     "phone_number": "555-014-2211", "email": "maria.gonzalez@example.com",
     "address_line_1": "88 Elm Street", "city": "Newark", "state": "NJ", "zip_code": "07102",
     "insurance_provider": "Aetna", "insurance_member_id": "AB123456", "preferred_language": "Spanish"},
    {"first_name": "Robert", "last_name": "Chen", "date_of_birth": "11/03/1965", "sex": "Male",
     "phone_number": "555-017-7342", "address_line_1": "1500 Market Street", "address_line_2": "Apt 4B",
     "city": "Philadelphia", "state": "PA", "zip_code": "19102",
     "emergency_contact_name": "Linda Chen", "emergency_contact_phone": "555-017-7343"},
]


def main():
    with SessionLocal() as db:
        for row in SEED:
            data = PatientCreate(**row)
            if service.list_patients(db, phone_number=data.phone_number):
                print(f"Skipped (already exists): {data.first_name} {data.last_name}")
                continue
            service.create_patient(db, data)
            print(f"Added: {data.first_name} {data.last_name}")


if __name__ == "__main__":
    main()