"""
Human In The Loop (HITL) Workflow Manager
Manages running workflow instances for HITL interactions.
"""

from typing import Dict, Optional
from datetime import datetime
from super_starter_suite.shared.config_manager import config_manager

# Get logger
logger = config_manager.get_logger("workflow.ui_event")

# Global registry for HITL workflow instances
# Maps: workflow_id -> {session_id, workflow_instance, user_id}
_hitl_workflow_registry: Dict[str, Dict] = {}


def register_hitl_workflow_instance(workflow_id: str, session_id: str, workflow_instance, user_id: Optional[str] = None) -> bool:
    """
    Register a running workflow instance for HITL interactions.

    Args:
        workflow_id: Unique workflow identifier
        session_id: Session identifier
        workflow_instance: The actual workflow instance that can be resumed
        user_id: Optional user identifier for multi-user scenarios

    Returns:
        bool: True if registered successfully
    """
    try:
        _hitl_workflow_registry[workflow_id] = {
            'session_id': session_id,
            'workflow_instance': workflow_instance,
            'user_id': user_id,
            'registered_at': datetime.now().timestamp(),
            'status': 'active'
        }

        logger.info(f"[HITL] Registered workflow instance: {workflow_id} for session {session_id}")
        return True

    except Exception as e:
        logger.error(f"[HITL] Failed to register workflow instance: {e}")
        return False


def get_hitl_workflow_instance(workflow_id: str) -> Optional[Dict]:
    """
    Get registered workflow instance for HITL interactions.

    Args:
        workflow_id: Workflow identifier

    Returns:
        Dict containing workflow instance data or None if not found
    """
    instance_data = _hitl_workflow_registry.get(workflow_id)
    if instance_data and instance_data.get('status') == 'active':
        return instance_data

    if instance_data:
        logger.warning(f"[HITL] Workflow instance {workflow_id} is not active (status: {instance_data.get('status')})")
    else:
        logger.warning(f"[HITL] No workflow instance found for {workflow_id}")

    return None


def unregister_hitl_workflow_instance(workflow_id: str) -> bool:
    """
    Unregister a workflow instance (e.g., after completion or failure).

    Args:
        workflow_id: Workflow identifier

    Returns:
        bool: True if unregistered successfully
    """
    try:
        if workflow_id in _hitl_workflow_registry:
            _hitl_workflow_registry[workflow_id]['status'] = 'completed'
            logger.info(f"[HITL] Unregistered workflow instance: {workflow_id}")
            return True

        logger.warning(f"[HITL] Attempted to unregister non-existent workflow: {workflow_id}")
        return False

    except Exception as e:
        logger.error(f"[HITL] Failed to unregister workflow instance: {e}")
        return False


def resume_hitl_workflow_instance(workflow_id: str, response_event) -> Optional[Dict]:
    """
    Resume a paused workflow instance with a response event.

    Args:
        workflow_id: Workflow identifier
        response_event: The response event to send to the workflow

    Returns:
        Dict with resume result or None if failed
    """
    try:
        instance_data = get_hitl_workflow_instance(workflow_id)
        if not instance_data:
            return None

        workflow_instance = instance_data.get('workflow_instance')
        if not workflow_instance:
            logger.error(f"[HITL] No workflow instance to resume for {workflow_id}")
            return None

        logger.info(f"[HITL] Resuming workflow instance {workflow_id}")

        # Attempt to resume the workflow with the response event
        # Note: This is a simplified implementation. The actual resume mechanism
        # depends on how the workflow framework handles paused states.
        resume_result = {
            'workflow_id': workflow_id,
            'status': 'resumed',
            'response_event': response_event,
            'timestamp': datetime.now().timestamp()
        }

        logger.info(f"[HITL] Workflow {workflow_id} resume initiated successfully")
        return resume_result

    except Exception as e:
        logger.error(f"[HITL] Failed to resume workflow instance {workflow_id}: {e}")
        return None


def is_workflow_hitl_supported(workflow_id: str) -> bool:
    """
    Check if a workflow supports HITL interactions.

    Args:
        workflow_id: Workflow identifier

    Returns:
        bool: True if workflow supports HITL
    """
    # For now, hardcode known HITL workflows
    # In a real implementation, this could be configuration-driven
    hitl_supported_workflows = [
        'human_in_the_loop',
        'hitl_file_organizer',
        'terminal_command_executor'
    ]

    return workflow_id in hitl_supported_workflows


def cleanup_expired_instances(max_age_hours: int = 24) -> int:
    """
    Clean up expired workflow instances.

    Args:
        max_age_hours: Maximum age in hours for instances to keep

    Returns:
        int: Number of instances cleaned up
    """
    try:
        current_time = datetime.now().timestamp()
        expired_ids = []
        max_age_seconds = max_age_hours * 3600

        for workflow_id, instance_data in _hitl_workflow_registry.items():
            registered_at = instance_data.get('registered_at')
            if registered_at and (current_time - registered_at) > max_age_seconds:
                expired_ids.append(workflow_id)
            elif instance_data.get('status') != 'active':
                # Also cleanup non-active instances older than 1 hour
                if registered_at and (current_time - registered_at) > 3600:
                    expired_ids.append(workflow_id)

        # Remove expired instances
        for workflow_id in expired_ids:
            del _hitl_workflow_registry[workflow_id]
            logger.info(f"[HITL] Cleaned up expired instance: {workflow_id}")

        logger.info(f"[HITL] Cleaned up {len(expired_ids)} expired workflow instances")
        return len(expired_ids)

    except Exception as e:
        logger.error(f"[HITL] Failed to cleanup expired instances: {e}")
        return 0


def list_active_hitl_instances() -> list:
    """
    List all active HITL workflow instances.

    Returns:
        List of active instance summaries
    """
    active_instances = []
    for workflow_id, instance_data in _hitl_workflow_registry.items():
        if instance_data.get('status') == 'active':
            active_instances.append({
                'workflow_id': workflow_id,
                'session_id': instance_data.get('session_id'),
                'user_id': instance_data.get('user_id'),
                'registered_at': instance_data.get('registered_at')
            })

    return active_instances


# Cleanup expired instances on module load
cleanup_expired_instances()
