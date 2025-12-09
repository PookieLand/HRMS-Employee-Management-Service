"""
Event definitions for Employee Management Service.

Defines all event types and their data structures for Kafka publishing.
Events are categorized into:
- Employee lifecycle events (create, update, delete, terminate)
- Employment status events (probation, contract)
- Salary events
- Department/Team events
- HR events (reviews, notifications)
- Special events (birthdays, anniversaries)
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All event types produced by the Employee Management Service."""

    # Employee Lifecycle Events
    EMPLOYEE_CREATED = "employee.created"
    EMPLOYEE_UPDATED = "employee.updated"
    EMPLOYEE_DELETED = "employee.deleted"
    EMPLOYEE_TERMINATED = "employee.terminated"
    EMPLOYEE_PROMOTED = "employee.promoted"
    EMPLOYEE_TRANSFERRED = "employee.transferred"

    # Employment Status Events
    EMPLOYEE_PROBATION_STARTED = "employee.probation.started"
    EMPLOYEE_PROBATION_COMPLETED = "employee.probation.completed"
    EMPLOYEE_CONTRACT_STARTED = "employee.contract.started"
    EMPLOYEE_CONTRACT_RENEWED = "employee.contract.renewed"
    EMPLOYEE_CONTRACT_ENDED = "employee.contract.ended"

    # Status Change Events
    EMPLOYEE_ACTIVATED = "employee.activated"
    EMPLOYEE_SUSPENDED = "employee.suspended"
    EMPLOYEE_RESIGNED = "employee.resigned"

    # Salary Events
    EMPLOYEE_SALARY_UPDATED = "employee.salary.updated"
    EMPLOYEE_SALARY_INCREMENT = "employee.salary.increment"

    # Department/Team Events
    EMPLOYEE_DEPARTMENT_CHANGED = "employee.department.changed"
    EMPLOYEE_TEAM_CHANGED = "employee.team.changed"
    EMPLOYEE_MANAGER_CHANGED = "employee.manager.changed"

    # HR Events
    HR_PROBATION_ENDING = "hr.probation.ending"
    HR_CONTRACT_EXPIRING = "hr.contract.expiring"
    HR_PERFORMANCE_REVIEW_DUE = "hr.performance.review.due"
    HR_SALARY_INCREMENT_DUE = "hr.salary.increment.due"

    # Special Events (Celebrations)
    SPECIAL_BIRTHDAY = "employee.special.birthday"
    SPECIAL_WORK_ANNIVERSARY = "employee.special.work.anniversary"

    # Audit Events
    AUDIT_EMPLOYEE_ACTION = "audit.employee.action"


class EventMetadata(BaseModel):
    """Metadata attached to every event for tracing and correlation."""

    source_service: str = "employee-management-service"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    causation_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    trace_id: Optional[str] = None
    ip_address: Optional[str] = None


class EventEnvelope(BaseModel):
    """
    Standard envelope for all events.
    Provides consistent structure for Kafka messages.
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0"
    data: dict[str, Any]
    metadata: EventMetadata = Field(default_factory=EventMetadata)


# Employee Lifecycle Event Data Models


class EmployeeCreatedEvent(BaseModel):
    """Data for employee.created event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    role: str
    job_title: str
    department: Optional[str] = None
    team: Optional[str] = None
    manager_id: Optional[int] = None
    employment_type: str
    salary: float
    salary_currency: str
    joining_date: date
    probation_months: Optional[int] = None
    probation_end_date: Optional[date] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    created_by: Optional[int] = None


class EmployeeUpdatedEvent(BaseModel):
    """Data for employee.updated event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    updated_fields: dict[str, Any]
    previous_values: Optional[dict[str, Any]] = None
    updated_by: Optional[int] = None


class EmployeeDeletedEvent(BaseModel):
    """Data for employee.deleted event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    deleted_by: int
    reason: Optional[str] = None


class EmployeeTerminatedEvent(BaseModel):
    """Data for employee.terminated event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    termination_date: date
    reason: Optional[str] = None
    terminated_by: int


class EmployeePromotedEvent(BaseModel):
    """Data for employee.promoted event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    old_position: str
    new_position: str
    old_job_title: str
    new_job_title: str
    old_salary: Optional[float] = None
    new_salary: Optional[float] = None
    old_department: Optional[str] = None
    new_department: Optional[str] = None
    effective_date: date
    promoted_by: int


class EmployeeTransferredEvent(BaseModel):
    """Data for employee.transferred event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    old_department: Optional[str] = None
    new_department: str
    old_team: Optional[str] = None
    new_team: Optional[str] = None
    old_manager_id: Optional[int] = None
    new_manager_id: Optional[int] = None
    effective_date: date
    transferred_by: int


# Employment Status Event Data Models


class ProbationStartedEvent(BaseModel):
    """Data for employee.probation.started event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    probation_months: int
    probation_start_date: date
    probation_end_date: date
    manager_id: Optional[int] = None


