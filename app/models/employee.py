from datetime import date
from decimal import Decimal

from sqlmodel import Field, SQLModel


class EmployeeBase(SQLModel):
    """Base fields shared across Employee models"""

    first_name: str = Field(index=True, max_length=255, min_length=1)
    last_name: str = Field(max_length=255, min_length=1)
    age: int | None = Field(default=None, ge=0, le=100)
    date_of_birth: date | None = None
    contact_number: str | None = None
    email: str = Field(max_length=255)
    gender: str | None = None
    address: str | None = None


class Employee(EmployeeBase, table=True):
    """ORM model for Employee table"""

    id: int | None = Field(default=None, primary_key=True)
    position: str = Field(max_length=255)
    department: str = Field(max_length=255)
    date_of_hire: date
    contract_type: str = Field(max_length=100)
    salary: Decimal = Field(max_digits=12, decimal_places=2)


class EmployeeCreate(SQLModel):
    """Input schema for creating a new employee"""

    first_name: str = Field(max_length=255, min_length=1)
    last_name: str = Field(max_length=255, min_length=1)
    age: int | None = Field(default=None, ge=0, le=100)
    date_of_birth: date | None = None
    contact_number: str | None = None
    email: str = Field(max_length=255)
    gender: str | None = None
    address: str | None = None
    position: str = Field(max_length=255)
    department: str = Field(max_length=255)
    date_of_hire: date
    contract_type: str = Field(max_length=100)
    salary: Decimal = Field(max_digits=12, decimal_places=2)


class EmployeeUpdate(SQLModel):
    """Input schema for updating an existing employee"""

    first_name: str | None = Field(default=None, max_length=255, min_length=1)
    last_name: str | None = Field(default=None, max_length=255, min_length=1)
    age: int | None = Field(default=None, ge=0, le=100)
    date_of_birth: date | None = None
    contact_number: str | None = None
    email: str | None = Field(default=None, max_length=255)
    gender: str | None = None
    address: str | None = None
    position: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    date_of_hire: date | None = None
    contract_type: str | None = Field(default=None, max_length=100)
    salary: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)


class EmployeePublic(SQLModel):
    """Output schema for public API responses"""

    id: int
    first_name: str
    last_name: str
    position: str
    department: str
    date_of_hire: date
    contract_type: str


class EmployeeDetailed(SQLModel):
    """Output schema for detailed employee information (admin/audit purposes)"""

    id: int
    first_name: str
    last_name: str
    age: int | None
    date_of_birth: date | None
    contact_number: str | None
    email: str
    gender: str | None
    address: str | None
    position: str
    department: str
    date_of_hire: date
    contract_type: str
    salary: Decimal
