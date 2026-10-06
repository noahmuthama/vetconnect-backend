from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import auth
import database
import main
import models


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    models.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    original_session_local = database.SessionLocal
    database.SessionLocal = TestingSessionLocal
    main.app.dependency_overrides[database.get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    database.SessionLocal = original_session_local
    models.Base.metadata.drop_all(bind=engine)


def register(client: TestClient, email: str, role: str = "client") -> dict:
    response = client.post(
        "/register",
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "role": role,
            "password": "securepass123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def token_for(client: TestClient, email: str) -> str:
    response = client.post("/token", data={"username": email, "password": "securepass123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_me(client: TestClient):
    register(client, "owner@example.com")
    token = token_for(client, "owner@example.com")
    response = client.get("/me", headers=headers(token))
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["role"] == "client"


def test_password_policy_and_role_enforcement(client: TestClient):
    response = client.post(
        "/register",
        json={"email": "weak@example.com", "full_name": "Weak User", "password": "short", "role": "client"},
    )
    assert response.status_code == 422

    register(client, "vet@example.com", role="vet")
    vet_token = token_for(client, "vet@example.com")
    response = client.post(
        "/pets/",
        json={"name": "Buddy", "species": "dog", "age": 4},
        headers=headers(vet_token),
    )
    assert response.status_code == 403


def test_pet_ownership_and_request_creation(client: TestClient):
    register(client, "owner@example.com")
    owner_token = token_for(client, "owner@example.com")
    register(client, "other@example.com")
    other_token = token_for(client, "other@example.com")

    pet = client.post(
        "/pets/",
        json={"name": "Buddy", "species": "dog", "breed": "retriever", "age": 4},
        headers=headers(owner_token),
    )
    assert pet.status_code == 201
    pet_id = pet.json()["id"]

    forbidden_request = client.post(
        "/requests/",
        json={"pet_id": pet_id, "description": "Needs care", "latitude": 40.7, "longitude": -73.9},
        headers=headers(other_token),
    )
    assert forbidden_request.status_code == 404

    request = client.post(
        "/requests/",
        json={"pet_id": pet_id, "description": "Needs a checkup", "latitude": 40.7, "longitude": -73.9},
        headers=headers(owner_token),
    )
    assert request.status_code == 201
    assert request.json()["status"] == "pending"


def test_unverified_vet_cannot_dispatch(client: TestClient):
    register(client, "vet@example.com", role="vet")
    vet_token = token_for(client, "vet@example.com")
    response = client.put(
        "/vets/me/availability",
        json={"is_available": True, "latitude": 40.7, "longitude": -73.9},
        headers=headers(vet_token),
    )
    assert response.status_code == 403


def test_verified_vet_acceptance_and_lifecycle(client: TestClient):
    register(client, "owner@example.com")
    owner_token = token_for(client, "owner@example.com")
    register(client, "vet@example.com", role="vet")
    vet_token = token_for(client, "vet@example.com")

    db: Session = database.SessionLocal()
    try:
        vet = db.scalar(select(models.User).where(models.User.email == "vet@example.com"))
        assert vet is not None
        vet.vet_verified = True
        db.commit()
    finally:
        db.close()

    availability = client.put(
        "/vets/me/availability",
        json={"is_available": True, "latitude": 40.7, "longitude": -73.9},
        headers=headers(vet_token),
    )
    assert availability.status_code == 200

    pet = client.post(
        "/pets/",
        json={"name": "Miso", "species": "cat", "age": 2},
        headers=headers(owner_token),
    ).json()
    request = client.post(
        "/requests/",
        json={"pet_id": pet["id"], "description": "Miso needs an exam", "latitude": 40.7, "longitude": -73.9},
        headers=headers(owner_token),
    ).json()

    accepted = client.post(f"/requests/{request['id']}/accept", headers=headers(vet_token))
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    invalid_client_transition = client.put(
        f"/requests/{request['id']}/status",
        json={"status": "completed"},
        headers=headers(owner_token),
    )
    assert invalid_client_transition.status_code == 403

    in_progress = client.put(
        f"/requests/{request['id']}/status",
        json={"status": "in_progress"},
        headers=headers(vet_token),
    )
    assert in_progress.status_code == 200

    completed = client.put(
        f"/requests/{request['id']}/status",
        json={"status": "completed"},
        headers=headers(vet_token),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    repeated = client.put(
        f"/requests/{request['id']}/status",
        json={"status": "cancelled"},
        headers=headers(vet_token),
    )
    assert repeated.status_code == 409


def test_only_admin_can_verify_veterinarians(client: TestClient):
    register(client, "vet@example.com", role="vet")
    vet_token = token_for(client, "vet@example.com")

    public_admin = client.post(
        "/register",
        json={"email": "admin@example.com", "full_name": "Admin", "role": "admin", "password": "securepass123"},
    )
    assert public_admin.status_code == 422

    db: Session = database.SessionLocal()
    try:
        admin = models.User(
            email="admin@example.com",
            full_name="Platform Admin",
            hashed_password=auth.get_password_hash("securepass123"),
            role=models.UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()

    admin_token = token_for(client, "admin@example.com")
    pending = client.get("/admin/vets/pending", headers=headers(admin_token))
    assert pending.status_code == 200
    assert pending.json()[0]["email"] == "vet@example.com"

    vet_id = pending.json()[0]["id"]
    reviewed = client.put(
        f"/admin/vets/{vet_id}/verification",
        json={"verified": True, "notes": "Credentials checked in staging"},
        headers=headers(admin_token),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["vet_verified"] is True

    denied = client.get("/admin/vets/pending", headers=headers(vet_token))
    assert denied.status_code == 403
