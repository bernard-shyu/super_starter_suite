"""
Shared Session Utilities - Unified Session Management System

This module provides a comprehensive session management system with:
- Abstract BaseSessionHandler for consistent session lifecycle
- Concrete session classes (BasicUserSession, WorkflowSession, RagGenSession)
- Session registry for global management
- Factory functions for creating and accessing sessions
- CUDA cleanup utilities for GPU resource management
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime

from super_starter_suite.shared.config_manager import config_manager

logger = config_manager.get_logger("sess_manager")

# SESSION REGISTRY - Global mapping of session_id -> session handler
SESSION_REGISTRY: Dict[str, 'BaseSessionHandler'] = {}

class BaseSessionHandler(ABC):
    """Abstract base class for all session types with consistent lifecycle - USER AGNOSTIC"""

    def __init__(self, user_config, session_type: str, session_id: str):
        self.user_config = user_config
        self.session_type = session_type
        self.session_id = session_id
        # user_id determination moved to subclasses to handle different user_config types

    @abstractmethod
    def get_session_health_status(self) -> dict:
        """Return health metrics for monitoring - implemented by subclasses"""
        pass

    @abstractmethod
    def perform_session_health_check(self) -> bool:
        """Perform actual health validation - implemented by subclasses"""
        pass

    @abstractmethod
    def initialize_session_resources(self):
        """Initialize session-specific resources - implemented by subclasses"""
        pass

    @abstractmethod
    def dispose(self):
        """Clean up session resources and prepare for destruction - implemented by subclasses"""
        pass

    def matches(self, user_id: str, session_type: str, **kwargs) -> bool:
        """Check if this session handler matches the request requirements"""
        # Base implementation: check user_id and session_type
        # (user_id handled by BasicUserSession)
        current_user_id = getattr(self, 'user_id', None)
        return current_user_id == user_id and self.session_type == session_type

    def bind_context(self, **kwargs):
        """Bind additional context to an existing session (e.g., chat_session_id)"""
        # Base implementation: do nothing
        pass

    def initialize_session_llm(self):
        """Initialize LLM context for the session - called on creation and restoration"""
        # Default implementation: Initialize LLM for user config
        try:
            from .llama_utils import init_llm
            init_llm(self.user_config)
            logger.debug(f"[{self.session_type}] LLM initialized for session {self.session_id}")
        except Exception as e:
            logger.warning(f"[{self.session_type}] Failed to initialize LLM for session {self.session_id}: {str(e)}")

class BasicUserSession(BaseSessionHandler):
    """USER-AWARE BASE: Inherits from BaseSessionHandler and adds user config with dict-like access"""

    def __init__(self, user_config, session_type: str, session_id: str):
        # Call parent constructor first
        super().__init__(user_config, session_type, session_id)

        # USER AWARENESS: Provide dict-like interface for user_config and set user_id
        self.user_id = self._get_user_id_from_config()

    def _get_user_id_from_config(self):
        """Extract user_id from user_config (handles both UserConfig objects and dict-like access)"""
        # Handle both UserConfig objects (attribute access) and dict-like (get() method)
        if hasattr(self.user_config, 'get') and callable(getattr(self.user_config, 'get', None)):
            return self.user_config.get('user_id', 'anonymous')
        else:
            # Handle UserConfig objects
            return getattr(self.user_config, 'user_id', 'anonymous')

    def get_user_config_value(self, key: str, default=None):
        """Dict-like access to user config values for backward compatibility"""
        # Handle both UserConfig objects and dict-like objects
        if hasattr(self.user_config, 'get') and callable(getattr(self.user_config, 'get', None)):
            return self.user_config.get(key, default)
        else:
            # Handle UserConfig objects - map keys to attributes
            key_mapping = {
                'user_id': lambda: getattr(self.user_config, 'user_id', default),
                'my_rag_root': lambda: getattr(self.user_config, 'my_rag_root', default),
                'my_workflow': lambda: getattr(self.user_config, 'my_workflow', default),
                'settings': lambda: getattr(self.user_config, 'my_user_setting', default or {}),
                'chat_history_config': lambda: getattr(self.user_config, 'chat_history_config', default)
            }
            if key in key_mapping:
                return key_mapping[key]()
            return default

    def get_session_health_status(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "session_type": self.session_type,
            "user_config_valid": bool(self.user_config),
            "healthy": True
        }

    def perform_session_health_check(self) -> bool:
        try:
            uuid.UUID(self.session_id)
            assert self.user_config and self.user_id
            assert isinstance(self.session_type, str)
            return True
        except (ValueError, AssertionError):
            logger.warning(f"Health check failed for basic session {self.session_id}")
            return False

    def initialize_session_resources(self):
        if not self.user_config or not self.user_id:
            raise ValueError(f"Invalid user config for session {self.session_id}")
        logger.info(f"Basic user session {self.session_id} initialized for {self.user_id}")

    def dispose(self):
        logger.info(f"Basic user session {self.session_id} disposed")

    def refresh_config(self):
        """
        Refresh the user configuration from the config manager.
        Ensures that session-bound UserConfig objects stay in sync with saved settings.
        """
        from .config_manager import config_manager
        self.user_config = config_manager.get_user_config(self.user_id)


# =============================================================================
# SESSION FACTORY UTILITIES
# =============================================================================

def establish_session_handler(user_id: str, session_type: str, **kwargs) -> str:
    """Unified factory - creates appropriate handler based on session_type"""
    session_id = str(uuid.uuid4())
    user_config = config_manager.get_user_config(user_id)

    # Type determines class - direct string matching
    if session_type == "workflow_session":
        from super_starter_suite.chat_bot.session_manager import WorkflowSession
        # SRR COMPLIANT: Pass workflow_id at construction time
        workflow_id = kwargs.get('workflow_id')
        session = WorkflowSession(user_config, session_type, session_id, workflow_id)
        logger.debug(f"[SESSION_FACTORY] WorkflowSession created - session_id: {session_id}, workflow_id: {workflow_id}, type: {type(session)}")
    elif session_type == "rag_session":
        from super_starter_suite.rag_indexing.session_manager import RagGenSession
        session = RagGenSession(user_config, session_type, session_id)
    elif session_type == "history_session":
        from super_starter_suite.chat_bot.session_manager import HistorySession
        session = HistorySession(user_config, session_type, session_id)
    else:
        # Default to basic user session for "user_config" or any other type
        session = BasicUserSession(user_config, session_type, session_id)

    # Register session before initialization
    SESSION_REGISTRY[session_id] = session

    # Initialize session resources (may fail)
    try:
        session.initialize_session_resources()
    except Exception as init_error:
        # If initialization fails, remove from registry and re-raise
        logger.error(f"Session initialization failed for {session_type} {session_id}: {init_error}")
        del SESSION_REGISTRY[session_id]  # Clean up registry
        raise  # Re-raise to prevent returning invalid session_id

    return session_id


def get_or_establish_session(user_id: str, session_type: str,
                           request_state=None, **kwargs) -> tuple[str, BaseSessionHandler]:
    """FastAPI endpoint factory - integrates with request.state"""

    # Debug logging, showing existing session context
    existing_session_id = getattr(request_state, 'session_id', None) if request_state else None
    logger.debug(f"🔍 [DEBUG] get_or_establish_session called with user_id={user_id}, session_type={session_type}, kwargs={kwargs}, existing_session_id={existing_session_id}")

    # 1. ATTEMPT REUSE: Try to find an existing session in the registry by semantic match (Solution 1)
    # This correctly handles cases where request_state.session_id is None but the infrastructure exists.
    found_handler: Optional[BaseSessionHandler] = None
    for handler in list(SESSION_REGISTRY.values()):
        if handler.matches(user_id, session_type, **kwargs):
            found_handler = handler
            break

    if found_handler:
        # FOUND: Bind new context (e.g., chat_session_id) and return existing infrastructure
        found_handler.bind_context(**kwargs)
        sid = found_handler.session_id
        # Sync request state
        if request_state:
            setattr(request_state, 'session_id', sid)
            setattr(request_state, 'session_handler', found_handler)

        if sid in SESSION_REGISTRY:
            return sid, SESSION_REGISTRY[sid]
            
        return sid, found_handler

    # 2. ESTABLISH: No match found -> proceed with cleanup and creation
    logger.debug(f"[SESSION_ESTABLISH] No reusable session found for {user_id}/{session_type}. Cleaning up and creating fresh.")
    
    cleanup_user_session_handlers(user_id, session_type)

    # Create new session
    session_id = establish_session_handler(user_id, session_type, **kwargs)
    handler = SESSION_REGISTRY[session_id]

    # Store in request.state for future requests
    if request_state:
        setattr(request_state, 'session_id', session_id)
        setattr(request_state, 'session_handler', handler)

    return session_id, handler


def terminate_session_handler(session_id: str, reason: str = "user_request"):
    """Destroy session with inheritance-based cleanup"""
    if session_id in SESSION_REGISTRY:
        handler = SESSION_REGISTRY[session_id]
        handler.dispose()  # Use dispose() method for inheritance-based cleanup
        del SESSION_REGISTRY[session_id]


def cleanup_user_session_handlers(user_id: str, session_type: Optional[str] = None):
    """Cleanup all sessions for user, optionally filtered by session type"""
    to_terminate = []
    for sid, handler in SESSION_REGISTRY.items():
        if handler.user_id == user_id:
            if session_type is None or handler.session_type == session_type:
                to_terminate.append(sid)

    for sid in to_terminate:
        terminate_session_handler(sid, reason="cleanup_previous")


def enumerate_active_session_handlers(user_id: str, session_type: Optional[str] = None) -> List[str]:
    """Get active session IDs for user, optionally filtered by session type"""
    active = []
    for sid, handler in SESSION_REGISTRY.items():
        if handler.user_id == user_id:
            if session_type is None or handler.session_type == session_type:
                active.append(sid)
    return active


def validate_session_type(session_type: str) -> bool:
    """Validate session type is a recognized string"""
    valid_types = ["user_config", "workflow_session", "rag_session", "history_session"]
    return isinstance(session_type, str) and session_type in valid_types

def get_session_type_from_path(path: str) -> Optional[str]:
    """Derives session type string from endpoint path.

    Leverages semantic path conventions for session type determination:
    - /api/generate/* → "rag_session" (generation/cache operations)
    - /api/workflow/* → "workflow_session" (chat execution flows)
    - /api/system/* → "user_config" (settings/configuration endpoints)
    - /api/history/* → "history_session" (chat history operations)
    - /api/user_state/* → None (continuous identity management, no persistent session)

    Args:
        path: The FastAPI request URL path (e.g., "/api/generate/data_status")

    Returns:
        Session type string or None if no session needed

    Raises:
        ValueError: If path pattern is unrecognized
    """
    if path.startswith("/api/generate/"):
        return "rag_session"
    elif path.startswith("/api/workflow/"):
        return "workflow_session"
    elif path.startswith("/api/system/"):
        return "user_config"
    elif path.startswith("/api/history/"):
        return "history_session"
    elif path.startswith("/api/user_state/"):
        return None  # No persistent session needed for identity management
    else:
        # Unrecognized path pattern - should not happen in structured API
        raise ValueError(f"Unrecognized endpoint path pattern: {path}")


def create_session_from_endpoint_path(path: str, user_id: str) -> Optional[BaseSessionHandler]:
    """Create session for endpoint path if needed - Phase 1 unified factory"""
    session_type = get_session_type_from_path(path)
    if not session_type:
        return None

    # Use established unified factory
    session_id = establish_session_handler(user_id, session_type)
    return SESSION_REGISTRY.get(session_id)

# =============================================================================
# LEGACY COMPATIBILITY HELPERS
# =============================================================================

def find_session_for_user(user_id: str, session_type: Optional[str] = None) -> Optional[BaseSessionHandler]:
    """Find existing session handler for user"""
    for handler in SESSION_REGISTRY.values():
        if handler.user_id == user_id:
            if session_type is None or handler.session_type == session_type:
                return handler
    return None

def get_session_handler(session_id: str) -> Optional[BaseSessionHandler]:
    """Get session handler by session_id from registry"""
    return SESSION_REGISTRY.get(session_id)

# =============================================================================
# COMMON SANITY CHECKS FOR USER CONFIG AND SESSION VALIDATION
# =============================================================================

def validate_user_id(user_id: str) -> None:
    """Validate user_id and raise appropriate exceptions for invalid cases"""
    if not user_id:
        raise ValueError("User ID is required - no fallbacks allowed")

    if user_id == 'anonymous':
        raise ValueError("Anonymous user access forbidden - proper user identification required")

def validate_user_config(user_config: dict) -> dict:
    """Validate user configuration and return it, or raise exception"""
    if not user_config:
        raise ValueError("User configuration not found")

    # Check required attributes
    if not hasattr(user_config, 'user_id') or user_config.user_id is None:
        raise ValueError("User configuration is missing or has no user_id set")

    return user_config

def validate_session_type_string(session_type: str) -> str:
    """Validate session type is proper string value and return validated string

    Args:
        session_type: The session type to validate

    Returns:
        Validated session type string

    Raises:
        ValueError: if session_type is invalid
    """
    if not session_type:
        raise ValueError("Session type is required - no default fallbacks allowed")

    # Validate against known types
    valid_types = ["user_config", "workflow_session", "rag_session", "history_session"]
    if session_type not in valid_types:
        raise ValueError(f"Invalid session type '{session_type}'. Valid types: {valid_types}")

    return session_type

def validate_user_context_for_request(user_id: str, user_config_manager=None,
                                    validate_path_session_integrity: bool = True,
                                    session_type: str = None,
                                    workflow_context: str = None) -> tuple[dict, Optional[str]]:
    """Complete user context validation for FastAPI requests

    Args:
        user_id: The user ID to validate
        user_config_manager: Config manager instance (will use global if None)
        validate_path_session_integrity: Whether to validate that Session object exists and matches path expectations
        session_type: The session type string to validate
        workflow_context: Context for type validation (e.g., 'workflow', 'rag')

    Returns:
        tuple of (validated_user_config, validated_session_type)
    """

    # Validate user identification
    validate_user_id(user_id)

    # Load and validate user configuration
    user_config = config_manager.get_user_config(user_id)
    user_config = validate_user_config(user_config)

    # Validate session type if required
    validated_session_type = None
    if validate_path_session_integrity and session_type:
        validated_session_type = validate_session_type_string(session_type)

    return user_config, validated_session_type


# =============================================================================
# CENTRALIZED MANAGEMENT INFRASTRUCTURE (Phase 1)
# =============================================================================

@dataclass
class BoundSession:
    """Standardized session binding result for consistent request.state injection"""
    session_id: str
    session_handler: BaseSessionHandler

    def apply_to_request_state(self, request):
        """Apply session data to FastAPI request state"""
        from fastapi import Request
        request.state.session_id = self.session_id
        request.state.session_handler = self.session_handler

@dataclass
class ValidationResult:
    """Standardized validation result"""
    is_valid: bool
    error_code: int = 400
    message: str = "Validation failed"



class SessionBinder:
    """Centralized session management - SINGLE SOURCE for session binding"""

    @staticmethod
    def bind_session(request, session_type: str, context: Optional[Dict[str, Any]] = None) -> BoundSession:
        """Unified session binding algorithm with optional context for specialized sessions"""

        # Get user_id from request state (should be set by UserContextManager)
        user_id = getattr(request.state, 'user_id', None)
        logger.debug(f"[SessionBinder] session_type={session_type}, context={context}, user_id = {user_id}")
        if not user_id:
            raise ValueError("User ID must be available in request state")

        # Validate session type
        session_type = validate_session_type_string(session_type)

        # Use existing get_or_establish_session unified factory
        session_id, session_handler = get_or_establish_session(
            user_id=user_id,
            session_type=session_type,
            request_state=request.state,
            **(context or {})  # Pass context to establish additional session properties
        )

        # Initialize LLM for user config
        session_handler.initialize_session_llm()

        return BoundSession(session_id=session_id, session_handler=session_handler)


class RequestValidator:
    """Centralized request validation - SINGLE SOURCE for all validation logic"""

    @staticmethod
    def validate_user_context(request) -> ValidationResult:
        """Validate user context in request"""
        from fastapi import Request

        try:
            # Check user_id presence
            user_id = getattr(request.state, 'user_id', None)
            if not user_id:
                return ValidationResult(False, 400, "User ID is required")

            validate_user_id(user_id)

            # Check user_config presence
            user_config = getattr(request.state, 'user_config', None)
            if not user_config:
                return ValidationResult(False, 400, "User configuration is required")

            validate_user_config(user_config)

            return ValidationResult(True, 200, "User context valid")

        except ValueError as ve:
            return ValidationResult(False, 400, str(ve))
        except Exception as e:
            logger.error(f"RequestValidator user context error: {e}")
            return ValidationResult(False, 500, "Internal validation error")

    @staticmethod
    def validate_session_context(request, session_type: str) -> ValidationResult:
        """Validate session context in request"""
        try:
            # Check session_id and handler presence
            session_id = getattr(request.state, 'session_id', None)
            session_handler = getattr(request.state, 'session_handler', None)

            if not session_id:
                return ValidationResult(False, 400, "Session ID is required")
            if not session_handler:
                return ValidationResult(False, 400, "Session handler is required")

            # Validate session type match
            if session_handler.session_type != session_type:
                return ValidationResult(
                    False, 400,
                    f"Session type mismatch: expected {session_type}, got {session_handler.session_type}"
                )

            # Validate user_id match
            user_id = getattr(request.state, 'user_id', None)
            if user_id and session_handler.user_id != user_id:
                return ValidationResult(
                    False, 400,
                    f"Session user mismatch: request={user_id}, session={session_handler.user_id}"
                )

            return ValidationResult(True, 200, "Session context valid")

        except Exception as e:
            logger.error(f"RequestValidator session context error: {e}")
            return ValidationResult(False, 500, "Session validation error")

    @staticmethod
    def validate_path_session_integrity(path: str, request) -> ValidationResult:
        """Validate that path and session type align"""
        try:
            expected_type = get_session_type_from_path(path)

            if expected_type is None:
                # No session required for this path
                return ValidationResult(True, 200, "Path requires no session")

            # Get actual session type from handler
            session_handler = getattr(request.state, 'session_handler', None)
            if not session_handler:
                return ValidationResult(False, 400, "Session required but not found")

            actual_type = session_handler.session_type
            if actual_type != expected_type:
                return ValidationResult(
                    False, 400,
                    f"Path/session type mismatch: path expects {expected_type}, has {actual_type}"
                )

            return ValidationResult(True, 200, "Path-session integrity valid")

        except ValueError as ve:
            return ValidationResult(False, 400, f"Path recognition error: {ve}")
        except Exception as e:
            logger.error(f"RequestValidator path integrity error: {e}")
            return ValidationResult(False, 500, "Path validation error")