class ProbationCompletedEvent(BaseModel):
    """Data for employee.probation.completed event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    probation_start_date: date
    probation_end_date: date
    completed_date: date
    status: str  # 'passed', 'extended', 'terminated'
    notes: Optional[str] = None


class ContractStartedEvent(BaseModel):
    """Data for employee.contract.started event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    contract_start_date: date
    contract_end_date: date
    contract_type: str


class ContractRenewedEvent(BaseModel):
    """Data for employee.contract.renewed event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    old_contract_end_date: date
    new_contract_end_date: date
    renewed_by: int


class ContractEndedEvent(BaseModel):
    """Data for employee.contract.ended event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    contract_end_date: date
    reason: str  # 'completed', 'terminated', 'converted_to_permanent'


# Status Change Event Data Models


class EmployeeActivatedEvent(BaseModel):
    """Data for employee.activated event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    activated_by: int


class EmployeeSuspendedEvent(BaseModel):
    """Data for employee.suspended event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    suspended_by: int
    reason: Optional[str] = None


class EmployeeResignedEvent(BaseModel):
    """Data for employee.resigned event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    resignation_date: date
    last_working_date: date
    reason: Optional[str] = None


# Salary Event Data Models


class SalaryUpdatedEvent(BaseModel):
    """Data for employee.salary.updated event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    old_salary: float
    new_salary: float
    salary_currency: str
    effective_date: date
    reason: Optional[str] = None
    updated_by: int


class SalaryIncrementEvent(BaseModel):
    """Data for employee.salary.increment event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    old_salary: float
    new_salary: float
    increment_percentage: float
    salary_currency: str
    effective_date: date
    years_of_service: int
    approved_by: int


# Department/Team Event Data Models


class DepartmentChangedEvent(BaseModel):
    """Data for employee.department.changed event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    old_department: Optional[str]
    new_department: str
    effective_date: date
    changed_by: int


class TeamChangedEvent(BaseModel):
    """Data for employee.team.changed event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    old_team: Optional[str]
    new_team: str
    effective_date: date
    changed_by: int


class ManagerChangedEvent(BaseModel):
    """Data for employee.manager.changed event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    old_manager_id: Optional[int]
    new_manager_id: int
    effective_date: date
    changed_by: int


# HR Event Data Models


class ProbationEndingEvent(BaseModel):
    """Data for hr.probation.ending event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    probation_end_date: date
    days_remaining: int
    manager_id: Optional[int] = None
    manager_email: Optional[str] = None


class ContractExpiringEvent(BaseModel):
    """Data for hr.contract.expiring event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    contract_end_date: date
    days_remaining: int
    manager_id: Optional[int] = None
    manager_email: Optional[str] = None


class PerformanceReviewDueEvent(BaseModel):
    """Data for hr.performance.review.due event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    review_due_date: date
    years_since_joining: int
    manager_id: Optional[int] = None
    manager_email: Optional[str] = None


class SalaryIncrementDueEvent(BaseModel):
    """Data for hr.salary.increment.due event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    increment_due_date: date
    years_of_service: int
    current_salary: float
    salary_currency: str
    manager_id: Optional[int] = None


# Special Event Data Models


class BirthdayEvent(BaseModel):
    """Data for employee.special.birthday event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    date_of_birth: date
    age: Optional[int] = None
    department: Optional[str] = None


class WorkAnniversaryEvent(BaseModel):
    """Data for employee.special.work.anniversary event."""

    employee_id: int
    user_id: Optional[int] = None
    email: str
    first_name: str
    last_name: str
    joining_date: date
    years_of_service: int
    department: Optional[str] = None


# Audit Event Data Model


class AuditEmployeeActionEvent(BaseModel):
    """Data for audit.employee.action event."""

    actor_user_id: int
    actor_email: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: int
    description: str
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# Helper functions for creating events


def create_event(
    event_type: EventType,
    data: BaseModel,
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    """
    Helper function to create an event envelope with proper metadata.

    Args:
        event_type: Type of the event
        data: Event data as a Pydantic model
        actor_user_id: ID of the user performing the action
        actor_role: Role of the user performing the action
        correlation_id: Optional correlation ID for tracing

    Returns:
        EventEnvelope ready for publishing
    """
    metadata = EventMetadata(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        correlation_id=correlation_id or str(uuid4()),
    )

    return EventEnvelope(
        event_type=event_type,
        data=data.model_dump(mode="json"),
        metadata=metadata,
    )
