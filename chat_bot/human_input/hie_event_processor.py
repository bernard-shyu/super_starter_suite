"""
Human Input Event (HIE) Processor

Handles CLIHumanResponseEvent processing for actual command execution with security validation.
Implements Proposal 1: HIE Command Execution Pipeline.
"""

import asyncio
import subprocess
from typing import Callable, Any, Dict, Optional
from datetime import datetime
from super_starter_suite.shared.config_manager import config_manager

# Import HIE event types from workflow
try:
    from super_starter_suite.workflow_porting.human_in_the_loop import CLIHumanResponseEvent
except ImportError:
    # Fallback for when workflow module is not available
    CLIHumanResponseEvent = None

# Get logger
logger = config_manager.get_logger("workflow.ui_event")


async def process_hie_input_event(event, workflow_config: Any, session_id: Optional[str] = None, ui_event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None) -> Optional[Dict]:
    """
    Process CLIHumanInputEvent interception - broadcast to frontend for approval.

    Implements the first part of Proposal 1: HIE Command Interception.
    Records HIE request in chat history for Proposal 2: Chat History Integration.

    Args:
        event: The CLIHumanInputEvent containing the command to be approved
        workflow_config: Workflow configuration object
        session_id: Session identifier for state tracking
        ui_event_callback: Optional callback for real-time UI updates

    Returns:
        Dict with HIE data to cause early return, or None to continue processing
    """
    command = getattr(event.data, 'command', 'Unknown command') if hasattr(event, 'data') else 'Unknown command'
    workflow_name = getattr(workflow_config, 'display_name', 'unknown')
    workflow_id = getattr(workflow_config, 'workflow_ID', None)

    logger.info(f"🚨 HIE INTERCEPTED: {command}")

    # 📝 PROPOSAL 2: Record HIE request in chat history BEFORE interception
    await _record_hie_in_chat_history(session_id, 'hie_request', command, workflow_name)

    # 🔒 SESSION PROTECTION: Capture current workflow state before HIE
    hie_session_snapshot = {
        'session_id': session_id,
        'workflow_id': workflow_id,
        'workflow_name': workflow_name,
        'hie_active': True,
        'hie_command': command,
        'timestamp': datetime.now().isoformat()
    }

    # Store session protection info for recovery
    if ui_event_callback:
        await ui_event_callback('hie_session_protection', hie_session_snapshot)
        logger.debug(f"[{workflow_name}] Session protection snapshot stored")

    # Broadcast HIE request immediately to prevent User Waiting
    try:
        # First, try to broadcast via UI event callback (preferred for HITL modals)
        if ui_event_callback:
            await ui_event_callback('hie_command_event', {
                "event_type": "cli_human_input",  # REQUIRED: Frontend expects this field
                "command": command,
                "workflow_id": workflow_id,
                "session_id": session_id
            })
            logger.info(f"[{workflow_name}] HIE streamed via UI callback")
    except Exception as broadcast_error:
        logger.warning(f"[{workflow_name}] HIE broadcast failed: {broadcast_error}")

    # Return HIE data to prevent workflow deadlock
    hie_data = {
        "HIE_intercepted": True,
        "HIE_type": "cli_input_request",
        "HIE_command": command,
        "workflow_id": workflow_id,
        "session_snapshot": hie_session_snapshot  # Include for recovery
    }
    return hie_data


