# super_starter_suite/shared/workflow_utils.py

from typing import Callable, Any, Dict, Type, Tuple, List, Optional
from super_starter_suite.shared.workflow_server import WorkflowServer
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.artifact_utils import extract_artifact_metadata
from super_starter_suite.shared.workflow_loader import get_workflow_config
from llama_index.server.api.models import ArtifactEvent

# UNIFIED LOGGING SYSTEM - Replace global logging
workflow_logger = config_manager.get_logger("workflow.utils")

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

        # Generic event creation - rely on the event class constructor
        # The WorkflowServer's _create_framework_event will handle specific initializers
        try:
            return event_class(user_msg=user_question, context="")
        except TypeError:
            try:
                return event_class(user_msg=user_question)
            except TypeError:
                start_event = event_class()
                if hasattr(start_event, 'user_msg'):
                    start_event.user_msg = user_question
                if hasattr(start_event, 'message'):
                    start_event.message = user_question
                if hasattr(start_event, 'question'):
                    start_event.question = user_question
                return start_event

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

async def process_workflow_events(handler, workflow_name: str) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """
    Generic workflow event processing for consistent artifact extraction and response handling.

    This function processes ALL events during workflow execution, including artifacts sent after StopEvent,
    to handle workflows where artifacts are generated after completion (like deep_research).

    Args:
        handler: Async workflow handler from workflow.run()
        workflow_name: Name of the workflow for logging

    Returns:
        Tuple of (conversation_response, artifacts_collected, planning_response)
    """
    artifacts_collected = []
    response_content = ""
    planning_response = ""

    workflow_logger.debug(f"[{workflow_name}] Starting event processing...")

    # Process ALL events - don't stop on StopEvent, continue to catch delayed artifacts
    async for event in handler.stream_events():
        event_type = type(event).__name__
        workflow_logger.debug(f"[{workflow_name}] Processing event: {event_type}")

        # Generic UIEvent processing - attribute-wise, not state-wise
        from llama_index.server.api.models import UIEvent
        if isinstance(event, UIEvent) and hasattr(event, 'data'):
            planning_response = _process_ui_event_attributes(event, workflow_name, planning_response)

        # Generic ArtifactEvent processing - capture artifacts ANYTIME during execution
        elif isinstance(event, ArtifactEvent):
            workflow_logger.info(f"[{workflow_name}] FOUND ARTIFACT EVENT: {getattr(event.data, 'type', 'unknown')}")
            try:
                artifact_data = extract_artifact_metadata(event.data)
                artifacts_collected.append(artifact_data)
                workflow_logger.info(f"[{workflow_name}] SUCCESSFULLY EXTRACTED: {artifact_data['type']} ({len(artifact_data.get('content', ''))} chars)")
            except Exception as e:
                workflow_logger.error(f"[{workflow_name}] Artifact extraction failed: {e}")

        # Track StopEvent but continue processing (artifacts may come after)
        elif 'StopEvent' in event_type:
            workflow_logger.debug(f"[{workflow_name}] StopEvent encountered but continuing to catch artifacts...")

        # Fallback for streaming content
        elif hasattr(event, 'delta') and event.delta:
            response_content += event.delta
        elif hasattr(event, 'content') and event.content:
            response_content += event.content

    workflow_logger.debug(f"[{workflow_name}] Event processing complete: {len(artifacts_collected)} artifacts collected")
    return response_content, artifacts_collected, planning_response

def _process_ui_event_attributes(event, workflow_name: str, planning_response: str) -> str:
    """
    Process UI event attributes dynamically instead of hardcoded state names.

    This allows different workflows to use different attribute names and values:
    - code_generator: state="plan", requirement="planning text"
    - financial_report: state="analyze", analysis="analysis text"
    - deep_research: state="research", findings="research findings"

    Args:
        event: The UIEvent to process
        workflow_name: Workflow name for logging
        planning_response: Current planning response content

    Returns:
        Updated planning response if conversational text was found
    """
    # Dynamically inspect all attributes in event.data
    data_attrs = {}
    for attr_name in dir(event.data):
        if not attr_name.startswith('_'):  # Skip private attributes
            attr_value = getattr(event.data, attr_name, None)
            if attr_value is not None and not callable(attr_value):
                data_attrs[attr_name] = attr_value

    workflow_logger.debug(f"[{workflow_name}] UIEvent attributes: {list(data_attrs.keys())}")

    # Extract conversational/planning content from text attributes
    text_attributes = ['requirement', 'analysis', 'findings', 'summary', 'content', 'description', 'message']
    conversational_text = None

    for attr_name in text_attributes:
        if attr_name in data_attrs and isinstance(data_attrs[attr_name], str) and data_attrs[attr_name].strip():
            conversational_text = data_attrs[attr_name]
            attr_len = len(conversational_text)
            attr_preview = conversational_text[:50] + "..." if attr_len > 50 else conversational_text
            workflow_logger.debug(f"[{workflow_name}] Extracted {attr_name} ({attr_len} chars): {attr_preview}")
            break

    # Format conversational text for better display if found
    if conversational_text:
        # Format lists and improve readability
        formatted_response = conversational_text.replace('. ', '\n• ').replace(', ', '\n• ')
        planning_response = formatted_response
        workflow_logger.info(f"[{workflow_name}] Conversational response captured: {len(planning_response)} characters")

    # Log state information if available (for debugging)
    if 'state' in data_attrs:
        workflow_logger.debug(f"[{workflow_name}] Current state: {data_attrs['state']}")

    return planning_response

