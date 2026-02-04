"""
Human-In-The-Loop (HITL) Response Handlers

Handles different types of HITL responses from frontend.
Moved from hitl_endpoint.py for better separation of concerns.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from super_starter_suite.shared.config_manager import config_manager

# Get logger
logger = config_manager.get_logger("workflow.ui_event")


async def handle_cli_response_via_workflow(request: Request, response_data: Dict[str, Any]):
    """
    Handle CLI command approval/rejection directly.
    Execute approved commands immediately and send results back.
    """
    execute = response_data.get("execute", False)
    command = response_data.get("command", "")
    session_id = response_data.get("session_id")
    workflow_id = response_data.get("workflow_id")

    if not workflow_id or not session_id:
        return JSONResponse(status_code=400, content={"error": "Missing workflow_id or session_id"})

    logger.info(f"[HITL] ===== HANDLING CLI RESPONSE =====")
    logger.info(f"[HITL] Session: {session_id}, Workflow: {workflow_id}")
    logger.info(f"[HITL] Execute: {execute}, Command: {command[:50]}...")

    try:
        if not execute:
            # Command rejected - send rejection message
            logger.info(f"[HITL] Command rejected by user")
            return JSONResponse(content={
                "status": "rejected",
                "message": "Command rejected by user",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "execute": False
            })

        # Command approved - execute it directly
        if not command.strip():
            logger.error(f"[HITL] Empty command received for execution")
            return JSONResponse(status_code=400, content={"error": "Empty command"})

        logger.info(f"[HITL] Executing approved command: {command}")

        # Execute the command directly using the same logic as the workflow
        from super_starter_suite.shared.config_manager import config_manager
        import os
        import subprocess

        try:
            # Get workflow data directory from user configuration
            # USER_RAG_ROOT is set in the config and used for workflow data
            user_id = getattr(request.state, 'user_id', 'anonymous')
            user_config = config_manager.get_user_config(user_id)
            user_rag_root = getattr(user_config, 'my_rag_root', os.path.expanduser("~"))
            workflow_data_dir = os.path.join(user_rag_root, "workflow_data")

            logger.info(f"[HITL] Executing command in directory: {workflow_data_dir}")
            os.makedirs(workflow_data_dir, exist_ok=True)

            # Execute the command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute timeout
                cwd=workflow_data_dir
            )

            # Prepare execution result
            execution_result = {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "session_id": session_id,
                "workflow_id": workflow_id
            }

            logger.info(f"[HITL] Command executed with exit code: {result.returncode}")

            return JSONResponse(content={
                "status": "executed",
                "message": "Command executed successfully" if result.returncode == 0 else "Command execution failed",
                "execution_result": execution_result,
                "session_id": session_id,
                "workflow_id": workflow_id,
                "execute": True
            })

        except subprocess.TimeoutExpired:
            logger.error(f"[HITL] Command timed out: {command}")
            return JSONResponse(content={
                "status": "timeout",
                "message": "Command execution timed out after 5 minutes",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "execute": True
            })

        except Exception as exec_error:
            logger.error(f"[HITL] Command execution failed: {exec_error}")
            return JSONResponse(content={
                "status": "error",
                "message": f"Command execution failed: {str(exec_error)}",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "execute": True
            })

    except Exception as e:
        logger.error(f"[HITL] Error in CLI response handling: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Failed to process CLI response: {str(e)}",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "status": "error"
            }
        )


async def handle_text_input_response(response_data: Dict[str, Any], request: Request):
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


async def handle_feedback_response(response_data: Dict[str, Any], request: Request):
    """Handle feedback responses."""
    feedback = response_data.get("feedback", "")

    logger.info(f"[HITL] Feedback received: '{feedback[:200]}...'")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": "Feedback received",
        "feedback_length": len(feedback)
    })


async def handle_edit_resubmit_response(response_data: Dict[str, Any], request: Request):
    """Handle edit and resubmit responses."""
    feedback = response_data.get("feedback", "")

    logger.info(f"[HITL] Edit and resubmit: '{feedback[:200]}...'")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": "Edit and resubmit request received"
    })


async def handle_confirmation_response(response_data: Dict[str, Any], request: Request):
    """Handle confirmation responses."""
    confirmed = response_data.get("confirmed", False)
    modal_id = response_data.get("modalId", "")

    logger.info(f"[HITL] Confirmation response: {confirmed} (modal: {modal_id})")

    # TODO: Forward to running workflow instance

    return JSONResponse(content={
        "status": "processed",
        "message": f"Action {'confirmed' if confirmed else 'cancelled'}"
    })
