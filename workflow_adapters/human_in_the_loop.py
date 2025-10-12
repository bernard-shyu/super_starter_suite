from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.workflow_utils import (
    validate_workflow_payload,
    create_error_response,
    log_workflow_execution,
    execute_adapter_workflow
)
from super_starter_suite.STARTER_TOOLS.human_in_the_loop.app.workflow import create_workflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
logger = config_manager.get_logger("workflow.bzlogic")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "A_human_in_the_loop"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

@router.post("/chat")
@bind_workflow_session(workflow_config)  # Single param decorator # CRITICAL: Must come AFTER @router.post()
# Unified decorator with configuration-driven behavior flags
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the Human in the Loop workflow.
    Uses direct LlamaIndex workflow execution with proper AgentWorkflowStartEvent pattern.
    Integrated with chat history system for persistent conversations.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_html, status_code = create_error_response(error_msg, "Human in the Loop", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Extract user message (already added to session by decorator)
        user_message = payload["question"]

        # Get session and context prepared by decorator
        user_config = request.state.user_config
        chat_manager = request.state.chat_manager
        session = request.state.chat_session
        chat_memory = request.state.chat_memory

        # Execute workflow using shared utilities (replaces inline workflow execution)
        response_data = await execute_adapter_workflow(
            workflow_factory=create_workflow,
            workflow_config=workflow_config,
            user_message=user_message,
            user_config=user_config,
            chat_manager=chat_manager,
            session=session,
            chat_memory=chat_memory,
            logger=logger
        )

        # Extract response content for HTML formatting
        response_content = response_data.get("response", "Human in the loop workflow completed successfully")
        # Format as HTML response
        response_html = f"<p>{response_content}</p>"

        # Log execution with elapsed duration
        log_workflow_execution("Human In The Loop", user_message, True, (time.time() - start_time))

        return HTMLResponse(content=response_html, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Human In The Loop", payload.get("question", "unknown"), False, duration)
        logger.error(f"Human In The Loop workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Human In The Loop")
        return HTMLResponse(content=error_html, status_code=status_code)
