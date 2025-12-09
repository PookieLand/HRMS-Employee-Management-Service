"""
Employee Management Service Core Module.

Exports core utilities and configurations.
"""

from app.core.cache import (
    RedisClient,
    clear_cache_pattern,
    delete_from_cache,
    get_cache_key,
    get_from_cache,
    set_to_cache,
)
from app.core.config import settings
from app.core.consumers import register_onboarding_handlers
from app.core.events import (
    EventEnvelope,
    EventMetadata,
    EventType,
    create_event,
)
from app.core.kafka import (
    KafkaConsumer,
    KafkaProducer,
    publish_event,
    publish_event_sync,
)
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
from app.core.topics import KafkaTopics

__all__ = [
    # Config
    "settings",
    # Cache
    "RedisClient",
    "get_cache_key",
    "get_from_cache",
    "set_to_cache",
    "delete_from_cache",
    "clear_cache_pattern",
    # Kafka
    "KafkaProducer",
    "KafkaConsumer",
    "KafkaTopics",
    "publish_event",
    "publish_event_sync",
    # Events
    "EventType",
    "EventMetadata",
    "EventEnvelope",
    "create_event",
    # RBAC
    "get_highest_role",
    "can_view_employee",
    "can_update_employee",
    "can_delete_employee",
    "can_view_salary",
    "can_modify_salary",
    "can_promote_employee",
    "can_terminate_employee",
    "can_view_team_members",
    "can_perform_hr_operations",
    "get_allowed_fields_for_update",
    "filter_employee_data",
    # Consumers
    "register_onboarding_handlers",
]