async def execute_workflow_with_artifacts(workflow, user_message: str, chat_memory=None) -> Tuple[Any, str, List[Dict[str, Any]]]:
    """
    Execute a workflow and return artifacts using shared event processing.

    Args:
        workflow: The workflow instance to execute
        user_message: The user message/question
        chat_memory: Optional chat memory for context

    Returns:
        Tuple of (final_result, response_content, artifacts_collected)
    """
    handler = workflow.run(
        user_msg=user_message,
        chat_history=chat_memory.get() if chat_memory else None
    )
    workflow_logger.debug(f"Workflow handler created: {type(handler)}")

    # Use generic event processing
    response_content, artifacts_collected, _ = await process_workflow_events(handler, type(workflow).__name__)

    # Get final workflow result
    final_result = await handler
    workflow_logger.debug(f"Workflow completed: {type(final_result)}")

    return final_result, response_content, artifacts_collected

def save_artifacts_to_session(chat_manager, session, artifacts: List[Dict[str, Any]], workflow_config=None):
    """
    Save artifacts to chat session with proper metadata persistence.

    Args:
        chat_manager: ChatHistoryManager instance
        session: Current chat session
        artifacts: List of artifact dictionaries
        workflow_config: Optional WorkflowConfig for synthetic responses
    """
    if not artifacts:
        workflow_logger.warning("No artifacts to save to session")
        return

    # Generate synthetic conversational response if needed
    response_content = ""
    if workflow_config and workflow_config.synthetic_response:
        try:
            response_content = workflow_config.synthetic_response.format(count=len(artifacts))
        except (KeyError, ValueError) as e:
            workflow_logger.warning(f"Failed to use synthetic response template: {e}")
            response_content = f"Generated {len(artifacts)} artifacts"
    else:
        response_content = f"Generated {len(artifacts)} outputs"

    # Save with artifacts embedded in message metadata
    chat_manager.add_message_with_artifacts(
        session=session,
        response_content=response_content,
        artifacts=artifacts,
        workflow_config=workflow_config
    )

    workflow_logger.debug(f"Saved {len(artifacts)} artifacts to session {session.session_id}")

async def execute_adapter_workflow(workflow_factory, workflow_config, user_message: str, user_config, chat_manager, session, chat_memory, logger) -> Dict[str, Any]:
    """
    Generic workflow execution function that replaces 200+ lines of common code in workflow_adapters.

    This function packages all the common workflow execution patterns:
    - ChatRequest setup
    - Previous artifact checking
    - Workflow instantiation and execution
    - UIEvent processing (generic, not hardcoded state names)
    - Artifact collection
    - Conversational response extraction
    - Response formatting

    Args:
        workflow_factory: Function to create workflow instance
        user_message: The user query
        user_config: User configuration object
        chat_manager: ChatHistoryManager instance
        session: Current chat session
        chat_memory: LlamaIndex chat memory
        workflow_name: Name for logging
        logger: Logger instance

    Returns:
        Standard response dict with "response" and "artifacts" keys
    """
    import time
    from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
    from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole

    start_execution = time.time()

    logger.info(f"Starting {workflow_config.display_name} workflow for session {session.session_id}")

    try:
        # STEP 1: ChatRequest setup
        chat_request = ChatRequest(
            id=user_config.user_id,
            messages=[ChatAPIMessage(role=LlamaMessageRole.USER, content=user_message)],
        )

        # STEP 2: Previous artifact checking (optional enhancement)
        try:
            from llama_index.server.api.utils import get_last_artifact
            previous_artifact = get_last_artifact(chat_request)
            if previous_artifact:
                logger.debug(f"Found previous artifact: {previous_artifact.type}")
        except Exception as e:
            logger.debug(f"No previous artifacts or error checking: {e}")

        # STEP 3: Workflow instantiation
        workflow = workflow_factory(chat_request=chat_request)
        handler = workflow.run(
            user_msg=user_message,
            chat_history=chat_memory.get() if chat_memory else None
        )

        # STEP 4: Execute workflow with async shared utilities
        try:
            response_content, artifacts_collected, planning_response = await process_workflow_events(handler, workflow_config.display_name)

            # Get final workflow result
            final_result = await handler

            logger.info(f"{workflow_config.display_name} workflow completed: {len(artifacts_collected) if artifacts_collected else 0} artifacts")

        except Exception as e:
            logger.error(f"{workflow_config.display_name} workflow execution failed: {e}")
            response_content = f"Workflow error: {str(e)}"
            artifacts_collected = []

        # STEP 5: Save artifacts to session with persistence
        save_artifacts_to_session(
            chat_manager=chat_manager,
            session=session,
            artifacts=artifacts_collected,
            workflow_config=workflow_config
        )

        # STEP 7: Determine conversational response
        if planning_response and planning_response.strip():
            conversation_response = planning_response
        else:
            conversation_response = response_content or f"Workflow completed successfully"

        # STEP 8: Return standardized response format
        response_data = {
            "response": conversation_response,
            "artifacts": artifacts_collected if artifacts_collected else None
        }

        logger.debug(f"{workflow_config.display_name} execution completed in {(time.time() - start_execution):.2f}s")
        return response_data

    except Exception as e:
        logger.error(f"{workflow_config.display_name} workflow error: {e}")
        return {
            "response": f"Unexpected error: {str(e)}",
            "artifacts": None
        }

