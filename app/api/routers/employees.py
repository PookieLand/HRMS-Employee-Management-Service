"""
Employee Management API endpoints.

Provides endpoints for:
- Internal service-to-service employee creation (onboarding integration)
- RBAC-protected employee CRUD operations
- Employee status management (suspend, activate, terminate)
- Salary and promotion operations
- Dashboard metrics

RBAC Rules:
- HR_Admin: Full access to all employee data and operations
- HR_Manager: Access to managers and employees, limited HR operations
- manager: Access to team members only
- employee: Access to own data only
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select

from app.api.dependencies import CurrentUserDep, SessionDep
from app.core.cache import (
    clear_cache_pattern,
    delete_from_cache,
    get_cache_key,
    get_from_cache,
    set_to_cache,
)
from app.core.events import (
    EmployeeCreatedEvent,
    EmployeeDeletedEvent,
    EmployeePromotedEvent,
    EmployeeSuspendedEvent,
    EmployeeTerminatedEvent,
    EmployeeTransferredEvent,
    EmployeeUpdatedEvent,
    EventType,
    SalaryUpdatedEvent,
    create_event,
)
from app.core.kafka import publish_event
from app.core.logging import get_logger
from app.core.rbac import (
    can_delete_employee,
    can_modify_salary,
    can_perform_hr_operations,
    can_promote_employee,
    can_terminate_employee,
    can_update_employee,
    can_view_employee,
    can_view_salary,
    can_view_team_members,
    filter_employee_data,
    get_allowed_fields_for_update,
    get_highest_role,
)
from app.core.security import TokenData, get_current_user
from app.core.topics import KafkaTopics
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
    InternalEmployeeCreate,
    OnboardingEmployeeCreate,
    Pagination,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    responses={404: {"description": "Employee not found"}},
)


# =============================================================================
# Internal Service-to-Service Endpoints (No Auth Required)
# =============================================================================


@router.post("/internal", response_model=EmployeePublic, status_code=201)
async def create_employee_internal(
    employee: InternalEmployeeCreate,
    session: SessionDep,
):
    """
    Create a new employee record (Internal service-to-service endpoint).

    This endpoint is for internal service calls (e.g., from User Management Service)
    and does not require authentication. It only requires basic user info and sets
    default values for position, department, hire date, etc.
    """
    logger.info(
        f"Creating new employee (internal): {employee.first_name} {employee.last_name} "
        f"(user_id: {employee.user_id})"
    )

    # Check if employee already exists with this email or user_id
    existing = session.exec(
        select(Employee).where(
            (Employee.email == employee.email) | (Employee.user_id == employee.user_id)
        )
    ).first()

    if existing:
        logger.info(f"Employee already exists: {existing.id} for {employee.email}")
        return existing

    db_employee = Employee(
        user_id=employee.user_id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.contact_number,
        position="Employee",
        job_title="Employee",
        department="General",
        date_of_hire=date.today(),
        joining_date=date.today(),
        contract_type="Full-Time",
        salary=Decimal("0.00"),
        status=EmployeeStatus.ACTIVE.value,
    )

    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    clear_cache_pattern("employee:*")
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeCreatedEvent(
        employee_id=db_employee.id,
        user_id=db_employee.user_id,
        email=db_employee.email,
        first_name=db_employee.first_name,
        last_name=db_employee.last_name,
        role=db_employee.role,
        job_title=db_employee.job_title,
        department=db_employee.department,
        employment_type=db_employee.employment_type,
        salary=float(db_employee.salary),
        salary_currency=db_employee.salary_currency,
        joining_date=db_employee.joining_date or db_employee.date_of_hire,
    )
    event = create_event(EventType.EMPLOYEE_CREATED, event_data)
    await publish_event(KafkaTopics.EMPLOYEE_CREATED, event)

    logger.info(f"Employee created successfully with ID: {db_employee.id}")
    return db_employee


@router.post("/internal/onboarding", response_model=EmployeeDetailed, status_code=201)
async def create_employee_from_onboarding(
    employee_data: OnboardingEmployeeCreate,
    session: SessionDep,
):
    """
    Create a full employee record from onboarding data.

    This endpoint is called by User Management Service during the signup flow
    with all the onboarding data collected during HR initiation and employee signup.
    """
    logger.info(
        f"Creating employee from onboarding: {employee_data.email} "
        f"(user_id: {employee_data.user_id})"
    )

    # Check if employee already exists
    existing = session.exec(
        select(Employee).where(
            (Employee.email == employee_data.email)
            | (Employee.user_id == employee_data.user_id)
        )
    ).first()

    if existing:
        logger.info(
            f"Employee already exists: {existing.id}, updating with onboarding data"
        )
        # Update existing record with onboarding data
        for field, value in employee_data.model_dump(exclude_unset=True).items():
            if value is not None and hasattr(existing, field):
                setattr(existing, field, value)
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # Determine initial status
    employment_type = employee_data.employment_type
    probation_months = employee_data.probation_months

    if employment_type == "permanent" and probation_months:
        initial_status = EmployeeStatus.ON_PROBATION.value
    else:
        initial_status = EmployeeStatus.ACTIVE.value

    db_employee = Employee(
        # User Management Link
        user_id=employee_data.user_id,
        # Basic Identity
        email=employee_data.email,
        first_name=employee_data.first_name,
        last_name=employee_data.last_name,
        phone=employee_data.phone,
        # Role and Status
        role=employee_data.role,
        status=initial_status,
        # Job Details
        job_title=employee_data.job_title,
        position=employee_data.job_title,
        department=employee_data.department,
        team=employee_data.team,
        manager_id=employee_data.manager_id,
        # Salary
        salary=Decimal(str(employee_data.salary)),
        salary_currency=employee_data.salary_currency,
        # Employment
        employment_type=employment_type,
        date_of_hire=employee_data.joining_date,
        joining_date=employee_data.joining_date,
        # Probation
        probation_months=probation_months,
        probation_end_date=employee_data.probation_end_date,
        probation_completed=False if probation_months else True,
        # Contract
        contract_start_date=employee_data.contract_start_date,
        contract_end_date=employee_data.contract_end_date,
        # Review Dates
        performance_review_date=employee_data.performance_review_date,
        salary_increment_date=employee_data.salary_increment_date,
        # Personal Details
        date_of_birth=employee_data.date_of_birth,
        gender=employee_data.gender,
        nationality=employee_data.nationality,
        # Address
        address_line_1=employee_data.address_line_1,
        address_line_2=employee_data.address_line_2,
        city=employee_data.city,
        state=employee_data.state,
        country=employee_data.country,
        postal_code=employee_data.postal_code,
        # Emergency Contact
        emergency_contact_name=employee_data.emergency_contact_name,
        emergency_contact_phone=employee_data.emergency_contact_phone,
        emergency_contact_relationship=employee_data.emergency_contact_relationship,
        # Bank Details
        bank_name=employee_data.bank_name,
        bank_account_number=employee_data.bank_account_number,
        bank_routing_number=employee_data.bank_routing_number,
        # Notes
        notes=employee_data.notes,
    )

    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    clear_cache_pattern("employee:*")
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeCreatedEvent(
        employee_id=db_employee.id,
        user_id=db_employee.user_id,
        email=db_employee.email,
        first_name=db_employee.first_name,
        last_name=db_employee.last_name,
        role=db_employee.role,
        job_title=db_employee.job_title,
        department=db_employee.department,
        team=db_employee.team,
        manager_id=db_employee.manager_id,
        employment_type=db_employee.employment_type,
        salary=float(db_employee.salary),
        salary_currency=db_employee.salary_currency,
        joining_date=db_employee.joining_date or db_employee.date_of_hire,
        probation_months=db_employee.probation_months,
        probation_end_date=db_employee.probation_end_date,
        contract_start_date=db_employee.contract_start_date,
        contract_end_date=db_employee.contract_end_date,
    )
    event = create_event(EventType.EMPLOYEE_CREATED, event_data)
    await publish_event(KafkaTopics.EMPLOYEE_CREATED, event)

    logger.info(f"Employee created from onboarding with ID: {db_employee.id}")
    return db_employee


@router.get("/internal/list", response_model=list[EmployeePublic])
async def list_employees_internal(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=1000)] = 1000,
):
    """
    List employees (Internal endpoint without auth).
    """
    logger.info(f"Listing employees (internal): offset={offset}, limit={limit}")

    cache_key = get_cache_key("employees:list:internal", f"{offset}:{limit}")
    cached = get_from_cache(cache_key)
    if cached:
        logger.info("Cache hit for employees list (internal)")
        return cached

    employees = session.exec(select(Employee).offset(offset).limit(limit)).all()
    employees_list = [emp.model_dump() for emp in employees]
    set_to_cache(cache_key, employees_list)

    logger.info(f"Retrieved {len(employees)} employee(s)")
    return employees_list


@router.get("/internal/by-email/{email}", response_model=EmployeePublic)
async def get_employee_by_email_internal(
    email: str,
    session: SessionDep,
):
    """
    Get employee by email (Internal endpoint).
    """
    logger.info(f"Looking up employee by email (internal): {email}")

    cache_key = get_cache_key("employee:email", email)
    cached = get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for email: {email}")
        return cached

    statement = select(Employee).where(Employee.email == email)
    employee = session.exec(statement).first()

    if not employee:
        logger.warning(f"Employee with email {email} not found")
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_dict = employee.model_dump()
    set_to_cache(cache_key, employee_dict)

    logger.info(
        f"Employee found: {employee.id} - {employee.first_name} {employee.last_name}"
    )
    return employee


@router.get("/internal/by-user/{user_id}", response_model=EmployeePublic)
async def get_employee_by_user_id_internal(
    user_id: int,
    session: SessionDep,
):
    """
    Get employee by user_id (Internal endpoint).
    """
    logger.info(f"Looking up employee by user_id (internal): {user_id}")

    cache_key = get_cache_key("employee:user", user_id)
    cached = get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for user_id: {user_id}")
        return cached

    statement = select(Employee).where(Employee.user_id == user_id)
    employee = session.exec(statement).first()

    if not employee:
        logger.warning(f"Employee with user_id {user_id} not found")
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_dict = employee.model_dump()
    set_to_cache(cache_key, employee_dict)

    logger.info(
        f"Employee found: {employee.id} - {employee.first_name} {employee.last_name}"
    )
    return employee


@router.get("/internal/{employee_id}", response_model=EmployeePublic)
async def get_employee_internal(
    employee_id: int,
    session: SessionDep,
):
    """
    Get employee by ID (Internal endpoint).
    """
    logger.info(f"Fetching employee (internal): {employee_id}")

    cache_key = get_cache_key("employee", employee_id)
    cached = get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for employee ID: {employee_id}")
        return cached

    employee = session.get(Employee, employee_id)
    if not employee:
        logger.warning(f"Employee with ID {employee_id} not found")
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_dict = employee.model_dump()
    set_to_cache(cache_key, employee_dict)

    logger.info(f"Employee found: {employee.first_name} {employee.last_name}")
    return employee


# =============================================================================
# Authenticated Endpoints (RBAC Protected)
# =============================================================================


@router.get("/me", response_model=EmployeeDetailed)
async def get_current_employee(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Get the current authenticated user's employee profile.
    """
    logger.info(f"Fetching current employee profile for user: {current_user.sub}")

    # Find employee by email or from user's claims
    email = current_user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in token",
        )

    employee = session.exec(select(Employee).where(Employee.email == email)).first()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found",
        )

    return employee


