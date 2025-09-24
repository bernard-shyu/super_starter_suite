from functools import wraps
from fastapi import Request, HTTPException
from typing import Dict, Any
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


def bind_workflow_session(workflow_name: str):
    """
    Unified decorator for workflow_adapters that provides chat history session management.

    This decorator combines user context binding with persistent chat session management:
    1. Initializes user_config from request.state.user_id (like bind_user_context)
    2. Sets up ChatHistoryManager and SessionLifecycleManager
    3. Ensures one persistent session per workflow type
    4. Loads session and LlamaIndex memory for conversation context
    5. Injects session objects into request.state for endpoint use

    After endpoint execution, caller is responsible for:
    - Adding assistant response to session via chat_manager.add_message_to_session()

    Args:
        workflow_name: The workflow type identifier (e.g., "agentic-rag", "code-generator")

    Returns:
        Decorated function with chat session context in request.state
    """
    def decorator(func):
        @wraps(func)
        async def workflow_bound_function(request: Request, payload: Dict[str, Any], *args, **kwargs):
            try:
                logger.debug(f"bind_workflow_session({workflow_name}): Starting for {func.__name__}")

                # Step 1: Initialize user_config (like bind_user_context)
                user_id = getattr(request.state, 'user_id', 'Default')
                user_config = config_manager.get_user_config(user_id)
                request.state.user_config = user_config

                # Step 2: Initialize LLM for user
                try:
                    init_llm(user_config)
                except Exception as e:
                    logger.error(f"bind_workflow_session: Failed to initialize LLM for user {user_id}: {str(e)}")

                # Step 3: Set up chat session management
                from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager, SessionLifecycleManager
                from super_starter_suite.shared.dto import MessageRole, create_chat_message

                chat_manager = ChatHistoryManager(user_config)
                request.state.chat_manager = chat_manager

                # Step 4: Get or create ONE persistent session for this workflow
                session_lifecycle = SessionLifecycleManager(user_id, chat_manager)
                persistent_session_id = session_lifecycle.get_or_create_workflow_session(workflow_name)

                # Step 5: Load the persistent session
                session = chat_manager.load_session(workflow_name, persistent_session_id)
                if not session:
                    logger.error(f"bind_workflow_session: Failed to load session {persistent_session_id} for {workflow_name}")
                    raise HTTPException(status_code=500, detail=f"Failed to load chat session for {workflow_name}")

                request.state.chat_session = session
                request.state.session_lifecycle = session_lifecycle

                # Step 6: Add user message to session if present
                user_message = payload.get("question") or payload.get("user_message")
                if user_message:
                    user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
                    chat_manager.add_message_to_session(session, user_msg)
                    logger.debug(f"bind_workflow_session: Added user message to session {session.session_id}")

                # Step 7: Get LlamaIndex memory for conversation context
                chat_memory = chat_manager.get_llama_index_memory(session)
                request.state.chat_memory = chat_memory

                logger.debug(f"bind_workflow_session({workflow_name}): Session {session.session_id} ready with {len(session.messages)} messages")

                # Step 8: Execute the workflow endpoint
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

        return workflow_bound_function
    return decorator


def bind_workflow_session_porting(workflow_name: str):
    """
    Unified decorator for workflow_porting that provides chat history session management.

    This decorator is specifically designed for porting workflows which may have different
    payload structures or requirements compared to adapter workflows.

    Combines user context binding with persistent chat session management:
    1. Initializes user_config from request.state.user_id (like bind_user_context)
    2. Sets up ChatHistoryManager and SessionLifecycleManager
    3. Ensures one persistent session per workflow type
    4. Loads session and LlamaIndex memory for conversation context
    5. Injects session objects into request.state for endpoint use

    After endpoint execution, caller is responsible for:
    - Adding assistant response to session via chat_manager.add_message_to_session()

    Args:
        workflow_name: The workflow type identifier (e.g., "agentic-rag", "code-generator")

    Returns:
        Decorated function with chat session context in request.state
    """
    def decorator(func):
        @wraps(func)
        async def workflow_porting_bound_function(request: Request, payload: Dict[str, Any], *args, **kwargs):
            try:
                logger.debug(f"bind_workflow_session_porting({workflow_name}): Starting for {func.__name__}")

                # Step 1: Initialize user_config (like bind_user_context)
                user_id = getattr(request.state, 'user_id', 'Default')
                user_config = config_manager.get_user_config(user_id)
                request.state.user_config = user_config

                # Step 2: Initialize LLM for user
                try:
                    init_llm(user_config)
                except Exception as e:
                    logger.error(f"bind_workflow_session_porting: Failed to initialize LLM for user {user_id}: {str(e)}")

                # Step 3: Set up chat session management
                from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager, SessionLifecycleManager
                from super_starter_suite.shared.dto import MessageRole, create_chat_message

                chat_manager = ChatHistoryManager(user_config)
                request.state.chat_manager = chat_manager

                # Step 4: Get or create ONE persistent session for this workflow
                session_lifecycle = SessionLifecycleManager(user_id, chat_manager)
                persistent_session_id = session_lifecycle.get_or_create_workflow_session(workflow_name)

                # Step 5: Load the persistent session
                session = chat_manager.load_session(workflow_name, persistent_session_id)
                if not session:
                    logger.error(f"bind_workflow_session_porting: Failed to load session {persistent_session_id} for {workflow_name}")
                    raise HTTPException(status_code=500, detail=f"Failed to load chat session for {workflow_name}")

                request.state.chat_session = session
                request.state.session_lifecycle = session_lifecycle

                # Step 6: Add user message to session if present (may use different payload keys)
                user_message = payload.get("question") or payload.get("user_message") or payload.get("message")
                if user_message:
                    user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
                    chat_manager.add_message_to_session(session, user_msg)
                    logger.debug(f"bind_workflow_session_porting: Added user message to session {session.session_id}")

                # Step 7: Get LlamaIndex memory for conversation context
                chat_memory = chat_manager.get_llama_index_memory(session)
                request.state.chat_memory = chat_memory

                logger.debug(f"bind_workflow_session_porting({workflow_name}): Session {session.session_id} ready with {len(session.messages)} messages")

                # Step 8: Execute the workflow endpoint
                result = await func(request, payload, *args, **kwargs)

                return result

            except HTTPException:
                logger.error(f"bind_workflow_session_porting({workflow_name}): HTTPException caught, re-raising")
                raise
            except Exception as e:
                logger.error(f"bind_workflow_session_porting({workflow_name}): EXCEPTION: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize workflow porting session context: {str(e)}"
                )

        return workflow_porting_bound_function
    return decorator
