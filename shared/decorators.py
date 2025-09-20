from functools import wraps
from fastapi import Request, HTTPException
from .config_manager import config_manager
from .llama_utils import init_llm

# Initialize logger
logger = config_manager.get_logger("main")


def bind_user_context(func):
    """
    Decorator to bind user context to FastAPI endpoints.
    Ensures user settings are loaded and available in the request state.
    Also initializes the LLM for the user.

    CRITICAL: In Python, decorators are applied from bottom to top.
    This decorator must be placed AFTER @router decorators to ensure FastAPI gets this decorated function beforehand.
    """
    @wraps(func)
    async def context_bound_function(request: Request, *args, **kwargs):
        try:
            # Ensure user context is initialized
            user_id = getattr(request.state, 'user_id', 'Default')
            user_config = config_manager.get_user_config(user_id)
            request.state.user_config = user_config

            # CRITICAL: Always initialize LLM when decorator is called
            user_id = getattr(request.state, 'user_id', 'Default')
            user_config = request.state.user_config

            try:
                init_llm(user_config)
            except Exception as e:
                # Log error but don't fail the request - let endpoints handle LLM issues
                logger.error(f"bind_user_context: Failed to initialize LLM for user {user_id}: {str(e)}")

            # Verify settings are available
            if not hasattr(request.state, 'user_config'):
                raise HTTPException(
                    status_code=400,
                    detail="User context not available. Please ensure user is properly identified."
                )

            return await func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"EXCEPTION in bind_user_context decorator: {str(e)}", exc_info=True)
            # Re-raise the exception to not hide it
            raise

    return context_bound_function

def bind_rag_session(func):
    """
    PHASE 1: Single decorator that handles both user context and RAG session.

    This decorator combines @bind_user_context and @bind_rag_session functionality:
    1. Initializes user_config from request.state.user_id
    2. Initializes LLM for the user
    3. Creates/gets RAG generation session
    4. Handles RAG type switching automatically

    Single point of entry for Generate UI endpoints - no more dual decorators needed.

    Args:
        func: The endpoint function to decorate

    Returns:
        Decorated function with user_config and rag_session in request.state
    """
    @wraps(func)
    async def unified_bound_function(request: Request, *args, **kwargs):
        try:
            logger.debug(f"PHASE 1 bind_rag_session: Starting unified decorator for {func.__name__}")

            # PHASE 1: Step 1 - Initialize user_config (from bind_user_context)
            user_id = getattr(request.state, 'user_id', 'Default')
            user_config = config_manager.get_user_config(user_id)
            request.state.user_config = user_config

            # PHASE 1: Step 2 - Initialize LLM (from bind_user_context)
            try:
                init_llm(user_config)
            except Exception as e:
                logger.error(f"bind_rag_session: Failed to initialize LLM for user {user_id}: {str(e)}")

            # PHASE 1: Step 3 - Create/get RAG session (from bind_rag_session)
            from super_starter_suite.rag_indexing.rag_generation_session import create_rag_session
            session = create_rag_session(user_config)
            request.state.rag_session = session

            # PHASE 1: Step 4 - Auto-handle RAG type consistency
            # Session owns current_rag_type, no external parameters needed
            current_rag_type = user_config.my_rag.rag_type
            if session._current_rag_type != current_rag_type:
                logger.debug(f"bind_rag_session: Auto-switching RAG type {session._current_rag_type} -> {current_rag_type}")
                # Use session's clean switch_rag_type method (no external params)
                session.switch_rag_type(current_rag_type)
                logger.debug(f"bind_rag_session: Switched to {current_rag_type}, total_files={session.get_total_files()}")

            result = await func(request, *args, **kwargs)
            return result

        except HTTPException:
            logger.error("bind_rag_session: HTTPException caught, re-raising")
            raise
        except Exception as e:
            logger.error(f"EXCEPTION in bind_rag_session decorator: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize unified context: {str(e)}"
            )

    return unified_bound_function
