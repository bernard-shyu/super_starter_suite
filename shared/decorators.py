from functools import wraps
from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
from .config_manager import config_manager
from .llama_utils import init_llm

# Initialize logger
logger = config_manager.get_logger("endpoints")


def bind_user_context(validate_path_session_integrity: bool = False):
    """
    User context validation decorator - validates middleware-set user context.

    User context is set by middleware - this decorator only validates it exists.
    Follows architecture: middleware sets context, decorators validate and bind sessions.

    Args:
        validate_path_session_integrity: Whether to validate session domain matches path

    Returns:
        Request with validated user context (set by middleware)
    """
    def decorator(func):
        logger.info(f"[DECORATOR] bind_user_context registered for {func.__name__}")
        @wraps(func)
        async def context_bound_function(request: Request, *args, **kwargs):
            try:
                # VALIDATION ONLY: User context should be set by middleware
                from .session_utils import RequestValidator
                user_context_validation = RequestValidator.validate_user_context(request)
                if not user_context_validation.is_valid:
                    logger.error(f"User context validation failed: {user_context_validation.message}")
                    raise HTTPException(
                        status_code=user_context_validation.error_code,
                        detail=user_context_validation.message
                    )

                # Path-session integrity validation (optional)
                if validate_path_session_integrity:
                    path_validation = RequestValidator.validate_path_session_integrity(request.url.path, request)
                    if not path_validation.is_valid:
                        logger.warning(f"Path-session integrity failed: {path_validation.message}")
                        # For user context endpoints, we allow non-session endpoints so don't fail

                return await func(request, *args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                logger.error(f"EXCEPTION in bind_user_context decorator: {str(e)}", exc_info=True)
                # Re-raise the exception to not hide it
                raise

        return context_bound_function

    return decorator





def bind_workflow_session_dynamic():
    """
    Dynamic workflow session binding decorator - validates user context and binds workflow session.

    NOTE: This decorator is incompatible with FastAPI's route processing and has been replaced
    by direct function calls to ensure_workflow_session() in workflow endpoints.

    User context is set by middleware - this decorator validates, extracts workflow_id, and binds session.
    Follows architecture: middleware sets context, decorators validate and bind.
    """
    def decorator(func):
        @wraps(func)
        async def context_bound_function(request: Request, workflow_id: str, *args, **kwargs):

            # User context validation (middleware sets UserConfig object)
            from .session_utils import RequestValidator, SessionBinder
            user_context_validation = RequestValidator.validate_user_context(request)
            if not user_context_validation.is_valid:
                logger.error(f"User context validation failed: {user_context_validation.message}")
                raise HTTPException(
                    status_code=user_context_validation.error_code,
                    detail=user_context_validation.message
                )

            # Use workflow_id passed from endpoint (FastAPI resolves path parameters)

            # Session binding (uses user_config from middleware via BasicUserSession inheritance)
            bound_session = SessionBinder.bind_session(request, "workflow_session", {"workflow_id": workflow_id})

            # Apply session data to request state
            bound_session.apply_to_request_state(request)
            logger.debug(f"[DECORATOR] Applied to request.state: session_handler={getattr(request.state, 'session_handler', 'MISSING')}")

            return await func(request, workflow_id, *args, **kwargs)

        return context_bound_function

    return decorator

# ============================================================================
# COMMON SESSION BINDING UTILITY (Shared by all session-based decorators)
# ============================================================================

async def _restore_session_context(request: Request, session_id: str, session_type: str):
    """
    COMMON CONTEXT RESTORATION: Shared by all session-based decorators

    Restores complete request.state context from session_id:
    - request.state.user_config
    - request.state.user_id
    - request.state.session_handler
    - request.state.session_id

    Args:
        request: FastAPI request object
        session_id: Session ID from router parameter
        session_type: Expected session type ("workflow_session", "rag_session", "history_session")

    Returns:
        bool: True if context restored from existing session, False if new session needed
    """
    from .session_utils import RequestValidator, SessionBinder, SESSION_REGISTRY

    try:
        # ✅ STEP 1: Try to restore complete context from existing session
        if session_id in SESSION_REGISTRY:
            session_handler = SESSION_REGISTRY[session_id]

            # Validate session type and ownership
            if session_handler.session_type == session_type:
                # For existing sessions, get user_id from handler (all concrete handlers have it)
                handler_user_id = getattr(session_handler, 'user_id', None)
                current_user_id = getattr(request.state, 'user_id', None)

                # Allow if handler has user_id and matches current user (or no current user set)
                if handler_user_id and (not current_user_id or handler_user_id == current_user_id):

                    # 🔄 REFRESH SESSION CONTEXT from existing session
                    # 1. Refresh UserConfig to catch any settings changes since last binding
                    if hasattr(session_handler, 'refresh_config'):
                        session_handler.refresh_config()

                    # 2. Re-initialize LLM for the session (llama_utils safely handles caching/changes)
                    if hasattr(session_handler, 'initialize_session_llm'):
                        session_handler.initialize_session_llm()

                    # 3. Apply refreshed context to request state
                    request.state.user_config = getattr(session_handler, 'user_config', None)
                    request.state.user_id = handler_user_id
                    request.state.session_handler = session_handler
                    request.state.session_id = session_id

                    return True  # Context restored
            else:
                pass

        # ❌ STEP 2: New session - ensure user context exists
        if not hasattr(request.state, 'user_config') or not hasattr(request.state, 'user_id'):
            validation = RequestValidator.validate_user_context(request)
            if not validation.is_valid:
                logger.error(f"Session context validation failed: {validation.message}")
                raise HTTPException(validation.error_code, validation.message)

        # Set session_id for binding
        request.state.session_id = session_id

        # Perform binding for new session
        bound_session = SessionBinder.bind_session(request, session_type, {})
        bound_session.apply_to_request_state(request)

        return False  # New session created
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Context restoration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Context restoration failed: {str(e)}")


# ============================================================================
# SESSION-BASED DECORATORS (Share common context restoration)
# ============================================================================

def bind_workflow_session():
    """Workflow session binding with complete context restoration"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, session_id: str, *args, **kwargs):
            await _restore_session_context(request, session_id, "workflow_session")
            return await func(request, session_id, *args, **kwargs)
        return wrapper
    return decorator

def bind_rag_session():
    """RAG session binding with complete context restoration"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, session_id: str, *args, **kwargs):
            await _restore_session_context(request, session_id, "rag_session")
            return await func(request, session_id, *args, **kwargs)
        return wrapper
    return decorator

def bind_history_session():
    """History session binding with complete context restoration"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, session_id: str, *args, **kwargs):
            await _restore_session_context(request, session_id, "history_session")
            return await func(request, session_id, *args, **kwargs)
        return wrapper
    return decorator
