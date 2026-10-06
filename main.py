from contextlib import asynccontextmanager
import logging
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

import auth
import crud
import database
import models
import schemas
from settings import get_settings


settings = get_settings()
logger = logging.getLogger("vetconnect.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema changes are managed by Alembic. The API process does not mutate the
    # database schema on startup.
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="Secure, location-aware veterinary care dispatch API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "request_complete method=%s path=%s status=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


DbSession = Annotated[Session, Depends(database.get_db)]


@app.get("/healthz", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.post("/token", response_model=schemas.Token, tags=["authentication"])
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return schemas.Token(access_token=auth.create_access_token(user.email, user.role))


@app.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED, tags=["authentication"])
def register(user: schemas.UserCreate, db: DbSession):
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.get("/me", response_model=schemas.UserRead, tags=["authentication"])
def get_me(current_user: auth.CurrentUser):
    return current_user


@app.get("/admin/vets/pending", response_model=list[schemas.VerificationResult], tags=["administration"])
def list_pending_vets(current_user: auth.CurrentAdmin, db: DbSession):
    return list(
        db.scalars(
            select(models.User)
            .where(models.User.role == models.UserRole.VET, models.User.verification_reviewed_at.is_(None))
            .order_by(models.User.created_at)
        ).all()
    )


@app.put("/admin/vets/{vet_id}/verification", response_model=schemas.VerificationResult, tags=["administration"])
def review_vet(vet_id: int, payload: schemas.VerificationReview, current_user: auth.CurrentAdmin, db: DbSession):
    vet = db.scalar(select(models.User).where(models.User.id == vet_id))
    if vet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veterinarian not found")
    return crud.review_veterinarian(db, vet, current_user, payload)


@app.post("/pets/", response_model=schemas.PetRead, status_code=status.HTTP_201_CREATED, tags=["pets"])
def add_pet(pet: schemas.PetCreate, current_user: auth.CurrentClient, db: DbSession):
    return crud.create_pet(db=db, pet=pet, owner_id=current_user.id)


@app.get("/pets/", response_model=list[schemas.PetRead], tags=["pets"])
def list_pets(current_user: auth.CurrentClient, db: DbSession):
    return crud.get_user_pets(db=db, owner_id=current_user.id)


@app.put("/vets/me/availability", response_model=schemas.UserRead, tags=["veterinarians"])
def update_availability(payload: schemas.VetAvailabilityUpdate, current_user: auth.CurrentVet, db: DbSession):
    return crud.set_vet_availability(db, current_user, payload)


@app.post("/requests/", response_model=schemas.ServiceRequestRead, status_code=status.HTTP_201_CREATED, tags=["service requests"])
def create_request(request: schemas.ServiceRequestCreate, current_user: auth.CurrentClient, db: DbSession):
    pet = db.scalar(select(models.Pet).where(models.Pet.id == request.pet_id, models.Pet.owner_id == current_user.id))
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    return crud.create_service_request(db=db, request=request, client_id=current_user.id)


@app.get("/requests/nearby/", response_model=list[schemas.ServiceRequestRead], tags=["service requests"])
def get_nearby_requests(
    current_user: auth.CurrentVet,
    db: DbSession,
    radius_km: float = Query(default=10.0, gt=0, le=settings.max_nearby_radius_km),
):
    if not current_user.vet_verified or not current_user.is_available:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verified and available veterinarian status is required")
    if current_user.latitude is None or current_user.longitude is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vet location is not set")
    nearby = []
    for request in crud.get_available_requests(db):
        distance = crud.calculate_distance(current_user.latitude, current_user.longitude, request.latitude, request.longitude)
        if distance <= radius_km:
            nearby.append(request)
    return nearby


@app.post("/requests/{request_id}/accept", response_model=schemas.ServiceRequestRead, tags=["service requests"])
def accept_vet_request(request_id: int, current_user: auth.CurrentVet, db: DbSession):
    return crud.accept_request(db, request_id=request_id, vet=current_user)


@app.put("/requests/{request_id}/status", response_model=schemas.ServiceRequestRead, tags=["service requests"])
def update_status(
    request_id: int,
    payload: schemas.StatusUpdate,
    current_user: auth.CurrentUser,
    db: DbSession,
):
    request = db.scalar(select(models.ServiceRequest).where(models.ServiceRequest.id == request_id))
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return crud.update_request_status(db, request, current_user, payload.status)
