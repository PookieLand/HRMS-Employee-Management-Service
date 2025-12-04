from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

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
    EmployeeUpdatedEvent,
    EventEnvelope,
    EventMetadata,
    EventType,
)
from app.core.kafka import publish_event
from app.core.logging import get_logger
from app.core.security import TokenData, get_current_user
from app.models.employee import (
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_DEPARTMENT,
    DEFAULT_POSITION,
    DEFAULT_SALARY,
    Employee,
    EmployeeCreate,
    EmployeePublic,
    EmployeeUpdate,
    InternalEmployeeCreate,
)

logger = get_logger(__name__)

# Create router with prefix and tags for better organization
router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    responses={404: {"description": "Employee not found"}},
)


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

    # Create Employee with defaults for missing fields
    db_employee = Employee(
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        contact_number=employee.contact_number,
        position=DEFAULT_POSITION,
        department=DEFAULT_DEPARTMENT,
        date_of_hire=date.today(),
        contract_type=DEFAULT_CONTRACT_TYPE,
        salary=DEFAULT_SALARY,
    )

    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    clear_cache_pattern("employee:*")
    clear_cache_pattern("employees:*")

    event_data = EmployeeCreatedEvent(
        employee_id=db_employee.id,
        first_name=db_employee.first_name,
        last_name=db_employee.last_name,
        email=db_employee.email,
        contact_number=db_employee.contact_number,
        position=db_employee.position,
        department=db_employee.department,
        date_of_hire=db_employee.date_of_hire.isoformat(),
    )
    event = EventEnvelope(
        event_type=EventType.EMPLOYEE_CREATED,
        data=event_data.model_dump(),
        metadata=EventMetadata(),
    )
    await publish_event("employee-events", event)

    logger.info(f"Employee created successfully with ID: {db_employee.id}")
    return db_employee


@router.get("/internal/list", response_model=list[EmployeePublic])
async def list_employees_internal(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=1000)] = 1000,
):
    logger.info(f"Listing employees (internal): offset={offset}, limit={limit}")

    cache_key = get_cache_key("employees:list", f"{offset}:{limit}")
    cached = get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for employees list")
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


@router.get("/internal/{employee_id}", response_model=EmployeePublic)
async def get_employee_internal(
    employee_id: int,
    session: SessionDep,
):
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


@router.post("/", response_model=EmployeePublic, status_code=201)
async def create_employee(
    employee: EmployeeCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    logger.info(
        f"Creating new employee: {employee.first_name} {employee.last_name} "
        f"by user: {current_user.sub}"
    )

    db_employee = Employee.model_validate(employee)
    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    clear_cache_pattern("employee:*")
    clear_cache_pattern("employees:*")

    event_data = EmployeeCreatedEvent(
        employee_id=db_employee.id,
        first_name=db_employee.first_name,
        last_name=db_employee.last_name,
        email=db_employee.email,
        contact_number=db_employee.contact_number,
        position=db_employee.position,
        department=db_employee.department,
        date_of_hire=db_employee.date_of_hire.isoformat(),
    )
    event = EventEnvelope(
        event_type=EventType.EMPLOYEE_CREATED,
        data=event_data.model_dump(),
        metadata=EventMetadata(user_id=current_user.sub),
    )
    await publish_event("employee-events", event)

    logger.info(f"Employee created successfully with ID: {db_employee.id}")
    return db_employee


@router.get("/", response_model=list[EmployeePublic])
async def read_employees(
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    logger.info(
        f"Fetching employees with offset={offset}, limit={limit} "
        f"by user: {current_user.sub}"
    )

    cache_key = get_cache_key("employees:list", f"{offset}:{limit}")
    cached = get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for employees list")
        return cached

    employees = session.exec(select(Employee).offset(offset).limit(limit)).all()
    employees_list = [emp.model_dump() for emp in employees]
    set_to_cache(cache_key, employees_list)

    logger.info(f"Retrieved {len(employees)} employee(s)")
    return employees_list


@router.get("/{employee_id}", response_model=EmployeePublic)
async def read_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    logger.info(f"Fetching employee with ID: {employee_id} by user: {current_user.sub}")

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


@router.patch("/{employee_id}", response_model=EmployeePublic)
async def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    logger.info(
        f"Attempting to update employee with ID: {employee_id} "
        f"by user: {current_user.sub}"
    )

    employee_db = session.get(Employee, employee_id)
    if not employee_db:
        logger.warning(f"Employee with ID {employee_id} not found for update")
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = employee_update.model_dump(exclude_unset=True)
    logger.info(f"Updating employee {employee_id} with data: {update_data}")

    employee_db.sqlmodel_update(update_data)
    session.add(employee_db)
    session.commit()
    session.refresh(employee_db)

    delete_from_cache(get_cache_key("employee", employee_id))
    if employee_db.email:
        delete_from_cache(get_cache_key("employee:email", employee_db.email))
    clear_cache_pattern("employees:*")

    event_data = EmployeeUpdatedEvent(
        employee_id=employee_id, updated_fields=update_data
    )
    event = EventEnvelope(
        event_type=EventType.EMPLOYEE_UPDATED,
        data=event_data.model_dump(),
        metadata=EventMetadata(user_id=current_user.sub),
    )
    await publish_event("employee-events", event)

    logger.info(f"Employee with ID {employee_id} updated successfully")
    return employee_db


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    logger.info(
        f"Attempting to delete employee with ID: {employee_id} "
        f"by user: {current_user.sub}"
    )

    employee = session.get(Employee, employee_id)
    if not employee:
        logger.warning(f"Employee with ID {employee_id} not found for deletion")
        raise HTTPException(status_code=404, detail="Employee not found")

    employee_email = employee.email

    session.delete(employee)
    session.commit()

    delete_from_cache(get_cache_key("employee", employee_id))
    if employee_email:
        delete_from_cache(get_cache_key("employee:email", employee_email))
    clear_cache_pattern("employees:*")

    event_data = EmployeeDeletedEvent(employee_id=employee_id, email=employee_email)
    event = EventEnvelope(
        event_type=EventType.EMPLOYEE_DELETED,
        data=event_data.model_dump(),
        metadata=EventMetadata(user_id=current_user.sub),
    )
    await publish_event("employee-events", event)

    logger.info(f"Employee with ID {employee_id} deleted successfully")
    return {"ok": True}


@router.get("/auth/check")
async def protected_endpoint(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """
    A protected endpoint that requires authentication.

    **Authentication Required**: Bearer token in Authorization header

    Returns:
    - Confirmation of access
    - User ID from the token
    """
    logger.info(f"Protected endpoint accessed by user: {current_user.sub}")

    return {
        "message": "You have access to this protected endpoint.",
        "username": current_user.username,
    }
