from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from super_starter_suite.STARTER_TOOLS.financial_report.app.workflow import create_workflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from llama_index.core.base.llms.types import MessageRole
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
porting_logger = config_manager.get_logger("porting")
router = APIRouter()

@router.post("/chat")
@bind_user_context
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the ported Financial Report workflow.
    Uses direct LlamaIndex workflow execution with proper AgentWorkflowStartEvent pattern.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_html, status_code = create_error_response(error_msg, "Financial Report", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Extract the user's message from the payload
        user_message = payload.get("question")
        if not user_message:
            error_html, status_code = create_error_response("Question is required", "Financial Report", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Get user context from request state
        user_id = request.state.user_id
        user_config = request.state.user_config
        porting_logger.debug(f"Financial Report workflow request: URL={request.url}  USER={user_id}  PAYLOAD={user_message[:100]}...")

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
        porting_logger.debug(f"[DEBUG] Workflow completed successfully: {result}")

        # Handle AgentOutput result properly
        if hasattr(result, 'response') and result.response:
            response_content = str(result.response.content)
        else:
            response_content = str(result) if result else "Financial report completed successfully"

        # Format as HTML response
        response_content = f"<p>{response_content}</p>"

        # Log execution with elapsed duration
        log_workflow_execution("Financial Report", user_message, True, (time.time() - start_time))

        return HTMLResponse(content=response_content, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Financial Report", payload.get("question", "unknown"), False, duration)
        porting_logger.error(f"Financial Report workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Financial Report")
        return HTMLResponse(content=error_html, status_code=status_code)