async def execute_agentic_workflow(workflow_factory, workflow_config, user_message: str, user_config, chat_manager, session, chat_memory, logger) -> Dict[str, Any]:
    """
    Specialized workflow execution for AgentWorkflow types (like agentic_rag).

    AgentWorkflows use AgentWorkflowStartEvent pattern instead of simple user_msg,
    offering multi-turn conversation capabilities through agent-driven reasoning.

    Design Principles:
    1. Configuration-driven timeout control prevents runaway workflows
    2. Consistent session lifecycle management across agentic interactions
    3. Thread-safe execution within asyncio context
    4. Structured response format with optional artifacts for UI consumption

    Workflow Execution Flow:
    1. ChatRequest setup with conversation history
    2. AgentWorkflow instantiation with configured timeout
    3. Async execution with memory persistence
    4. Response extraction and session storage
    5. Standardized return format: {"response": str, "artifacts": None}

    Args:
        workflow_factory: Factory function creating AgentWorkflow instances
        workflow_config: WorkflowConfig object with timeout, display_name, etc.
        user_message: Current user query for agent processing
        user_config: User configuration object with model/llm settings
        chat_manager: ChatHistoryManager for session persistence
        session: Current chat session for message storage
        chat_memory: LlamaIndex chat memory for conversation context
        logger: Configured logger for execution tracking

    Returns:
        Standardized response dictionary:
        - "response": Agent-generated conversational response (str)
        - "artifacts": Always None (agent workflows don't generate artifacts)

    Raises:
        Execution-time exceptions are caught and returned as error responses,
        with proper logging and session cleanup.

    Note:
        AgentWorkflows prioritize conversational intelligence over artifact generation,
        reflecting their primary use case of intelligent document QA and knowledge retrieval.
    """
    import time
    from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
    from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
    from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent

    start_execution = time.time()

    logger.info(f"Starting AgentWorkflow {workflow_config.display_name} for session {session.session_id}")

    try:
        # STEP 1: ChatRequest setup
        chat_request = ChatRequest(
            id=user_config.user_id,
            messages=[ChatAPIMessage(role=LlamaMessageRole.USER, content=user_message)],
        )

        # STEP 2: Workflow instantiation with configured timeout
        workflow = workflow_factory(chat_request=chat_request, timeout_seconds=workflow_config.timeout)

        # STEP 3: Execute agent workflow with configured timeout control
        result = await workflow.run(
            user_msg=user_message,
            chat_history=None,
            memory=chat_memory,
            max_iterations=None
        )
        logger.info(f"AgentWorkflow {workflow_config.display_name} completed: {type(result)}")

        # STEP 5: Extract response content
        response_content = str(result) if result else "No response generated"

        # STEP 6: Save to session (agentic workflows typically don't have artifacts)
        from super_starter_suite.shared.dto import MessageRole, create_chat_message
        assistant_msg = create_chat_message(role=MessageRole.ASSISTANT, content=response_content)
        chat_manager.add_message_to_session(session, assistant_msg)

        # STEP 7: Return standard format (no artifacts for agentic workflows)
        response_data = {
            "response": response_content,
            "artifacts": None  # AgentWorkflows don't generate artifacts
        }

        logger.debug(f"AgentWorkflow {workflow_config.display_name} execution completed in {(time.time() - start_execution):.2f}s")
        return response_data

    except Exception as e:
        logger.error(f"AgentWorkflow {workflow_config.display_name} error: {e}")
        return {
            "response": f"Unexpected error: {str(e)}",
            "artifacts": None
        }
