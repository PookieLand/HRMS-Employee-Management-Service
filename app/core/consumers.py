"""
Kafka consumer handlers for Employee Management Service.

Handles events from other microservices, particularly:
- Onboarding events from user-management-service
- HR events for processing employee status changes

Each handler processes incoming events and creates corresponding
employee records or updates existing ones.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.cache import clear_cache_pattern
from app.core.config import settings
from app.core.database import engine
from app.core.events import (
    ContractStartedEvent,
    EmployeeCreatedEvent,
    EventType,
    ProbationStartedEvent,
    create_event,
)
from app.core.kafka import KafkaConsumer, publish_event
from app.core.logging import get_logger
from app.core.topics import KafkaTopics
from app.models.employee import Employee, EmployeeStatus, EmploymentType

logger = get_logger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        if isinstance(date_str, date):
            return date_str
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse date: {date_str}")
            return None


def handle_onboarding_initiated(event_data: dict[str, Any]):
    """
    Handle onboarding initiated event from user-management-service.

    At this stage, we just log the event. Employee record will be created
    when onboarding is completed (after signup step 2).
    """
    data = event_data.get("data", {})
    email = data.get("email", "unknown")
    role = data.get("role", "employee")
    job_title = data.get("job_title", "Employee")

    logger.info(f"Onboarding initiated for {email} - Role: {role}, Job: {job_title}")


def handle_onboarding_asgardeo_created(event_data: dict[str, Any]):
    """
    Handle Asgardeo user created event.

    At this stage, the user account has been created in Asgardeo.
    Employee record will be created in the next step.
    """
    data = event_data.get("data", {})
    email = data.get("email", "unknown")
    user_id = data.get("user_id")
    asgardeo_id = data.get("asgardeo_id")

    logger.info(
        f"Asgardeo user created for {email} - user_id: {user_id}, asgardeo_id: {asgardeo_id}"
    )


def handle_onboarding_employee_created(event_data: dict[str, Any]):
    """
    Handle employee created event from onboarding flow.

    This is triggered when the user-management-service calls our
    internal endpoint to create an employee record.
    """
    data = event_data.get("data", {})
    email = data.get("email", "unknown")
    employee_id = data.get("employee_id")
    user_id = data.get("user_id")

    logger.info(
        f"Employee record created via onboarding - email: {email}, "
        f"employee_id: {employee_id}, user_id: {user_id}"
    )


def handle_onboarding_completed(event_data: dict[str, Any]):
    """
    Handle onboarding completed event.

    This is the final event in the onboarding flow.
    We verify the employee record exists and update any missing fields.
    """
    data = event_data.get("data", {})
    email = data.get("email", "unknown")
    user_id = data.get("user_id")
    employee_id = data.get("employee_id")
    role = data.get("role", "employee")
    job_title = data.get("job_title", "Employee")
    employment_type = data.get("employment_type", "permanent")
    joining_date = parse_date(data.get("joining_date"))

    logger.info(
        f"Onboarding completed for {email} - "
        f"user_id: {user_id}, employee_id: {employee_id}"
    )

    # If employee_id is 0 or None, try to find and update by email
    if not employee_id:
        logger.warning(
            f"Employee ID not provided in onboarding completed event for {email}. "
            "Attempting to find by email..."
        )

        with Session(engine) as session:
            employee = session.exec(
                select(Employee).where(Employee.email == email)
            ).first()

            if employee:
                # Update any missing fields from onboarding data
                if user_id and not employee.user_id:
                    employee.user_id = user_id
                if role:
                    employee.role = role
                if job_title:
                    employee.job_title = job_title
                if employment_type:
                    employee.employment_type = employment_type
                if joining_date:
                    employee.joining_date = joining_date

                employee.updated_at = datetime.utcnow()
                session.add(employee)
                session.commit()

                logger.info(
                    f"Updated employee {employee.id} with onboarding completion data"
                )

                # Clear cache
                clear_cache_pattern("employee:*")
                clear_cache_pattern("employees:*")
                clear_cache_pattern("dashboard:*")
            else:
                logger.error(f"Employee not found for completed onboarding: {email}")


def handle_onboarding_failed(event_data: dict[str, Any]):
    """
    Handle onboarding failed event.

    Log the failure and clean up any partial employee records if needed.
    """
    data = event_data.get("data", {})
    email = data.get("email", "unknown")
    step = data.get("step", "unknown")
    error_message = data.get("error_message", "Unknown error")

    logger.error(f"Onboarding failed for {email} at step '{step}': {error_message}")

    # If failure occurred after employee record was created, we might need to clean up
    # For now, just log - cleanup should be handled by user-management-service


async def create_employee_from_onboarding(
    session: Session,
    data: dict[str, Any],
) -> Optional[Employee]:
    """
    Create a full employee record from onboarding data.

    This is called when receiving the full onboarding data payload.

    Args:
        session: Database session
        data: Onboarding data from user-management-service

    Returns:
        Created Employee or None if failed
    """
    try:
        email = data.get("email")
        if not email:
            logger.error("No email provided in onboarding data")
            return None

        # Check if employee already exists
        existing = session.exec(select(Employee).where(Employee.email == email)).first()

        if existing:
            logger.warning(f"Employee already exists for email: {email}")
            return existing

        # Determine initial status based on employment type
        employment_type = data.get("employment_type", "permanent")
        probation_months = data.get("probation_months")

        if employment_type == "permanent" and probation_months:
            initial_status = EmployeeStatus.ON_PROBATION.value
        else:
            initial_status = EmployeeStatus.ACTIVE.value

        # Parse dates
        joining_date = parse_date(data.get("joining_date")) or date.today()
        probation_end_date = parse_date(data.get("probation_end_date"))
        contract_start_date = parse_date(data.get("contract_start_date"))
        contract_end_date = parse_date(data.get("contract_end_date"))
        performance_review_date = parse_date(data.get("performance_review_date"))
        salary_increment_date = parse_date(data.get("salary_increment_date"))
        date_of_birth = parse_date(data.get("date_of_birth"))

        # Parse salary
        salary = data.get("salary", 0)
        if isinstance(salary, str):
            salary = float(salary)

        employee = Employee(
            # User Management Link
            user_id=data.get("user_id"),
            # Basic Identity
            email=email,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            phone=data.get("phone"),
            # Role and Status
            role=data.get("role", "employee"),
            status=initial_status,
            # Job Details
            job_title=data.get("job_title", "Employee"),
            position=data.get("job_title", "Employee"),
            department=data.get("department"),
            team=data.get("team"),
            manager_id=data.get("manager_id"),
            # Salary Information
            salary=Decimal(str(salary)),
            salary_currency=data.get("salary_currency", "USD"),
            # Employment Type and Dates
            employment_type=employment_type,
            date_of_hire=joining_date,
            joining_date=joining_date,
            # Probation
            probation_months=probation_months,
            probation_end_date=probation_end_date,
            probation_completed=False if probation_months else True,
            # Contract
            contract_type=data.get("contract_type", "Full-Time"),
            contract_start_date=contract_start_date,
            contract_end_date=contract_end_date,
            # Important Review Dates
            performance_review_date=performance_review_date,
            salary_increment_date=salary_increment_date,
            # Personal Details
            date_of_birth=date_of_birth,
            gender=data.get("gender"),
            nationality=data.get("nationality"),
            # Address
            address_line_1=data.get("address_line_1"),
            address_line_2=data.get("address_line_2"),
            city=data.get("city"),
            state=data.get("state"),
            country=data.get("country"),
            postal_code=data.get("postal_code"),
            # Emergency Contact
            emergency_contact_name=data.get("emergency_contact_name"),
            emergency_contact_phone=data.get("emergency_contact_phone"),
            emergency_contact_relationship=data.get("emergency_contact_relationship"),
            # Bank Details
            bank_name=data.get("bank_name"),
            bank_account_number=data.get("bank_account_number"),
            bank_routing_number=data.get("bank_routing_number"),
            # Notes
            notes=data.get("notes"),
        )

        session.add(employee)
        session.commit()
        session.refresh(employee)

        logger.info(f"Created employee {employee.id} from onboarding data: {email}")

        # Clear caches
        clear_cache_pattern("employee:*")
        clear_cache_pattern("employees:*")
        clear_cache_pattern("dashboard:*")

        # Publish employee created event
        event_data = EmployeeCreatedEvent(
            employee_id=employee.id,
            user_id=employee.user_id,
            email=employee.email,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=employee.role,
            job_title=employee.job_title,
            department=employee.department,
            team=employee.team,
            manager_id=employee.manager_id,
            employment_type=employee.employment_type,
            salary=float(employee.salary),
            salary_currency=employee.salary_currency,
            joining_date=employee.joining_date or employee.date_of_hire,
            probation_months=employee.probation_months,
            probation_end_date=employee.probation_end_date,
            contract_start_date=employee.contract_start_date,
            contract_end_date=employee.contract_end_date,
        )
        event = create_event(EventType.EMPLOYEE_CREATED, event_data)
        await publish_event(KafkaTopics.EMPLOYEE_CREATED, event)

        # If on probation, publish probation started event
        if initial_status == EmployeeStatus.ON_PROBATION.value and probation_end_date:
            probation_event = ProbationStartedEvent(
                employee_id=employee.id,
                user_id=employee.user_id,
                email=employee.email,
                first_name=employee.first_name,
                last_name=employee.last_name,
                probation_months=probation_months,
                probation_start_date=joining_date,
                probation_end_date=probation_end_date,
                manager_id=employee.manager_id,
            )
            event = create_event(EventType.EMPLOYEE_PROBATION_STARTED, probation_event)
            await publish_event(KafkaTopics.EMPLOYEE_PROBATION_STARTED, event)

        # If contract employee, publish contract started event
        if employment_type == "contract" and contract_start_date and contract_end_date:
            contract_event = ContractStartedEvent(
                employee_id=employee.id,
                user_id=employee.user_id,
                email=employee.email,
                first_name=employee.first_name,
                last_name=employee.last_name,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                contract_type=employee.contract_type,
            )
            event = create_event(EventType.EMPLOYEE_CONTRACT_STARTED, contract_event)
            await publish_event(KafkaTopics.EMPLOYEE_CONTRACT_STARTED, event)

        return employee

    except Exception as e:
        logger.error(f"Failed to create employee from onboarding: {e}")
        session.rollback()
        return None


def register_onboarding_handlers():
    """
    Register all handlers for onboarding events from user-management-service.

    Call this function during application startup before starting the consumer.
    """
    logger.info("Registering onboarding event handlers...")

    # Register handlers for each onboarding topic
    KafkaConsumer.register_handler(
        KafkaTopics.ONBOARDING_INITIATED,
        handle_onboarding_initiated,
    )

    KafkaConsumer.register_handler(
        KafkaTopics.ONBOARDING_ASGARDEO_USER_CREATED,
        handle_onboarding_asgardeo_created,
    )

    KafkaConsumer.register_handler(
        KafkaTopics.ONBOARDING_EMPLOYEE_CREATED,
        handle_onboarding_employee_created,
    )

    KafkaConsumer.register_handler(
        KafkaTopics.ONBOARDING_COMPLETED,
        handle_onboarding_completed,
    )

    KafkaConsumer.register_handler(
        KafkaTopics.ONBOARDING_FAILED,
        handle_onboarding_failed,
    )

    logger.info(
        f"Registered handlers for {len(KafkaTopics.onboarding_topics())} onboarding topics"
    )
