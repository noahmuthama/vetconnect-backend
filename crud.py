from datetime import datetime, timezone
from math import asin, cos, pi, sin, sqrt

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
import schemas


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.email == email.lower()))


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        email=user.email.lower(),
        full_name=user.full_name,
        hashed_password=auth.get_password_hash(user.password),
        role=user.role,
        latitude=user.latitude,
        longitude=user.longitude,
        # Vet accounts require a later verification step before dispatch access.
        vet_verified=False,
        is_available=False,
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    db.refresh(db_user)
    return db_user


def create_pet(db: Session, pet: schemas.PetCreate, owner_id: int) -> models.Pet:
    db_pet = models.Pet(**pet.model_dump(), owner_id=owner_id)
    db.add(db_pet)
    db.commit()
    db.refresh(db_pet)
    return db_pet


def get_user_pets(db: Session, owner_id: int) -> list[models.Pet]:
    return list(db.scalars(select(models.Pet).where(models.Pet.owner_id == owner_id).order_by(models.Pet.id)).all())


def create_service_request(db: Session, request: schemas.ServiceRequestCreate, client_id: int) -> models.ServiceRequest:
    db_request = models.ServiceRequest(
        **request.model_dump(),
        client_id=client_id,
        status=models.RequestStatus.PENDING,
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request


def get_available_requests(db: Session) -> list[models.ServiceRequest]:
    return list(
        db.scalars(
            select(models.ServiceRequest)
            .where(models.ServiceRequest.status == models.RequestStatus.PENDING)
            .order_by(models.ServiceRequest.created_at)
        ).all()
    )


def set_vet_availability(db: Session, vet: models.User, payload: schemas.VetAvailabilityUpdate) -> models.User:
    if not vet.vet_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Veterinarian verification is required")
    if payload.is_available and (payload.latitude is None or payload.longitude is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Latitude and longitude are required when becoming available")
    vet.is_available = payload.is_available
    if payload.latitude is not None:
        vet.latitude = payload.latitude
    if payload.longitude is not None:
        vet.longitude = payload.longitude
    db.commit()
    db.refresh(vet)
    return vet


def accept_request(db: Session, request_id: int, vet: models.User) -> models.ServiceRequest:
    if not vet.vet_verified or not vet.is_available:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verified and available veterinarian status is required")
    # The predicate makes acceptance safe when two veterinarians race for the same request.
    result = db.execute(
        update(models.ServiceRequest)
        .where(
            models.ServiceRequest.id == request_id,
            models.ServiceRequest.status == models.RequestStatus.PENDING,
            models.ServiceRequest.vet_id.is_(None),
        )
        .values(
            vet_id=vet.id,
            status=models.RequestStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is no longer available")
    db.commit()
    return db.scalar(select(models.ServiceRequest).where(models.ServiceRequest.id == request_id))


def update_request_status(
    db: Session,
    request: models.ServiceRequest,
    actor: models.User,
    new_status: models.RequestStatus,
) -> models.ServiceRequest:
    if actor.id != request.client_id and actor.id != request.vet_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this request")

    allowed = {
        models.RequestStatus.PENDING: {models.RequestStatus.CANCELLED},
        models.RequestStatus.ACCEPTED: {models.RequestStatus.IN_PROGRESS, models.RequestStatus.CANCELLED},
        models.RequestStatus.IN_PROGRESS: {models.RequestStatus.COMPLETED, models.RequestStatus.CANCELLED},
        models.RequestStatus.COMPLETED: set(),
        models.RequestStatus.CANCELLED: set(),
    }
    if new_status in {models.RequestStatus.IN_PROGRESS, models.RequestStatus.COMPLETED} and actor.id != request.vet_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned veterinarian can advance care")
    if new_status not in allowed[request.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition request from {request.status.value} to {new_status.value}",
        )
    if new_status == models.RequestStatus.CANCELLED and actor.id not in {request.client_id, request.vet_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the request participants can cancel")

    request.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == models.RequestStatus.COMPLETED:
        request.completed_at = now
    if new_status == models.RequestStatus.CANCELLED:
        request.cancelled_at = now
    db.commit()
    db.refresh(request)
    return request


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = pi / 180
    a = 0.5 - cos((lat2 - lat1) * p) / 2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
    return 12742 * asin(sqrt(max(0, min(1, a))))


def review_veterinarian(
    db: Session,
    vet: models.User,
    reviewer: models.User,
    payload: schemas.VerificationReview,
) -> models.User:
    if vet.role != models.UserRole.VET:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only veterinarian accounts can be reviewed")
    if vet.id == reviewer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An administrator cannot review their own account")

    vet.vet_verified = payload.verified
    vet.is_available = False if not payload.verified else vet.is_available
    vet.verification_reviewed_at = datetime.now(timezone.utc)
    vet.verification_reviewed_by = reviewer.id
    vet.verification_notes = payload.notes
    db.commit()
    db.refresh(vet)
    return vet
