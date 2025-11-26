from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.dependencies import CurrentUserDep, SessionDep
from app.core.logging import get_logger
from app.core.security import TokenData, get_current_user
from app.models.employee import Employee, EmployeeCreate, EmployeePublic, EmployeeUpdate

logger = get_logger(__name__)

# Create router with prefix and tags for better organization
router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    responses={404: {"description": "Employee not found"}},
)


@router.post("/", response_model=EmployeePublic, status_code=201)
async def create_employee(
    employee: EmployeeCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Create a new employee record.
    """
    logger.info(
        f"Creating new employee: {employee.first_name} {employee.last_name} "
        f"by user: {current_user.sub}"
    )

    # Convert input schema to ORM model
    db_employee = Employee.model_validate(employee)
    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    logger.info(f"Employee created successfully with ID: {db_employee.id}")
    return db_employee


@router.get("/", response_model=list[EmployeePublic])
async def read_employees(
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    """
    Retrieve a list of employees with pagination.

    - **offset**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100, max: 100)
    """
    logger.info(
        f"Fetching employees with offset={offset}, limit={limit} "
        f"by user: {current_user.sub}"
    )

    employees = session.exec(select(Employee).offset(offset).limit(limit)).all()

    logger.info(f"Retrieved {len(employees)} employee(s)")
    return list(employees)


@router.get("/{employee_id}", response_model=EmployeePublic)
async def read_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Retrieve a specific employee by ID.
    """
    logger.info(f"Fetching employee with ID: {employee_id} by user: {current_user.sub}")

    employee = session.get(Employee, employee_id)
    if not employee:
        logger.warning(f"Employee with ID {employee_id} not found")
        raise HTTPException(status_code=404, detail="Employee not found")

    logger.info(f"Employee found: {employee.first_name} {employee.last_name}")
    return employee


@router.patch("/{employee_id}", response_model=EmployeePublic)
async def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Update an existing employee record with partial data.
    """
    logger.info(
        f"Attempting to update employee with ID: {employee_id} "
        f"by user: {current_user.sub}"
    )

    employee_db = session.get(Employee, employee_id)
    if not employee_db:
        logger.warning(f"Employee with ID {employee_id} not found for update")
        raise HTTPException(status_code=404, detail="Employee not found")

    # Only update fields that were explicitly provided
    update_data = employee_update.model_dump(exclude_unset=True)
    logger.info(f"Updating employee {employee_id} with data: {update_data}")

    employee_db.sqlmodel_update(update_data)
    session.add(employee_db)
    session.commit()
    session.refresh(employee_db)

    logger.info(f"Employee with ID {employee_id} updated successfully")
    return employee_db


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Delete an employee record by ID.
    """
    logger.info(
        f"Attempting to delete employee with ID: {employee_id} "
        f"by user: {current_user.sub}"
    )

    employee = session.get(Employee, employee_id)
    if not employee:
        logger.warning(f"Employee with ID {employee_id} not found for deletion")
        raise HTTPException(status_code=404, detail="Employee not found")

    session.delete(employee)
    session.commit()

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
