"""
Employee database models and schemas for Employee Management Service.

Includes comprehensive employee data for onboarding integration,
HR management, and payroll operations.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class EmploymentType(str, Enum):
    """Type of employment."""

    PERMANENT = "permanent"
    CONTRACT = "contract"


class EmployeeStatus(str, Enum):
    """Employee status in the system."""

    ACTIVE = "active"
    ON_PROBATION = "on_probation"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"


class Gender(str, Enum):
    """Gender options."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


# Database Models


class Employee(SQLModel, table=True):
    """
    ORM model for Employee table.

    Contains all employee data including:
    - Basic identity info
    - Employment details (job, salary, department)
    - Contract/probation information
    - Personal details
    - Emergency contacts
    - Bank details for payroll
    """

    __tablename__ = "employees"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Link to User Management Service
    user_id: Optional[int] = Field(default=None, index=True, unique=True)

    # Basic Identity
    first_name: str = Field(max_length=255, min_length=1)
    last_name: str = Field(max_length=255, min_length=1)
    email: str = Field(max_length=255, index=True, unique=True)
    phone: Optional[str] = Field(default=None, max_length=20)

    # Role and Status
    role: str = Field(default="employee", max_length=50)
    status: str = Field(default=EmployeeStatus.ACTIVE.value, max_length=50)

    # Job Details
    job_title: str = Field(default="Employee", max_length=100)
    position: str = Field(default="Employee", max_length=255)
    department: Optional[str] = Field(default=None, max_length=255)
    team: Optional[str] = Field(default=None, max_length=100)
    manager_id: Optional[int] = Field(default=None)

    # Salary Information
    salary: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    salary_currency: str = Field(default="USD", max_length=3)

    # Employment Type and Dates
    employment_type: str = Field(default=EmploymentType.PERMANENT.value, max_length=20)
    date_of_hire: date = Field(default_factory=date.today)
    joining_date: Optional[date] = Field(default=None)

    # Probation (for permanent employees)
    probation_months: Optional[int] = Field(default=None)
    probation_end_date: Optional[date] = Field(default=None)
    probation_completed: bool = Field(default=False)

    # Contract (for contract employees)
    contract_type: str = Field(default="Full-Time", max_length=100)
    contract_start_date: Optional[date] = Field(default=None)
    contract_end_date: Optional[date] = Field(default=None)

    # Important Review Dates
    performance_review_date: Optional[date] = Field(default=None)
    salary_increment_date: Optional[date] = Field(default=None)
    next_review_date: Optional[date] = Field(default=None)

    # Personal Details
    date_of_birth: Optional[date] = Field(default=None)
    age: Optional[int] = Field(default=None, ge=0, le=100)
    gender: Optional[str] = Field(default=None, max_length=10)
    nationality: Optional[str] = Field(default=None, max_length=100)

    # Address
    address: Optional[str] = Field(default=None, max_length=500)
    address_line_1: Optional[str] = Field(default=None, max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)

    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(default=None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=20)
    emergency_contact_relationship: Optional[str] = Field(default=None, max_length=50)

    # Bank Details (for payroll)
    bank_name: Optional[str] = Field(default=None, max_length=100)
    bank_account_number: Optional[str] = Field(default=None, max_length=50)
    bank_routing_number: Optional[str] = Field(default=None, max_length=50)

    # Metadata
    notes: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    terminated_at: Optional[datetime] = Field(default=None)


# Request Schemas


class InternalEmployeeCreate(SQLModel):
    """
    Simplified input schema for internal service-to-service employee creation.
    Used by User Management Service during basic signup.
    Only requires basic user info; other fields get default values.
    """

    user_id: int
    email: str = Field(max_length=255)
    first_name: str = Field(max_length=255, min_length=1)
    last_name: str = Field(max_length=255, min_length=1)
    contact_number: Optional[str] = None


class OnboardingEmployeeCreate(BaseModel):
    """
    Full employee creation schema for onboarding flow.
    Contains all the data collected during HR onboarding process.
    """

    # User Management Link
    user_id: int

    # Basic Identity
    email: EmailStr
    first_name: str = PydanticField(min_length=1, max_length=255)
    last_name: str = PydanticField(min_length=1, max_length=255)
    phone: Optional[str] = None

    # Role and Job Details
    role: str = PydanticField(default="employee", max_length=50)
    job_title: str = PydanticField(default="Employee", max_length=100)
    department: Optional[str] = None
    team: Optional[str] = None
    manager_id: Optional[int] = None

    # Salary Information
    salary: float = PydanticField(default=0.0, ge=0)
    salary_currency: str = PydanticField(default="USD", max_length=3)

    # Employment Type and Dates
    employment_type: str = PydanticField(default="permanent")
    joining_date: date

    # Probation (for permanent employees)
    probation_months: Optional[int] = PydanticField(default=None, ge=1, le=12)
    probation_end_date: Optional[date] = None

    # Contract (for contract employees)
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None

    # Important Review Dates
    performance_review_date: Optional[date] = None
    salary_increment_date: Optional[date] = None

    # Personal Details (from signup step 2)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None

    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

    # Emergency Contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None

    # Bank Details
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_routing_number: Optional[str] = None

    # Notes
    notes: Optional[str] = None