@router.patch("/me", response_model=EmployeeDetailed)
async def update_current_employee(
    employee_update: EmployeeUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Update the current authenticated user's employee profile.

    Users can only update their own personal information fields.
    """
    logger.info(f"Updating current employee profile for user: {current_user.sub}")

    email = current_user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in token",
        )

    employee = session.exec(select(Employee).where(Employee.email == email)).first()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found",
        )

    actor_role = get_highest_role(current_user.roles)
    allowed_fields = get_allowed_fields_for_update(actor_role, is_own_record=True)

    update_data = employee_update.model_dump(exclude_unset=True)
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not filtered_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update",
        )

    old_values = {k: getattr(employee, k) for k in filtered_data.keys()}

    for key, value in filtered_data.items():
        setattr(employee, key, value)
    employee.updated_at = datetime.utcnow()

    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee.id))
    delete_from_cache(get_cache_key("employee:email", employee.email))
    if employee.user_id:
        delete_from_cache(get_cache_key("employee:user", employee.user_id))
    clear_cache_pattern("employees:*")

    # Publish event
    event_data = EmployeeUpdatedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        updated_fields=filtered_data,
        previous_values=old_values,
    )
    event = create_event(
        EventType.EMPLOYEE_UPDATED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_UPDATED, event)

    logger.info(f"Employee profile updated: {employee.id}")
    return employee


@router.post("/", response_model=EmployeePublic, status_code=201)
async def create_employee(
    employee: EmployeeCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Create a new employee (Authenticated endpoint).

    Requires HR_Admin or HR_Manager role.
    """
    logger.info(
        f"Creating new employee: {employee.first_name} {employee.last_name} "
        f"by user: {current_user.sub}"
    )

    actor_role = get_highest_role(current_user.roles)

    if not can_perform_hr_operations(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin and HR Manager can create employees",
        )

    # Check for existing employee
    existing = session.exec(
        select(Employee).where(Employee.email == employee.email)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An employee with this email already exists",
        )

    db_employee = Employee(
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.phone,
        age=employee.age,
        date_of_birth=employee.date_of_birth,
        gender=employee.gender,
        address=employee.address,
        position=employee.position,
        job_title=employee.job_title,
        department=employee.department,
        team=employee.team,
        manager_id=employee.manager_id,
        date_of_hire=employee.date_of_hire,
        employment_type=employee.employment_type,
        contract_type=employee.contract_type,
        salary=employee.salary,
        salary_currency=employee.salary_currency,
        probation_months=employee.probation_months,
        contract_start_date=employee.contract_start_date,
        contract_end_date=employee.contract_end_date,
    )

    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    clear_cache_pattern("employee:*")
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeCreatedEvent(
        employee_id=db_employee.id,
        user_id=db_employee.user_id,
        email=db_employee.email,
        first_name=db_employee.first_name,
        last_name=db_employee.last_name,
        role=db_employee.role,
        job_title=db_employee.job_title,
        department=db_employee.department,
        employment_type=db_employee.employment_type,
        salary=float(db_employee.salary),
        salary_currency=db_employee.salary_currency,
        joining_date=db_employee.joining_date or db_employee.date_of_hire,
    )
    event = create_event(
        EventType.EMPLOYEE_CREATED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_CREATED, event)

    logger.info(f"Employee created successfully with ID: {db_employee.id}")
    return db_employee


@router.get("/", response_model=EmployeeListResponse)
async def list_employees(
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
    department: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    employment_type: Optional[str] = None,
):
    """
    List employees with pagination and filters.

    Results are filtered based on the user's role:
    - HR_Admin: See all employees
    - HR_Manager: See all employees except HR_Admin
    - manager: See all employees (directory view) + full access to team members
    - employee: See all employees (directory view, read-only)

    Note: For directory viewing, all roles can see employee listings.
    Detailed information and actions are controlled by other endpoints.
    """
    logger.info(f"Fetching employees by user: {current_user.sub}")

    actor_role = get_highest_role(current_user.roles)

    # Build query
    query = select(Employee)

    # Apply role-based filtering
    # For directory view, we allow most roles to see listings
    # Sensitive operations are controlled by update/delete endpoints
    if actor_role == "HR_Manager":
        # HR_Manager cannot see HR_Admin
        query = query.where(Employee.role != "HR_Admin")
    # HR_Admin sees all
    # manager and employee roles see all for directory purposes

    # Apply filters
    if department:
        query = query.where(Employee.department == department)
    if status_filter:
        query = query.where(Employee.status == status_filter)
    if employment_type:
        query = query.where(Employee.employment_type == employment_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # Apply pagination
    employees = session.exec(query.offset(offset).limit(limit)).all()

    # Calculate has_more for pagination
    has_more = (offset + len(employees)) < total

    return EmployeeListResponse(
        employees=[EmployeePublic.model_validate(emp) for emp in employees],
        pagination={
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": has_more,
        },
    )


@router.get("/summary", response_model=list[EmployeeSummary])
async def list_employees_summary(
    session: SessionDep,
    current_user: CurrentUserDep,
    department: Optional[str] = None,
):
    """
    Get a minimal employee summary list (for dropdowns, selectors).
    """
    actor_role = get_highest_role(current_user.roles)

    if not can_view_team_members(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view employee lists",
        )

    query = select(Employee)

    if department:
        query = query.where(Employee.department == department)

    employees = session.exec(query).all()

    return [EmployeeSummary.model_validate(emp) for emp in employees]


@router.get("/{employee_id}", response_model=EmployeeDetailed)
async def get_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Get employee by ID.

    Access is based on RBAC rules.
    """
    logger.info(f"Fetching employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)
    is_own = current_user.email == employee.email

    # Check view permission
    if not is_own and not can_view_employee(actor_role, employee.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this employee",
        )

    # Filter salary info if not allowed
    can_see_salary = can_view_salary(actor_role, employee.role, is_own)

    employee_data = employee.model_dump()
    filtered_data = filter_employee_data(
        employee_data, actor_role, is_own, include_salary=can_see_salary
    )

    return EmployeeDetailed.model_validate(filtered_data)


@router.patch("/{employee_id}", response_model=EmployeeDetailed)
async def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Update employee by ID.

    Access is based on RBAC rules.
    """
    logger.info(f"Updating employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)
    is_own = current_user.email == employee.email

    # Check update permission
    if not can_update_employee(actor_role, employee.role, is_own):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this employee",
        )

    # Get allowed fields
    allowed_fields = get_allowed_fields_for_update(actor_role, is_own)

    update_data = employee_update.model_dump(exclude_unset=True)
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not filtered_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update or no permission to update requested fields",
        )

    old_values = {k: getattr(employee, k) for k in filtered_data.keys()}

    for key, value in filtered_data.items():
        setattr(employee, key, value)
    employee.updated_at = datetime.utcnow()

    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    delete_from_cache(get_cache_key("employee:email", employee.email))
    if employee.user_id:
        delete_from_cache(get_cache_key("employee:user", employee.user_id))
    clear_cache_pattern("employees:*")

    # Publish event
    event_data = EmployeeUpdatedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        updated_fields=filtered_data,
        previous_values=old_values,
        updated_by=int(current_user.sub) if current_user.sub.isdigit() else None,
    )
    event = create_event(
        EventType.EMPLOYEE_UPDATED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_UPDATED, event)

    logger.info(f"Employee {employee_id} updated successfully")
    return employee


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    reason: Optional[str] = None,
):
    """
    Delete employee by ID.

    Only HR_Admin and HR_Manager can delete employees.
    """
    logger.info(f"Deleting employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_delete_employee(actor_role, employee.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this employee",
        )

    employee_email = employee.email
    employee_user_id = employee.user_id

    session.delete(employee)
    session.commit()

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    delete_from_cache(get_cache_key("employee:email", employee_email))
    if employee_user_id:
        delete_from_cache(get_cache_key("employee:user", employee_user_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeDeletedEvent(
        employee_id=employee_id,
        user_id=employee_user_id,
        email=employee_email,
        deleted_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
        reason=reason,
    )
    event = create_event(
        EventType.EMPLOYEE_DELETED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_DELETED, event)

    logger.info(f"Employee {employee_id} deleted successfully")
    return {"ok": True, "message": "Employee deleted successfully"}


# =============================================================================
# Status Management Endpoints
# =============================================================================


@router.post("/{employee_id}/suspend", response_model=EmployeePublic)
async def suspend_employee(
    employee_id: int,
    status_update: EmployeeStatusUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Suspend an employee.

    Only HR_Admin and HR_Manager can suspend employees.
    """
    logger.info(f"Suspending employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_perform_hr_operations(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin and HR Manager can suspend employees",
        )

    # HR_Manager cannot suspend HR_Admin or other HR_Managers
    if actor_role == "HR_Manager" and employee.role in ["HR_Admin", "HR_Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HR Manager cannot suspend HR Admin or other HR Managers",
        )

    employee.status = EmployeeStatus.SUSPENDED.value
    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeSuspendedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        suspended_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
        reason=status_update.reason,
    )
    event = create_event(
        EventType.EMPLOYEE_SUSPENDED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_UPDATED, event)

    logger.info(f"Employee {employee_id} suspended")
    return employee


@router.post("/{employee_id}/activate", response_model=EmployeePublic)
async def activate_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Activate a suspended employee.

    Only HR_Admin and HR_Manager can activate employees.
    """
    logger.info(f"Activating employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_perform_hr_operations(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin and HR Manager can activate employees",
        )

    employee.status = EmployeeStatus.ACTIVE.value
    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    logger.info(f"Employee {employee_id} activated")
    return employee


@router.post("/{employee_id}/terminate", response_model=EmployeePublic)
async def terminate_employee(
    employee_id: int,
    status_update: EmployeeStatusUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Terminate an employee.

    Only HR_Admin and HR_Manager can terminate employees.
    """
    logger.info(f"Terminating employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_terminate_employee(actor_role, employee.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to terminate this employee",
        )

    employee.status = EmployeeStatus.TERMINATED.value
    employee.terminated_at = datetime.utcnow()
    employee.updated_at = datetime.utcnow()
    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeTerminatedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        first_name=employee.first_name,
        last_name=employee.last_name,
        termination_date=date.today(),
        reason=status_update.reason,
        terminated_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
    )
    event = create_event(
        EventType.EMPLOYEE_TERMINATED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_TERMINATED, event)

    logger.info(f"Employee {employee_id} terminated")
    return employee


# =============================================================================
# Promotion and Transfer Endpoints
# =============================================================================


@router.post("/{employee_id}/promote", response_model=EmployeeDetailed)
async def promote_employee(
    employee_id: int,
    promotion: EmployeePromote,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Promote an employee to a new position.

    Only HR_Admin and HR_Manager can promote employees.
    """
    logger.info(f"Promoting employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_promote_employee(actor_role, employee.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to promote this employee",
        )

    old_position = employee.position
    old_job_title = employee.job_title
    old_salary = float(employee.salary)
    old_department = employee.department

    employee.position = promotion.new_position
    employee.job_title = promotion.new_job_title
    if promotion.new_salary:
        employee.salary = promotion.new_salary
    if promotion.new_department:
        employee.department = promotion.new_department
    employee.updated_at = datetime.utcnow()

    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeePromotedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        first_name=employee.first_name,
        last_name=employee.last_name,
        old_position=old_position,
        new_position=promotion.new_position,
        old_job_title=old_job_title,
        new_job_title=promotion.new_job_title,
        old_salary=old_salary,
        new_salary=float(employee.salary),
        old_department=old_department,
        new_department=employee.department,
        effective_date=promotion.effective_date,
        promoted_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
    )
    event = create_event(
        EventType.EMPLOYEE_PROMOTED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_PROMOTED, event)

    logger.info(f"Employee {employee_id} promoted to {promotion.new_position}")
    return employee


@router.post("/{employee_id}/transfer", response_model=EmployeeDetailed)
async def transfer_employee(
    employee_id: int,
    transfer: EmployeeTransfer,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Transfer an employee to a new department/team.

    Only HR_Admin and HR_Manager can transfer employees.
    """
    logger.info(f"Transferring employee {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_perform_hr_operations(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin and HR Manager can transfer employees",
        )

    old_department = employee.department
    old_team = employee.team
    old_manager_id = employee.manager_id

    employee.department = transfer.new_department
    if transfer.new_team:
        employee.team = transfer.new_team
    if transfer.new_manager_id:
        employee.manager_id = transfer.new_manager_id
    employee.updated_at = datetime.utcnow()

    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")
    clear_cache_pattern("dashboard:*")

    event_data = EmployeeTransferredEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        first_name=employee.first_name,
        last_name=employee.last_name,
        old_department=old_department,
        new_department=transfer.new_department,
        old_team=old_team,
        new_team=transfer.new_team,
        old_manager_id=old_manager_id,
        new_manager_id=transfer.new_manager_id,
        effective_date=transfer.effective_date,
        transferred_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
    )
    event = create_event(
        EventType.EMPLOYEE_TRANSFERRED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_TRANSFERRED, event)

    logger.info(f"Employee {employee_id} transferred to {transfer.new_department}")
    return employee


# =============================================================================
# Salary Endpoints
# =============================================================================


@router.patch("/{employee_id}/salary", response_model=EmployeeDetailed)
async def update_employee_salary(
    employee_id: int,
    salary_update: EmployeeSalaryUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Update employee salary.

    Only HR_Admin and HR_Manager can modify salary.
    """
    logger.info(
        f"Updating salary for employee {employee_id} by user: {current_user.sub}"
    )

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    actor_role = get_highest_role(current_user.roles)

    if not can_modify_salary(actor_role, employee.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this employee's salary",
        )

    old_salary = float(employee.salary)

    employee.salary = salary_update.salary
    if salary_update.salary_currency:
        employee.salary_currency = salary_update.salary_currency
    employee.updated_at = datetime.utcnow()

    session.add(employee)
    session.commit()
    session.refresh(employee)

    # Clear cache
    delete_from_cache(get_cache_key("employee", employee_id))
    clear_cache_pattern("employees:*")

    event_data = SalaryUpdatedEvent(
        employee_id=employee.id,
        user_id=employee.user_id,
        email=employee.email,
        old_salary=old_salary,
        new_salary=float(employee.salary),
        salary_currency=employee.salary_currency,
        effective_date=salary_update.effective_date or date.today(),
        reason=salary_update.reason,
        updated_by=int(current_user.sub) if current_user.sub.isdigit() else 0,
    )
    event = create_event(
        EventType.EMPLOYEE_SALARY_UPDATED,
        event_data,
        actor_user_id=current_user.sub,
        actor_role=actor_role,
    )
    await publish_event(KafkaTopics.EMPLOYEE_SALARY_UPDATED, event)

    logger.info(f"Salary updated for employee {employee_id}")
    return employee


# =============================================================================
# Dashboard Metrics Endpoint
# =============================================================================


@router.get("/dashboard/metrics", response_model=EmployeeDashboardMetrics)
async def get_dashboard_metrics(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Get dashboard metrics for employees.

    Only HR_Admin and HR_Manager can view full metrics.
    """
    actor_role = get_highest_role(current_user.roles)

    if not can_perform_hr_operations(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR Admin and HR Manager can view dashboard metrics",
        )

    # Try cache first
    cache_key = "dashboard:employee:metrics"
    cached = get_from_cache(cache_key)
    if cached:
        return EmployeeDashboardMetrics.model_validate(cached)

    # Calculate metrics
    today = date.today()
    month_start = today.replace(day=1)

    # Total counts
    total_employees = session.exec(select(func.count(Employee.id))).one()

    active_employees = session.exec(
        select(func.count(Employee.id)).where(
            Employee.status == EmployeeStatus.ACTIVE.value
        )
    ).one()

    on_probation = session.exec(
        select(func.count(Employee.id)).where(
            Employee.status == EmployeeStatus.ON_PROBATION.value
        )
    ).one()

    on_leave = session.exec(
        select(func.count(Employee.id)).where(
            Employee.status == EmployeeStatus.ON_LEAVE.value
        )
    ).one()

    suspended = session.exec(
        select(func.count(Employee.id)).where(
            Employee.status == EmployeeStatus.SUSPENDED.value
        )
    ).one()

    permanent_employees = session.exec(
        select(func.count(Employee.id)).where(
            Employee.employment_type == EmploymentType.PERMANENT.value
        )
    ).one()

    contract_employees = session.exec(
        select(func.count(Employee.id)).where(
            Employee.employment_type == EmploymentType.CONTRACT.value
        )
    ).one()

    # Employees by department
    dept_counts = session.exec(
        select(Employee.department, func.count(Employee.id))
        .where(Employee.department.isnot(None))
        .group_by(Employee.department)
    ).all()
    employees_by_department = {dept: count for dept, count in dept_counts if dept}

    # Employees by role
    role_counts = session.exec(
        select(Employee.role, func.count(Employee.id)).group_by(Employee.role)
    ).all()
    employees_by_role = {role: count for role, count in role_counts}

    # New hires this month
    new_hires_this_month = session.exec(
        select(func.count(Employee.id)).where(Employee.date_of_hire >= month_start)
    ).one()

    # Probation ending soon (within 7 days)
    from datetime import timedelta

    probation_deadline = today + timedelta(days=7)
    probation_ending_soon = session.exec(
        select(func.count(Employee.id)).where(
            Employee.probation_end_date.isnot(None),
            Employee.probation_end_date <= probation_deadline,
            Employee.probation_completed == False,
        )
    ).one()

    # Contracts expiring soon (within 30 days)
    contract_deadline = today + timedelta(days=30)
    contracts_expiring_soon = session.exec(
        select(func.count(Employee.id)).where(
            Employee.contract_end_date.isnot(None),
            Employee.contract_end_date <= contract_deadline,
            Employee.status != EmployeeStatus.TERMINATED.value,
        )
    ).one()

    # Birthdays this month
    birthdays_this_month = session.exec(
        select(func.count(Employee.id)).where(
            Employee.date_of_birth.isnot(None),
            func.month(Employee.date_of_birth) == today.month,
        )
    ).one()

    # Work anniversaries this month
    work_anniversaries = session.exec(
        select(func.count(Employee.id)).where(
            Employee.joining_date.isnot(None),
            func.month(Employee.joining_date) == today.month,
            Employee.joining_date < month_start,  # Not this year's joins
        )
    ).one()

    metrics = EmployeeDashboardMetrics(
        total_employees=total_employees,
        active_employees=active_employees,
        on_probation=on_probation,
        on_leave=on_leave,
        suspended=suspended,
        permanent_employees=permanent_employees,
        contract_employees=contract_employees,
        employees_by_department=employees_by_department,
        employees_by_role=employees_by_role,
        new_hires_this_month=new_hires_this_month,
        probation_ending_soon=probation_ending_soon,
        contracts_expiring_soon=contracts_expiring_soon,
        birthdays_this_month=birthdays_this_month,
        work_anniversaries_this_month=work_anniversaries,
    )

    # Cache for 5 minutes
    set_to_cache(cache_key, metrics.model_dump(), ttl=300)

    return metrics


# =============================================================================
# Auth Check Endpoint
# =============================================================================


@router.get("/auth/check")
async def protected_endpoint(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """
    A protected endpoint that requires authentication.
    """
    logger.info(f"Protected endpoint accessed by user: {current_user.sub}")

    return {
        "message": "You have access to this protected endpoint.",
        "username": current_user.username,
        "roles": current_user.roles,
    }
