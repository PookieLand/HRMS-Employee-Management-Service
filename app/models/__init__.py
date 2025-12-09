"""
Employee Management Service Models.

Exports all model classes for easy importing.
"""

from app.models.employee import (
    Employee,
    EmployeeCreate,
    EmployeeDashboardMetrics,
    EmployeeDetailed,
    EmployeeListResponse,
    EmployeePromote,
    EmployeePublic,
    EmployeeSalaryUpdate,
    EmployeeStatus,
    EmployeeStatusUpdate,
    EmployeeSummary,
    EmployeeTransfer,
    EmployeeUpdate,
    EmploymentType,
    Gender,
    InternalEmployeeCreate,
    OnboardingEmployeeCreate,
)

__all__ = [
    # Database Model
    "Employee",
    # Enums
    "EmployeeStatus",
    "EmploymentType",
    "Gender",
    # Request Schemas
    "InternalEmployeeCreate",
    "OnboardingEmployeeCreate",
    "EmployeeCreate",
    "EmployeeUpdate",
    "EmployeeStatusUpdate",
    "EmployeeSalaryUpdate",
    "EmployeePromote",
    "EmployeeTransfer",
    # Response Schemas
    "EmployeePublic",
    "EmployeeDetailed",
    "EmployeeSummary",
    "EmployeeListResponse",
    "EmployeeDashboardMetrics",
]
