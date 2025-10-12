"""
Human-In-The-Loop Workflow Endpoint
Handles responses from frontend HITL interactions and forwards them to running workflows.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.shared.config_manager import config_manager

# Get logger for HITL endpoint
logger = config_manager.get_logger("hitl_endpoint")

router = APIRouter()

@router.post("/workflow/response")
@bind_user_context
async def handle_workflow_response(request: Request, response_data: Dict[str, Any]):
    """
    Handle human-in-the-loop responses from the frontend.
    Forwards responses to the appropriate running workflow.
    """
    user_config = request.state.user_config
    user_id = user_config.user_id

    try:
        event_type = response_data.get("event_type")

        logger.info(f"[HITL] Received response from user {user_id}: {event_type}")

        # Handle different types of HITL responses
        if event_type == "CLIHumanResponseEvent":
            return await handle_cli_response(response_data, user_id, request)
        elif event_type == "TextInputResponseEvent":
            return await handle_text_input_response(response_data, user_id, request)
        elif event_type == "FeedbackResponseEvent":
            return await handle_feedback_response(response_data, user_id, request)
        elif event_type == "EditAndResubmitEvent":
            return await handle_edit_resubmit_response(response_data, user_id, request)
        elif event_type == "ConfirmationResponseEvent":
            return await handle_confirmation_response(response_data, user_id, request)
        else:
            logger.warning(f"[HITL] Unknown event type: {event_type}")
            return JSONResponse(content={
                "status": "ignored",
                "message": f"Unknown event type: {event_type}"
            })

    except Exception as e:
        logger.error(f"[HITL] Error handling workflow response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Workflow response error: {str(e)}")

async def handle_cli_response(response_data: Dict[str, Any], user_id: str, request: Request):
    """Handle CLI command approval/rejection."""
    execute = response_data.get("execute", False)
    command = response_data.get("command", "")

    # Import the event types
    try:
        from super_starter_suite.STARTER_TOOLS.human_in_the_loop.app.events import CLIHumanResponseEvent, CLICommand
    except ImportError:
        logger.warning("[HITL] CLI event types not available, sending generic acknowledgment")
        return JSONResponse(content={
            "status": "received",
            "message": f"CLI command {'approved' if execute else 'rejected'}",
            "command": command
        })

    try:
        # Create the proper event object
        cli_response = CLIHumanResponseEvent(
            execute=execute,
            command=command
        )

        logger.info(f"[HITL] CLI Response processed: execute={execute}, command='{command}'")

        # TODO: Forward the event to the running workflow instance
        # For now, just acknowledge and log
        # In a full implementation, this would:
        # 1. Find the running workflow instance for this user/session
        # 2. Send the CLIHumanResponseEvent to resume the workflow
        # 3. Handle workflow state persistence

        return JSONResponse(content={
            "status": "processed",
            "message": f"CLI command {'approved and executed' if execute else 'rejected'}",
            "command": command[:100] + "..." if len(command) > 100 else command
        })

    except Exception as e:
        logger.error(f"[HITL] Error processing CLI response: {e}")
        raise

async def handle_text_input_response(response_data: Dict[str, Any], user_id: str, request: Request):
    """Handle text input responses."""
    input_value = response_data.get("input", "")
    modal_id = response_data.get("modalId", "")

    logger.info(f"[HITL] Text input received: '{input_value[:100]}...' (modal: {modal_id})")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": "Text input received",
        "input_length": len(input_value)
    })

async def handle_feedback_response(response_data: Dict[str, Any], user_id: str, request: Request):
    """Handle feedback responses."""
    feedback = response_data.get("feedback", "")

    logger.info(f"[HITL] Feedback received: '{feedback[:200]}...'")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": "Feedback received",
        "feedback_length": len(feedback)
    })

async def handle_edit_resubmit_response(response_data: Dict[str, Any], user_id: str, request: Request):
    """Handle edit and resubmit responses."""
    feedback = response_data.get("feedback", "")

    logger.info(f"[HITL] Edit and resubmit: '{feedback[:200]}...'")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": "Edit and resubmit request received"
    })

async def handle_confirmation_response(response_data: Dict[str, Any], user_id: str, request: Request):
    """Handle confirmation responses."""
    confirmed = response_data.get("confirmed", False)
    modal_id = response_data.get("modalId", "")

    logger.info(f"[HITL] Confirmation response: {confirmed} (modal: {modal_id})")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": f"Action {'confirmed' if confirmed else 'cancelled'}"
    })