async def process_hie_response_event(event, workflow_config: Any, ui_event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None) -> Optional[CLIHumanResponseEvent]:
    """
    Process CLIHumanResponseEvent and forward to workflow (DOES NOT EXECUTE COMMANDS).

    Implements the event routing layer of HIE workflow design:
    1. Receives user approval/rejection from frontend
    2. Validates security (prevents dangerous commands)
    3. Forwards decision back to workflow's handle_human_response() method
    4. COMMAND EXECUTION HAPPENS IN WORKFLOW BUSINESS LOGIC, NOT HERE

    Args:
        event: The frontend response event containing execute flag and command
        workflow_config: Workflow configuration object
        ui_event_callback: Optional callback for UI notifications

    Returns:
        CLIHumanResponseEvent: Event to forward to workflow's handle_human_response()
        None: If security rejection occurred
    """
    # Handle both direct attributes and data attribute (for MockCLIEvent compatibility)
    execute = getattr(event, 'execute', None)
    command = getattr(event, 'command', '')

    # If not found directly, check event.data (MockCLIEvent structure)
    if execute is None and hasattr(event, 'data'):
        execute = getattr(event.data, 'execute', False)
        command = getattr(event.data, 'command', command)

    workflow_name = getattr(workflow_config, 'display_name', 'unknown')
    logger.info(f"🚨 HIE USER RESPONSE PROCESSED: execute={execute}, command='{command[:50]}...'")

    # 📝 PROPOSAL 2: Record HIE response in chat history
    # Now that we have session context, pass the session ID directly
    # Note: session_id and workflow_id come from response data, not execution context
    action = 'approved' if execute else 'rejected'
    session_id_from_response = getattr(event, 'session_id', None) or getattr(event.data, 'session_id', None)
    if session_id_from_response:
        await _record_hie_in_chat_history(session_id_from_response, f'hie_{action}', command, workflow_name)
    else:
        logger.warning(f"[_record_hie_in_chat_history] No session ID available for HIE response recording")

    if execute and command:
        # ⚠️ SECURITY: Validate command BEFORE forwarding to workflow
        if not _validate_command_security(command):
            logger.warning(f"🚫 COMMAND REJECTED BY SECURITY: {command}")
            # Notify frontend of security rejection
            if ui_event_callback:
                security_data = {
                    'command': command,
                    'success': False,
                    'exit_code': -1,
                    'stdout': '',
                    'stderr': 'Command rejected by security policy',
                    'timestamp': datetime.now().isoformat()
                }
                await ui_event_callback('hie_execution_result', security_data)
            return None  # Don't forward to workflow - reject immediately

        # ✅ Create CLIHumanResponseEvent for workflow resumption
        logger.info(f"✅ COMMAND VALID: Creating CLIHumanResponseEvent for workflow resumption")

        # 🎯 Return CLIHumanResponseEvent - this will be used to start a new workflow execution
        # that begins directly in handle_human_response() method
        from super_starter_suite.workflow_porting.human_in_the_loop import CLIHumanResponseEvent

        workflow_response_event = CLIHumanResponseEvent(
            execute=True,
            command=command
        )

        return workflow_response_event

    else:
        logger.info(f"🚫 HIE COMMAND REJECTED BY USER: {command[:30]}...")

        # 🎯 Return rejection CLIHumanResponseEvent
        from super_starter_suite.workflow_porting.human_in_the_loop import CLIHumanResponseEvent

        workflow_response_event = CLIHumanResponseEvent(
            execute=False,
            command=command
        )

        return workflow_response_event


