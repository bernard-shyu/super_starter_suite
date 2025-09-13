from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Dict, Any
import logging, os
import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.shared.workflow_server import WorkflowServer
from super_starter_suite.STARTER_TOOLS.agentic_rag.app.workflow import create_workflow
from super_starter_suite.shared.workflow_server import Settings, WorkflowRegistry
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from llama_index.core.llms import ChatMessage
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from llama_index.core.base.llms.types import MessageRole

# UNIFIED LOGGING SYSTEM - Replace global logging
adapter_logger = config_manager.get_logger("adapter")
router = APIRouter()

@router.post("/chat")
@bind_user_context  # CRITICAL: bind_user_context must come AFTER @router.post()
# This ensures the router gets the decorated function, not the original.
# Before: @bind_user_context was applied first, then @router.post() captured the original function
# After: @router.post() captures the decorated function, enabling proper LLM initialization
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the Agentic RAG workflow.
    Uses the bridge pattern with shared workflow_server for consistent integration.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_html, status_code = create_error_response(error_msg, "Agentic RAG", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Extract the user's message from the payload
        user_message = payload.get("question")

        # Get user context from request state
        user_message = payload["question"]
        user_id = request.state.user_id
        user_config = request.state.user_config
        adapter_logger.debug(f"ChatEndpoint called: URL={request.url}  USER={user_id}  PAYLOAD={user_message[:100]}...")

        # Create ChatRequest object for user context
        chat_request = ChatRequest(
            id=user_id,
            messages=[ChatAPIMessage(role=MessageRole.USER, content=user_message)],
        )

        # Create a proper start event with the chat request
        start_event = AgentWorkflowStartEvent(
            user_msg=user_message,
            chat_history=None,
            memory=None,
            max_iterations=None
        )

        # Instantiate and run the workflow with the start event
        workflow = create_workflow(chat_request=chat_request)
        result = await workflow.run(start_event=start_event)
        adapter_logger.debug(f"[DEBUG] Workflow completed successfully: {result}")

        # Convert the result to a suitable HTML string
        response_content = f"<p>{result}</p>"

        # Log execution with elapsed duration
        log_workflow_execution("Agentic RAG", user_message, True, (time.time() - start_time))

        return HTMLResponse(content=response_content, status_code=status.HTTP_200_OK)


    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Agentic RAG", payload.get("question", "unknown"), False, duration)
        adapter_logger.error(f"Agentic RAG workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Agentic RAG")
        return HTMLResponse(content=error_html, status_code=status_code)

    return HTMLResponse(content="Internal Server Error", status_code=500)
