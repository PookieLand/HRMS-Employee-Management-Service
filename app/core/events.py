from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    EMPLOYEE_CREATED = "employee.created"
    EMPLOYEE_UPDATED = "employee.updated"
    EMPLOYEE_DELETED = "employee.deleted"


class EventMetadata(BaseModel):
    source_service: str = "employee-management-service"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    causation_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0"
    data: dict[str, Any]
    metadata: EventMetadata


class EmployeeCreatedEvent(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    email: str
    contact_number: str | None
    position: str
    department: str
    date_of_hire: str


class EmployeeUpdatedEvent(BaseModel):
    employee_id: int
    updated_fields: dict[str, Any]


class EmployeeDeletedEvent(BaseModel):
    employee_id: int
    email: str
