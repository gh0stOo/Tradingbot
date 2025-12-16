from datetime import datetime, date
from pydantic import BaseModel, EmailStr
from typing import Optional, List


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    name: str


class OrganizationOut(BaseModel):
    id: str
    name: str
    autopilot_enabled: bool

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    autopilot_enabled: bool = False


class ProjectOut(BaseModel):
    id: str
    name: str
    autopilot_enabled: bool
    organization_id: str

    class Config:
        from_attributes = True


class PlanOut(BaseModel):
    id: str
    slot_date: date
    slot_index: int
    status: str
    project_id: str

    class Config:
        from_attributes = True


class PromptVersionOut(BaseModel):
    name: str
    version: int
    body: str

    class Config:
        from_attributes = True


class VideoAssetOut(BaseModel):
    id: str
    status: str
    video_path: str
    thumbnail_path: str

    class Config:
        from_attributes = True


class MetricOut(BaseModel):
    metric: str
    value: int
    created_at: datetime

    class Config:
        from_attributes = True


class CalendarSlot(BaseModel):
    date: date
    slots: List[PlanOut]
