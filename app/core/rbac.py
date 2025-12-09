"""
RBAC (Role-Based Access Control) utilities for Employee Management Service.

Defines role hierarchy and permission checking functions for:
- HR_Admin: Full access to all employee data and operations
- HR_Manager: Access to managers and employees, limited HR operations
- manager: Access to team members only
- employee: Access to own data only

Based on the RBAC rules defined in CLAUDE.md specification.
"""

from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Role hierarchy from highest to lowest authority
ROLE_HIERARCHY = {
    "HR_Admin": 4,
    "admin": 4,  # Alias for HR_Admin
    "HR_Manager": 3,
    "manager": 2,
    "employee": 1,
}

# Roles that can perform HR operations
HR_ROLES = {"HR_Admin", "admin", "HR_Manager"}

# Roles that can view salary information
SALARY_VIEW_ROLES = {"HR_Admin", "admin", "HR_Manager"}

# Roles that can modify salary information
SALARY_MODIFY_ROLES = {"HR_Admin", "admin", "HR_Manager"}

# Roles that can terminate employees
TERMINATE_ROLES = {"HR_Admin", "admin", "HR_Manager"}

# Roles that can promote employees
PROMOTE_ROLES = {"HR_Admin", "admin", "HR_Manager"}


def get_role_level(role: str) -> int:
    """
    Get the numeric level for a role.
    Higher number = higher authority.
    """
    return ROLE_HIERARCHY.get(role, 0)


def get_highest_role(roles: list[str]) -> str:
    """
    Get the highest authority role from a list of roles.

    Args:
        roles: List of role names

    Returns:
        The role with highest authority, or 'employee' if none found
    """
    if not roles:
        return "employee"

    highest_role = "employee"
    highest_level = 0

    for role in roles:
        level = get_role_level(role)
        if level > highest_level:
            highest_level = level
            highest_role = role

    # Normalize admin to HR_Admin
    if highest_role == "admin":
        highest_role = "HR_Admin"

    return highest_role


def can_view_employee(actor_role: str, target_employee_role: str) -> bool:
    """
    Check if actor can view target employee's data.

    Rules:
    - HR_Admin: Can view all employees
    - HR_Manager: Can view managers and employees (not other HR_Managers)
    - manager: Can view employees in their team
    - employee: Can view their own data only

    Args:
        actor_role: Role of the person requesting access
        target_employee_role: Role of the employee being accessed

    Returns:
        True if access is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can view everyone
    if actor_role == "HR_Admin":
        return True

    # HR_Manager cannot view other HR_Managers or HR_Admin
    if actor_role == "HR_Manager":
        return target_level < actor_level

    # manager can view employees only (and themselves)
    if actor_role == "manager":
        return target_level <= 1  # employee level

    # employee can only view themselves (checked separately)
    return False


def can_update_employee(
    actor_role: str,
    target_employee_role: str,
    is_own_record: bool = False,
) -> bool:
    """
    Check if actor can update target employee's data.

    Rules:
    - HR_Admin: Can update any user data
    - HR_Manager: Can update their own and lower roles (not other HR_Managers)
    - manager: Can update their own data, cannot update employee data
    - employee: Can only update their own data

    Args:
        actor_role: Role of the person requesting update
        target_employee_role: Role of the employee being updated
        is_own_record: Whether actor is updating their own record

    Returns:
        True if update is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    # Everyone can update their own record (with restrictions on fields)
    if is_own_record:
        return True

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can update anyone
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can update lower roles (not HR_Admin or other HR_Managers)
    if actor_role == "HR_Manager":
        return target_level < actor_level

    # manager cannot update employee data
    if actor_role == "manager":
        return False

    # employee cannot update others
    return False


def can_delete_employee(actor_role: str, target_employee_role: str) -> bool:
    """
    Check if actor can delete target employee.

    Rules:
    - HR_Admin: Can delete anyone
    - HR_Manager: Can delete managers and employees
    - Others: Cannot delete

    Args:
        actor_role: Role of the person requesting deletion
        target_employee_role: Role of the employee being deleted

    Returns:
        True if deletion is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    if actor_role not in HR_ROLES:
        return False

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can delete anyone
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can delete lower roles
    if actor_role == "HR_Manager":
        return target_level < actor_level

    return False


def can_view_salary(
    actor_role: str, target_employee_role: str, is_own: bool = False
) -> bool:
    """
    Check if actor can view salary information.

    Rules:
    - HR_Admin: Can see everyone's salary
    - HR_Manager: Can see salary of lower roles
    - manager: Cannot see employee salary (except own)
    - employee: Can see own salary slip only

    Args:
        actor_role: Role of the person requesting access
        target_employee_role: Role of the employee whose salary is being viewed
        is_own: Whether viewing own salary

    Returns:
        True if access is allowed
    """
    # Everyone can see their own salary
    if is_own:
        return True

    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    if actor_role not in SALARY_VIEW_ROLES:
        return False

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can see all
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can see lower roles
    if actor_role == "HR_Manager":
        return target_level < actor_level

    return False


def can_modify_salary(actor_role: str, target_employee_role: str) -> bool:
    """
    Check if actor can modify salary information.

    Rules:
    - HR_Admin: Can modify anyone's salary
    - HR_Manager: Can modify salary of lower roles
    - Others: Cannot modify salary

    Args:
        actor_role: Role of the person requesting modification
        target_employee_role: Role of the employee whose salary is being modified

    Returns:
        True if modification is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    if actor_role not in SALARY_MODIFY_ROLES:
        return False

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can modify all
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can modify lower roles
    if actor_role == "HR_Manager":
        return target_level < actor_level

    return False


