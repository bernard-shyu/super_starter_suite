# super_starter_suite/shared/workflow_utils.py

from typing import Callable, Any, Dict, Type, Tuple
from super_starter_suite.shared.workflow_server import WorkflowServer
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
workflow_logger = config_manager.get_logger("workflow")

def create_workflow_factory(workflow_server: WorkflowServer) -> Callable[[str], Type[Any]]:
    """
    Create a generic workflow factory function.

    Args:
        workflow_server: The WorkflowServer instance to use for retrieving workflows.

    Returns:
        A function that takes a workflow name and returns the corresponding workflow class.
    """
    def workflow_factory(workflow_name: str) -> Type[Any]:
        workflow_class = workflow_server.registry.get_workflow(workflow_name)
        if not workflow_class:
            raise ValueError(f"Workflow {workflow_name} not found in registry")
        return workflow_class

    return workflow_factory

def create_event_factory(workflow_server: WorkflowServer) -> Callable[[str, str], Any]:
    """
    Create a generic event factory function.

    Args:
        workflow_server: The WorkflowServer instance to use for retrieving events.

    Returns:
        A function that takes a workflow name and user question, and returns the corresponding event class.
    """
    def event_factory(workflow_name: str, user_question: str) -> Any:
        event_class = workflow_server.registry.get_event(workflow_name)
        if not event_class:
            raise ValueError(f"Event for workflow {workflow_name} not found in registry")

        if workflow_name == "DeepResearchWorkflow":
            start_event = event_class()
            start_event.user_msg = user_question
            start_event.chat_history = []
            return start_event

        return event_class(user_msg=user_question, context="")

    return event_factory

def validate_workflow_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the workflow payload.

    Args:
        payload: The request payload containing user input.

    Returns:
        A tuple containing a boolean indicating if the payload is valid and an error message if not.
    """
    if "question" not in payload:
        return False, "Request must contain a 'question' field"
    if not payload["question"].strip():
        return False, "Question field cannot be empty"
    return True, ""

def create_error_response(error_message: str, workflow_name: str, status_code: int = 500) -> Tuple[str, int]:
    """
    Create an error response HTML content.

    Args:
        error_message: The error message to display.
        workflow_name: The name of the workflow that encountered the error.
        status_code: The HTTP status code to return.

    Returns:
        A tuple containing the error HTML content and the status code.
    """
    error_html = f"""
    <html>
    <head><title>Error</title></head>
    <body>
    <h1>Error in {workflow_name} Workflow</h1>
    <p>{error_message}</p>
    </body>
    </html>
    """
    return error_html, status_code

def log_workflow_execution(workflow_name: str, question: str, success: bool, duration: float):
    """
    Log the execution of a workflow.

    Args:
        workflow_name: The name of the workflow that was executed.
        question: The user question that was processed.
        success: A boolean indicating if the execution was successful.
        duration: The duration of the execution in seconds.
    """
    log_message = f"{workflow_name} workflow executed {'successfully' if success else 'unsuccessfully'}"
    workflow_logger.info(f"{log_message} in {duration:.2f} seconds for question: {question[:100]}...")
