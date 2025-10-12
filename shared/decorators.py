from functools import wraps
from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
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


def bind_workflow_session(workflow_config):
    """
    UNIFIED DECORATOR with behavior flags for all workflow types.

    This unified decorator replaces bind_workflow_session and bind_workflow_session_porting,
    dynamically managing behavior based on configuration flags instead of hardcoded logic.

    Args:
        workflow_type: "adapted" (imports STARTER_TOOLS), "ported" (direct logic), "meta" (orchestration)
        response_format: "json" (for artifacts + response), "html" (legacy format)
        artifact_enabled: True to enable artifact extraction and synthetic response generation
        chat_history_context: True to maintain conversation history

    Returns:
        Decorated function with configurable workflow session context
    """
    def decorator(func):
        @wraps(func)
        async def unified_workflow_bound_function(request: Request, payload: Dict[str, Any], *args, **kwargs):
            # SINGLE RESPONSIBILITY: Use raw workflow ID from TOML config for consistent session keys
            workflow_name = workflow_config.workflow_ID

            try:
                # Extract workflow configuration attributes (now available outside try)
                workflow_type = workflow_config.workflow_type
                response_format = workflow_config.response_format
                artifact_enabled = workflow_config.artifact_enabled
                chat_history_context = workflow_config.chat_history_context

                logger.debug(f"bind_workflow_session({workflow_name}): CONFIG-DRIVEN decorator starting for {func.__name__}")

                # Step 1: Initialize user_config (like bind_user_context)
                user_id = getattr(request.state, 'user_id', 'Default')
                user_config = config_manager.get_user_config(user_id)
                request.state.user_config = user_config

                # Step 2: Initialize LLM for user
                try:
                    init_llm(user_config)
                except Exception as e:
                    logger.error(f"bind_workflow_session: Failed to initialize LLM for user {user_id}: {str(e)}")

                # Step 3: ROUTE SESSION MANAGEMENT THROUGH SessionAuthority (SINGLE SOURCE OF TRUTH)
                if chat_history_context:
                    from super_starter_suite.chat_bot.session_authority import session_authority as _session_authority

                    # SINGLE SOURCE: All session operations go through SessionAuthority
                    # This ensures one active session per workflow, no more uncoordinated creation
                    session_data = _session_authority.get_or_create_session(
                        workflow_name=workflow_name,
                        user_config=user_config,
                        existing_session_id=None  # Decorators get what's available, don't specify
                    )

                    session = session_data['session']
                    request.state.chat_session = session
                    request.state.chat_memory = session_data.get('memory')
                    replaced_session_id = session_data.get('replaced_session_id')

                    if replaced_session_id:
                        logger.debug(f"bind_workflow_session({workflow_name}): Session {replaced_session_id[:8]}... replaced by {session.session_id[:8]}...")
                    else:
                        logger.debug(f"bind_workflow_session({workflow_name}): Using session {session.session_id[:8]}... for {workflow_name}")

                    logger.debug(f"bind_workflow_session({workflow_name}): Session {session.session_id} ready with {len(session.messages)} messages via bridge")
                else:
                    # Minimal setup for non-chat workflows
                    request.state.chat_manager = None
                    request.state.chat_session = None
                    request.state.chat_memory = None

                # Step 8: Store workflow config in request state for endpoint access
                request.state.workflow_config = workflow_config

                logger.debug(f"bind_workflow_session({workflow_name}): Configured with workflow_type={workflow_type}")

                # Step 9: Execute the workflow endpoint
                result = await func(request, payload, *args, **kwargs)

                return result

            except HTTPException:
                logger.error(f"bind_workflow_session({workflow_name}): HTTPException caught, re-raising")
                raise
            except Exception as e:
                logger.error(f"bind_workflow_session({workflow_name}): EXCEPTION: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize workflow session context: {str(e)}"
                )

        return unified_workflow_bound_function
    return decorator
