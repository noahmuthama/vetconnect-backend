from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import RequestStatus, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    role: UserRole = UserRole.CLIENT
    password: str = Field(min_length=10, max_length=128)

    @field_validator("role")
    @classmethod
    def prevent_public_admin_signup(cls, value: UserRole) -> UserRole:
        if value == UserRole.ADMIN:
            raise ValueError("Administrator accounts cannot be created through public registration")
        return value
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("password")
    @classmethod
    def require_password_complexity(cls, value: str) -> str:
        if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    vet_verified: bool
    verification_reviewed_at: Optional[datetime] = None
    verification_reviewed_by: Optional[int] = None
    verification_notes: Optional[str] = None
    is_available: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class VerificationReview(BaseModel):
    verified: bool
    notes: Optional[str] = Field(default=None, max_length=1000)


class VerificationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    vet_verified: bool
    verification_reviewed_at: Optional[datetime] = None
    verification_reviewed_by: Optional[int] = None
    verification_notes: Optional[str] = None


class VetAvailabilityUpdate(BaseModel):
    is_available: bool
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=80)
    breed: Optional[str] = Field(default=None, max_length=120)
    age: int = Field(ge=0, le=200)


class PetRead(PetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int


class ServiceRequestCreate(BaseModel):
    pet_id: int = Field(gt=0)
    description: str = Field(min_length=5, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ServiceRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    client_id: int
    vet_id: Optional[int] = None
    description: str
    latitude: float
    longitude: float
    status: RequestStatus


class StatusUpdate(BaseModel):
    status: RequestStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[EmailStr] = None