def _validate_command_security(command: str) -> bool:
    """
    Validate command security before execution.

    Basic security checks to prevent dangerous commands.

    Args:
        command: The command string to validate

    Returns:
        bool: True if command is safe to execute, False otherwise
    """
    import re

    # Convert to lowercase for case-insensitive checks
    cmd_lower = command.lower().strip()

    # Dangerous patterns to reject
    dangerous_patterns = [
        # System destruction
        r'\brm\s+-rf\s+/',  # rm -rf /
        r'\brm\s+-rf\s+\*',  # rm -rf *
        r'\brm\s+-rf\s+\.\.',  # rm -rf ..
        r'\brm\s+-rf\s+/.*',  # rm -rf /anything

        # System overwrite
        r'\bdd\s+if=.*of=/.*',  # dd if=source of=/dev/sda

        # Dangerous file operations
        r'\b>\s*/dev/',  # redirect to /dev/*
        r'\bchmod\s+777\s+/',  # chmod 777 /

        # Dangerous overrides
        r'\bchmod\s+777\s+.*',
        r'\bchown\s+root\s+.*',

        # Process killing
        r'\bkill\s+-9\s+-1',  # kill -9 -1 (kill all processes)

        # Service/systemd operations
        r'\bsystemctl\s+disable\s+.*',
        r'\bsystemctl\s+stop\s+.*',

        # System power
        r'\bhalt\b',
        r'\breboot\b',
        r'\bshutdown\b',
        r'\bpoweroff\b',
    ]

    # Check against dangerous patterns
    for pattern in dangerous_patterns:
        if re.search(pattern, cmd_lower):
            logger.warning(f"🚫 SECURITY VIOLATION: Command matches dangerous pattern '{pattern}': {command}")
            return False

    # Check for obviously dangerous commands
    dangerous_commands = [
        'mkfs', 'fdisk', 'parted', 'dd', 'wipefs',  # Disk operations
        'init', 'telinit', 'systemctl isolate',  # Init changes
        'passwd', 'usermod', 'userdel', 'groupmod',  # User management
        'modprobe', 'insmod', 'rmmod',  # Kernel modules
    ]

    # Check if command starts with dangerous command
    cmd_start = cmd_lower.split()[0] if cmd_lower.split() else ''
    for dangerous_cmd in dangerous_commands:
        if cmd_start.startswith(dangerous_cmd):
            logger.warning(f"🚫 SECURITY VIOLATION: Dangerous command '{dangerous_cmd}' detected: {command}")
            return False

    # Check for path traversal attempts
    if '..' in command and ('/' in command or '\\' in command):
        logger.warning(f"🚫 SECURITY VIOLATION: Path traversal detected: {command}")
        return False

    # Check command length (prevent extremely long commands)
    if len(command) > 1000:
        logger.warning(f"🚫 SECURITY VIOLATION: Command too long ({len(command)} chars)")
        return False

    # Allow safe commands (whitelist approach)
    safe_starts = [
        'ls', 'pwd', 'echo', 'cat', 'head', 'tail',
        'grep', 'find', 'wc', 'sort', 'uniq',
        'mkdir', 'touch', 'cp', 'mv', 'ln',
        'git', 'python', 'python3', 'node', 'npm',
        'docker', 'make', 'tar', 'zip', 'unzip',
    ]

    # Check if the command starts with a safe command
    if cmd_start in safe_starts:
        logger.debug(f"✅ SECURITY: Command passed validation: {command}")
        return True

    # Default: conservative approach - only allow explicitly safe commands
    # This can be relaxed based on deployment requirements
    logger.warning(f"⚠️ SECURITY: Command not in whitelist, rejecting: {command}")
    return False


async def _record_hie_in_chat_history(session_id: Optional[str], hie_type: str, command: str, workflow_name: str):
    """
    Record HIE events in chat history for STARTER_TOOLS compatibility (Proposal 2).

    Args:
        session_id: Session identifier (can be None for response events)
        hie_type: Type of HIE event ('hie_request', 'hie_approved', 'hie_rejected')
        command: The command string from the HIE event
        workflow_name: Display name of the workflow
    """
    try:
        from super_starter_suite.shared.dto import MessageRole, ChatMessageDTO, MessageMetadata, StructuredMessage

        # Create HIE chat message content based on event type
        if hie_type == 'hie_request':
            content = f"```\n{command}\n```\n🤖 **Workflow {workflow_name}** requires approval to execute this command."
        elif hie_type == 'hie_approved':
            content = f"```\n{command}\n```\n✅ **Approved** for execution."
        elif hie_type == 'hie_rejected':
            content = f"```\n{command}\n```\n❌ **Rejected** by user."
        else:
            content = f"HIE event: {hie_type} - {command}"

        # Create structured message for HIE event
        hie_message = StructuredMessage(
            content=content,
            metadata=MessageMetadata(),
            workflow_name=workflow_name
        )
        hie_message.metadata.hie_event = hie_type
        hie_message.metadata.command = command

        # Get chat manager and session info (need to access via current execution context)
        # This is a bit complex since we don't have direct access to chat_manager here
        # For response events, we'll try to access the current execution context

        from super_starter_suite.chat_bot.workflow_execution.execution_engine import _get_current_execution_context
        current_context = _get_current_execution_context()

        if current_context and hasattr(current_context, 'chat_manager') and hasattr(current_context, 'session'):
            from super_starter_suite.chat_bot.workflow_execution.execution_engine import save_message_to_session
            await save_message_to_session(current_context.chat_manager, current_context.session, hie_message)
            logger.debug(f"📝 Recorded HIE event in chat history: {hie_type}")
        else:
            # HIE recording should only happen within normal workflow execution context
            # If we can't access the context, skip recording entirely
            logger.warning(f"Could not record HIE event '{hie_type}' - no execution context available, skipping HIE history recording")

    except Exception as e:
        logger.warning(f"Failed to record HIE in chat history: {e}")
        # Don't raise - HIE processing should continue even if chat history recording fails
