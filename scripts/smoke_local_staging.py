import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from sqlalchemy import select

import auth
import database
import models

BASE_URL = os.getenv("VETCONNECT_BASE_URL", "http://127.0.0.1:8001")
PASSWORD = "stagingpass123"


def register(email: str, role: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/register",
        json={"email": email, "full_name": role.title(), "role": role, "password": PASSWORD},
        timeout=10,
    )
    if response.status_code not in {200, 201, 409}:
        response.raise_for_status()
    return response.json() if response.status_code != 409 else {}


def token(email: str) -> str:
    response = requests.post(
        f"{BASE_URL}/token",
        data={"username": email, "password": PASSWORD},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main() -> None:
    requests.get(f"{BASE_URL}/healthz", timeout=10).raise_for_status()
    register("staging-client@example.com", "client")
    register("staging-vet@example.com", "vet")
    client_token = token("staging-client@example.com")
    vet_token = token("staging-vet@example.com")

    db = database.SessionLocal()
    try:
        vet = db.scalar(select(models.User).where(models.User.email == "staging-vet@example.com"))
        admin = db.scalar(select(models.User).where(models.User.email == "staging-admin@example.com"))
        if vet is None:
            raise RuntimeError("staging veterinarian was not created")
        vet.vet_verified = True
        vet.verification_reviewed_at = datetime.now(timezone.utc)
        if admin is None:
            admin = models.User(
                email="staging-admin@example.com",
                full_name="Staging Admin",
                hashed_password=auth.get_password_hash(PASSWORD),
                role=models.UserRole.ADMIN,
            )
            db.add(admin)
        db.commit()
    finally:
        db.close()

    client_headers = {"Authorization": f"Bearer {client_token}"}
    vet_headers = {"Authorization": f"Bearer {vet_token}"}
    pet = requests.post(
        f"{BASE_URL}/pets/",
        headers=client_headers,
        json={"name": "Miso", "species": "cat", "age": 2},
        timeout=10,
    )
    pet.raise_for_status()
    pet_id = pet.json()["id"]

    service_request = requests.post(
        f"{BASE_URL}/requests/",
        headers=client_headers,
        json={"pet_id": pet_id, "description": "Staging health check", "latitude": 40.7, "longitude": -73.9},
        timeout=10,
    )
    service_request.raise_for_status()
    request_id = service_request.json()["id"]

    available = requests.put(
        f"{BASE_URL}/vets/me/availability",
        headers=vet_headers,
        json={"is_available": True, "latitude": 40.7, "longitude": -73.9},
        timeout=10,
    )
    available.raise_for_status()
    accepted = requests.post(f"{BASE_URL}/requests/{request_id}/accept", headers=vet_headers, timeout=10)
    accepted.raise_for_status()

    print({"status": "ok", "pet_id": pet_id, "request_id": request_id, "request_status": accepted.json()["status"]})


if __name__ == "__main__":
    main()