def can_promote_employee(actor_role: str, target_employee_role: str) -> bool:
    """
    Check if actor can promote an employee.

    Rules:
    - HR_Admin: Can promote anyone
    - HR_Manager: Can promote managers and employees
    - Others: Cannot promote

    Args:
        actor_role: Role of the person promoting
        target_employee_role: Role of the employee being promoted

    Returns:
        True if promotion is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    if actor_role not in PROMOTE_ROLES:
        return False

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can promote anyone
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can promote lower roles
    if actor_role == "HR_Manager":
        return target_level < actor_level

    return False


def can_terminate_employee(actor_role: str, target_employee_role: str) -> bool:
    """
    Check if actor can terminate an employee.

    Rules:
    - HR_Admin: Can terminate anyone
    - HR_Manager: Can terminate managers and employees
    - Others: Cannot terminate

    Args:
        actor_role: Role of the person terminating
        target_employee_role: Role of the employee being terminated

    Returns:
        True if termination is allowed
    """
    actor_role = normalize_role(actor_role)
    target_employee_role = normalize_role(target_employee_role)

    if actor_role not in TERMINATE_ROLES:
        return False

    actor_level = get_role_level(actor_role)
    target_level = get_role_level(target_employee_role)

    # HR_Admin can terminate anyone
    if actor_role == "HR_Admin":
        return True

    # HR_Manager can terminate lower roles
    if actor_role == "HR_Manager":
        return target_level < actor_level

    return False


def can_view_team_members(actor_role: str) -> bool:
    """
    Check if actor can view team members list.

    Rules:
    - HR_Admin and HR_Manager: Can view all employees
    - manager: Can view their team members
    - employee: Cannot view team lists

    Args:
        actor_role: Role of the person requesting access

    Returns:
        True if access is allowed
    """
    actor_role = normalize_role(actor_role)
    return actor_role in {"HR_Admin", "HR_Manager", "manager"}


def can_perform_hr_operations(actor_role: str) -> bool:
    """
    Check if actor can perform HR operations (onboarding, bulk actions, etc.).

    Args:
        actor_role: Role of the person requesting access

    Returns:
        True if HR operations are allowed
    """
    actor_role = normalize_role(actor_role)
    return actor_role in HR_ROLES


def normalize_role(role: str) -> str:
    """
    Normalize role name (handle aliases).

    Args:
        role: Role name

    Returns:
        Normalized role name
    """
    if role == "admin":
        return "HR_Admin"
    return role


def get_allowed_fields_for_update(
    actor_role: str, is_own_record: bool = False
) -> set[str]:
    """
    Get the fields an actor is allowed to update.

    Args:
        actor_role: Role of the person updating
        is_own_record: Whether updating own record

    Returns:
        Set of allowed field names
    """
    actor_role = normalize_role(actor_role)

    # Fields everyone can update on their own record
    own_fields = {
        "phone",
        "address",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "country",
        "postal_code",
        "emergency_contact_name",
        "emergency_contact_phone",
        "emergency_contact_relationship",
        "bank_name",
        "bank_account_number",
        "bank_routing_number",
    }

    # HR fields that only HR roles can modify
    hr_fields = {
        "first_name",
        "last_name",
        "email",
        "role",
        "status",
        "job_title",
        "position",
        "department",
        "team",
        "manager_id",
        "salary",
        "salary_currency",
        "employment_type",
        "date_of_hire",
        "joining_date",
        "probation_months",
        "probation_end_date",
        "probation_completed",
        "contract_type",
        "contract_start_date",
        "contract_end_date",
        "performance_review_date",
        "salary_increment_date",
        "notes",
    }

    # Personal fields (can be updated by self or HR)
    personal_fields = {
        "date_of_birth",
        "age",
        "gender",
        "nationality",
    }

    if actor_role == "HR_Admin":
        return own_fields | hr_fields | personal_fields

    if actor_role == "HR_Manager":
        return own_fields | hr_fields | personal_fields

    if is_own_record:
        return own_fields | personal_fields

    return set()


def filter_employee_data(
    employee_data: dict,
    actor_role: str,
    is_own_record: bool = False,
    include_salary: bool = False,
) -> dict:
    """
    Filter employee data based on actor's role and permissions.

    Removes sensitive fields the actor shouldn't see.

    Args:
        employee_data: Full employee data dictionary
        actor_role: Role of the person viewing
        is_own_record: Whether viewing own record
        include_salary: Whether to include salary info (after permission check)

    Returns:
        Filtered employee data
    """
    actor_role = normalize_role(actor_role)

    # Sensitive fields to remove for non-HR roles
    sensitive_fields = {
        "bank_account_number",
        "bank_routing_number",
    }

    # Salary fields
    salary_fields = {"salary", "salary_currency"}

    filtered = employee_data.copy()

    # HR roles see everything
    if actor_role in {"HR_Admin", "HR_Manager"}:
        return filtered

    # Remove sensitive financial data for non-HR
    for field in sensitive_fields:
        filtered.pop(field, None)

    # Remove salary unless explicitly allowed or viewing own record
    if not include_salary and not is_own_record:
        for field in salary_fields:
            filtered.pop(field, None)

    return filtered