class EmployeeCreate(SQLModel):
    """Input schema for creating a new employee (authenticated endpoint)."""

    first_name: str = Field(max_length=255, min_length=1)
    last_name: str = Field(max_length=255, min_length=1)
    email: str = Field(max_length=255)
    phone: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    position: str = Field(max_length=255)
    job_title: str = Field(default="Employee", max_length=100)
    department: str = Field(max_length=255)
    team: Optional[str] = None
    manager_id: Optional[int] = None
    date_of_hire: date
    employment_type: str = Field(default="permanent", max_length=20)
    contract_type: str = Field(default="Full-Time", max_length=100)
    salary: Decimal = Field(max_digits=12, decimal_places=2)
    salary_currency: str = Field(default="USD", max_length=3)
    probation_months: Optional[int] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None


class EmployeeUpdate(SQLModel):
    """Input schema for updating an existing employee."""

    first_name: Optional[str] = Field(default=None, max_length=255, min_length=1)
    last_name: Optional[str] = Field(default=None, max_length=255, min_length=1)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    # Address
    address: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

    # Job Details
    position: Optional[str] = Field(default=None, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=100)
    department: Optional[str] = Field(default=None, max_length=255)
    team: Optional[str] = None
    manager_id: Optional[int] = None

    # Employment
    date_of_hire: Optional[date] = None
    employment_type: Optional[str] = Field(default=None, max_length=20)
    contract_type: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=50)

    # Salary
    salary: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    salary_currency: Optional[str] = None

    # Dates
    probation_months: Optional[int] = None
    probation_end_date: Optional[date] = None
    probation_completed: Optional[bool] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    performance_review_date: Optional[date] = None
    salary_increment_date: Optional[date] = None

    # Emergency Contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None

    # Bank Details
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_routing_number: Optional[str] = None

    # Notes
    notes: Optional[str] = None


class EmployeeStatusUpdate(SQLModel):
    """Schema for updating employee status."""

    status: str = Field(max_length=50)
    reason: Optional[str] = Field(default=None, max_length=500)


class EmployeeSalaryUpdate(SQLModel):
    """Schema for updating employee salary."""

    salary: Decimal = Field(max_digits=12, decimal_places=2)
    salary_currency: Optional[str] = Field(default=None, max_length=3)
    effective_date: Optional[date] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class EmployeePromote(SQLModel):
    """Schema for promoting an employee."""

    new_position: str = Field(max_length=255)
    new_job_title: str = Field(max_length=100)
    new_salary: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    new_department: Optional[str] = None
    effective_date: date
    reason: Optional[str] = Field(default=None, max_length=500)


class EmployeeTransfer(SQLModel):
    """Schema for transferring an employee."""

    new_department: str = Field(max_length=255)
    new_team: Optional[str] = None
    new_manager_id: Optional[int] = None
    effective_date: date
    reason: Optional[str] = Field(default=None, max_length=500)


# Response Schemas


class EmployeePublic(SQLModel):
    """Output schema for public API responses (limited fields)."""

    id: int
    first_name: str
    last_name: str
    email: str
    position: str
    job_title: str
    department: Optional[str]
    team: Optional[str]
    date_of_hire: date
    employment_type: str
    contract_type: str
    status: str


class EmployeeDetailed(SQLModel):
    """Output schema for detailed employee information (admin/HR purposes)."""

    id: int
    user_id: Optional[int]

    # Basic Identity
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]

    # Role and Status
    role: str
    status: str

    # Job Details
    job_title: str
    position: str
    department: Optional[str]
    team: Optional[str]
    manager_id: Optional[int]

    # Salary
    salary: Decimal
    salary_currency: str

    # Employment
    employment_type: str
    date_of_hire: date
    joining_date: Optional[date]
    contract_type: str

    # Probation
    probation_months: Optional[int]
    probation_end_date: Optional[date]
    probation_completed: bool

    # Contract
    contract_start_date: Optional[date]
    contract_end_date: Optional[date]

    # Review Dates
    performance_review_date: Optional[date]
    salary_increment_date: Optional[date]

    # Personal
    date_of_birth: Optional[date]
    age: Optional[int]
    gender: Optional[str]
    nationality: Optional[str]

    # Address
    address_line_1: Optional[str]
    address_line_2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]

    # Emergency Contact
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    emergency_contact_relationship: Optional[str]

    # Metadata
    created_at: datetime
    updated_at: datetime


class EmployeeSummary(SQLModel):
    """Minimal employee summary for lists and dropdowns."""

    id: int
    user_id: Optional[int]
    first_name: str
    last_name: str
    email: str
    job_title: str
    department: Optional[str]
    status: str


class EmployeeListResponse(SQLModel):
    """Paginated employee list response."""

    total: int
    employees: list[EmployeePublic]


class EmployeeDashboardMetrics(BaseModel):
    """Dashboard metrics for employee statistics."""

    total_employees: int
    active_employees: int
    on_probation: int
    on_leave: int
    suspended: int
    permanent_employees: int
    contract_employees: int
    employees_by_department: dict[str, int]
    employees_by_role: dict[str, int]
    new_hires_this_month: int
    probation_ending_soon: int
    contracts_expiring_soon: int
    birthdays_this_month: int
    work_anniversaries_this_month: int
