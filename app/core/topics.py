"""
Kafka Topic Definitions for Employee Management Service.

Topic naming follows the pattern: <domain>-<event-type>
This makes topics easily identifiable and organized by business domain.
"""


class KafkaTopics:
    """
    Central registry of all Kafka topics used by the Employee Management Service.
    Topics are named following the pattern: <domain>-<event-type>
    """

    # Employee Events - General employee lifecycle events
    EMPLOYEE_CREATED = "employee-created"
    EMPLOYEE_UPDATED = "employee-updated"
    EMPLOYEE_DELETED = "employee-deleted"
    EMPLOYEE_TERMINATED = "employee-terminated"
    EMPLOYEE_PROMOTED = "employee-promoted"
    EMPLOYEE_TRANSFERRED = "employee-transferred"

    # Onboarding Events - Listen for these from user-management-service
    ONBOARDING_INITIATED = "user-onboarding-initiated"
    ONBOARDING_ASGARDEO_USER_CREATED = "user-onboarding-asgardeo-created"
    ONBOARDING_EMPLOYEE_CREATED = "user-onboarding-employee-created"
    ONBOARDING_COMPLETED = "user-onboarding-completed"
    ONBOARDING_FAILED = "user-onboarding-failed"

    # Employment Status Events
    EMPLOYEE_PROBATION_STARTED = "employee-probation-started"
    EMPLOYEE_PROBATION_COMPLETED = "employee-probation-completed"
    EMPLOYEE_CONTRACT_STARTED = "employee-contract-started"
    EMPLOYEE_CONTRACT_RENEWED = "employee-contract-renewed"
    EMPLOYEE_CONTRACT_ENDED = "employee-contract-ended"

    # Salary Events - For payroll service integration
    EMPLOYEE_SALARY_UPDATED = "employee-salary-updated"
    EMPLOYEE_SALARY_INCREMENT = "employee-salary-increment"

    # Department/Team Events
    EMPLOYEE_DEPARTMENT_CHANGED = "employee-department-changed"
    EMPLOYEE_TEAM_CHANGED = "employee-team-changed"
    EMPLOYEE_MANAGER_CHANGED = "employee-manager-changed"

    # HR Events - Publish to these for notification service
    HR_PROBATION_ENDING = "hr-probation-ending"
    HR_CONTRACT_EXPIRING = "hr-contract-expiring"
    HR_PERFORMANCE_REVIEW_DUE = "hr-performance-review-due"
    HR_SALARY_INCREMENT_DUE = "hr-salary-increment-due"

    # Special Events - Celebrations and milestones
    SPECIAL_BIRTHDAY = "employee-special-birthday"
    SPECIAL_WORK_ANNIVERSARY = "employee-special-work-anniversary"

    # Audit Events - For audit service consumption
    AUDIT_EMPLOYEE_ACTION = "audit-employee-action"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Return list of all topic names."""
        return [
            value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("_")
        ]

    @classmethod
    def employee_topics(cls) -> list[str]:
        """Return list of employee-related topics."""
        return [
            cls.EMPLOYEE_CREATED,
            cls.EMPLOYEE_UPDATED,
            cls.EMPLOYEE_DELETED,
            cls.EMPLOYEE_TERMINATED,
            cls.EMPLOYEE_PROMOTED,
            cls.EMPLOYEE_TRANSFERRED,
        ]

    @classmethod
    def onboarding_topics(cls) -> list[str]:
        """Return list of onboarding-related topics to subscribe to."""
        return [
            cls.ONBOARDING_INITIATED,
            cls.ONBOARDING_ASGARDEO_USER_CREATED,
            cls.ONBOARDING_EMPLOYEE_CREATED,
            cls.ONBOARDING_COMPLETED,
            cls.ONBOARDING_FAILED,
        ]

    @classmethod
    def employment_status_topics(cls) -> list[str]:
        """Return list of employment status topics."""
        return [
            cls.EMPLOYEE_PROBATION_STARTED,
            cls.EMPLOYEE_PROBATION_COMPLETED,
            cls.EMPLOYEE_CONTRACT_STARTED,
            cls.EMPLOYEE_CONTRACT_RENEWED,
            cls.EMPLOYEE_CONTRACT_ENDED,
        ]

    @classmethod
    def hr_event_topics(cls) -> list[str]:
        """Return list of HR event topics."""
        return [
            cls.HR_PROBATION_ENDING,
            cls.HR_CONTRACT_EXPIRING,
            cls.HR_PERFORMANCE_REVIEW_DUE,
            cls.HR_SALARY_INCREMENT_DUE,
        ]

    @classmethod
    def special_event_topics(cls) -> list[str]:
        """Return list of special event topics."""
        return [
            cls.SPECIAL_BIRTHDAY,
            cls.SPECIAL_WORK_ANNIVERSARY,
        ]
