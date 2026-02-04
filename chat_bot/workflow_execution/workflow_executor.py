"""
Simplified Workflow Executor Service

Simplified WebSocket Architecture & Eliminated Context Conversion

This module provides a single, streamlined entry point for all workflow execution requests.
All execution paths now use direct WorkflowSession integration with no context conversion.

Key Features:
- Single execution entry point: execute_workflow_request()
- Direct WorkflowSession integration (no context conversion)
- Simplified parameter handling and validation
- Unified session management and persistence
- Consistent error handling and metrics
"""

import time
import re
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime
from dataclasses import dataclass
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.dto import ExecutionContext, MessageRole, create_chat_message
from super_starter_suite.chat_bot.workflow_execution.execution_engine import execute_workflow

# UNIFIED LOGGING SYSTEM
logger = config_manager.get_logger("workflow.executor")

# HELPER FUNCTIONS TO AVOID CIRCULAR IMPORTS
def execute_hie_command(command: str, session_id: str, workflow_id: str) -> Dict[str, Any]:
    """
    Execute HIE command with proper error handling and logging.

    Args:
        command: The command to execute
        session_id: The session ID
        workflow_id: The workflow ID

    Returns:
        Dictionary with execution result
    """
    try:
        # Call local function (defined below) to avoid circular dependency
        execution_result = execute_command(command, session_id, workflow_id)
        return {
            "status": "executed",
            "execution_result": execution_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def update_progressive_ui_event(event_type: str, state: str, question: str, answer: str) -> Dict[str, Any]:
    """
    Update progressive UI with proper error handling and logging.

    Args:
        event_type: The event type
        state: The state
        question: The question
        answer: The answer

    Returns:
        Dictionary with update result
    """
    try:
        # Call local function (defined below) to avoid circular dependency
        progressive_result = update_progressive_ui(event_type, state, question, answer)
        return {
            "status": "updated",
            "progressive_result": progressive_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def save_artifact_data(artifact_type: str, artifact_name: str, artifact_content: str) -> Dict[str, Any]:
    """
    Save artifact with proper error handling and logging.

    Args:
        artifact_type: The artifact type
        artifact_name: The artifact name
        artifact_content: The artifact content

    Returns:
        Dictionary with save result
    """
    try:
        # Call local function (defined below) to avoid circular dependency
        artifact_result = save_artifact(artifact_type, artifact_name, artifact_content)
        return {
            "status": "saved",
            "artifact_result": artifact_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# SHARED MEMORY FOR SAME-MACHINE IPC
class SharedMemory:
    """Shared memory for same-machine IPC"""

    def __init__(self, name, size):
        self.name = name
        self.size = size
        self.memory = bytearray(size)

    def read(self):
        """Read from shared memory"""
        return self.memory

    def write(self, data):
        """Write to shared memory"""
        self.memory = data

# Initialize shared memory for session context
shared_memory = SharedMemory("session_context", 1024)

# DECORATOR FOR SHARED MEMORY CONTEXT
def with_shared_memory_context(func):
    """Decorator to handle shared memory context for functions"""
    def wrapper(data):
        # 1. Read context from shared memory
        context_data = shared_memory.read()

        # 2. Process data with context (call original function)
        processed_data = func(data, context_data)

        # 3. Write context to shared memory
        shared_memory.write(processed_data)

        return processed_data
    return wrapper

# EVENT-SPECIFIC FUNCTIONS
@with_shared_memory_context
def process_hie_event(event, context_data):
    """Process HIE event with context"""
    return process_hie_with_context(event, context_data)

@with_shared_memory_context
def process_progressive_event(event, context_data):
    """Process progressive event with context"""
    return process_progressive_with_context(event, context_data)

@with_shared_memory_context
def process_artifact_event(event, context_data):
    """Process artifact event with context"""
    return process_artifact_with_context(event, context_data)

# EVENT-SPECIFIC PROCESSING FUNCTIONS
def execute_command(command, session_id, workflow_id):
    """Execute HIE command"""
    # Basic implementation - log and return success
    logger.info(f"[HIE] COMMAND: session='{session_id}' | {command}")
    # TODO: Implement actual command execution logic
    return {"success": True, "command": command, "session_id": session_id}

def process_hie_with_context(event, context_data):
    """Process HIE event with context"""
    # HIE-specific processing
    command = event.data.get("command")
    session_id = event.data.get("session_id")
    workflow_id = event.data.get("workflow_id")

    # HIE-specific validation
    if not command:
        raise ValueError("Command is required for HIE event")

    # HIE-specific execution using helper function
    execution_result = execute_hie_command(command, session_id, workflow_id)

    # HIE-specific response
    return {
        "status": "executed",
        "execution_result": execution_result
    }

def update_progressive_ui(event_type, state, question, answer):
    """Update progressive UI"""
    # Basic implementation - log and return success
    # Basic implementation - log and return success
    logger.info(f"[UI] UPDATE: {event_type} | {state}")
    # TODO: Implement actual UI update logic
    return {"success": True, "event_type": event_type, "state": state}

def process_progressive_with_context(event, context_data):
    """Process progressive event with context"""
    # Progressive-specific processing
    event_type = event.data.get("event")
    state = event.data.get("state")
    question = event.data.get("question")
    answer = event.data.get("answer")

    # Progressive-specific validation
    if not event_type:
        raise ValueError("Event type is required for progressive event")

    # Progressive-specific execution using helper function
    progressive_result = update_progressive_ui_event(event_type, state, question, answer)

    # Progressive-specific response
    return {
        "status": "updated",
        "progressive_result": progressive_result
    }

def save_artifact(artifact_type, artifact_name, artifact_content):
    """Save artifact"""
    # Basic implementation - log and return success
    logger.info(f"[ARTIFACT] SAVE: type='{artifact_type}' | name='{artifact_name}' | size={len(str(artifact_content))}")
    # TODO: Implement actual artifact saving logic
    return {"success": True, "artifact_type": artifact_type, "artifact_name": artifact_name}

def process_artifact_with_context(event, context_data):
    """Process artifact event with context"""
    # Artifact-specific processing
    artifact_type = event.data.get("artifact_type")
    artifact_name = event.data.get("artifact_name")
    artifact_content = event.data.get("artifact_content")

    # Artifact-specific validation
    if not artifact_type:
        raise ValueError("Artifact type is required for artifact event")

    # Artifact-specific execution using helper function
    artifact_result = save_artifact_data(artifact_type, artifact_name, artifact_content)

    # Artifact-specific response
    return {
        "status": "saved",
        "artifact_result": artifact_result
    }


@dataclass
class CitationInfo:
    """Citation information for UUID-based LlamaIndex nodes"""
    number: int                    # Sequential number: 1, 2, 3...
    uuid: str                      # LlamaIndex node UUID: "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    title: str                     # Enhanced: "attention-paper.pdf | page 1 | chunk 3"
    content_preview: str           # First 200 chars of node.text
    metadata: Dict[str, Any]       # Full node metadata for display
    url: str                       # API endpoint: "/api/workflow/{workflow}/citations/{uuid}/view"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "number": self.number,
            "uuid": self.uuid,
            "title": self.title,
            "content_preview": self.content_preview,
            "metadata": self.metadata,
            "url": self.url
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CitationInfo':
        """Create from dictionary"""
        return cls(
            number=data["number"],
            uuid=data["uuid"],
            title=data["title"],
            content_preview=data["content_preview"],
            metadata=data["metadata"],
            url=data["url"]
        )


def _preprocess_citations(response_text: str, source_nodes: List[Any]) -> tuple[str, List[CitationInfo]]:
    """
    Process citations from LlamaIndex UUID-based nodes.

    RAW: "The transformer architecture [citation:f47ac10b-58cc-4372-a567-0e02b2c3d479] revolutionized NLP."
    PROCESSED: Direct transformation to HTML anchors (no intermediate [1] text)

    Args:
        response_text: RAW LLM response with [citation:uuid] markers
        source_nodes: List of NodeWithScore objects from retrieval

    Returns:
        Tuple of (processed_html_text, citation_map)
    """
    citation_counter = 0
    citation_map = []

    # Extract citation UUIDs from RAW response
    citation_pattern = r'\[citation:([^\]]+)\]'
    matches = re.findall(citation_pattern, response_text)

    # Create node lookup by UUID
    node_lookup = {getattr(node, 'node', node).node_id: node for node in source_nodes}

    for citation_uuid in matches:
        if any(c.uuid == citation_uuid for c in citation_map):
            continue

        citation_counter += 1
        node = node_lookup.get(citation_uuid)

        if node:
            # Enhanced title with metadata
            actual_node = getattr(node, 'node', node)
            metadata = getattr(actual_node, 'metadata', {})

            title_parts = []
            if metadata.get('source'):
                title_parts.append(metadata['source'])
            if metadata.get('page'):
                title_parts.append(f"page {metadata['page']}")
            if metadata.get('chunk_id'):
                title_parts.append(f"chunk {metadata['chunk_id']}")

            title = " | ".join(title_parts) if title_parts else f"Source {citation_counter}"

            citation_info = CitationInfo(
                number=citation_counter,
                uuid=citation_uuid,
                title=title,
                content_preview=getattr(actual_node, 'text', '')[:200] + '...',
                metadata=metadata,
                url=f"/api/workflow/{{workflow_id}}/citations/{citation_uuid}/view"
            )
        else:
            citation_info = CitationInfo(
                number=citation_counter,
                uuid=citation_uuid,
                title=f"Source {citation_counter}",
                content_preview="Content not available in retrieved nodes",
                metadata={},
                url=f"/api/workflow/{{workflow_id}}/citations/{citation_uuid}/view"
            )

        citation_map.append(citation_info)

        # Replace [citation:uuid] with HTML anchor (no intermediate [1] text)
        html_anchor = f'<a href="javascript:window.richTextRenderer.openCitationPopup(\'{citation_uuid}\');" class="citation-link" data-citation-id="{citation_uuid}" title="{citation_info.title}">[{citation_counter}]</a>'
        response_text = response_text.replace(f'[citation:{citation_uuid}]', html_anchor)

    return response_text, citation_map


class WorkflowExecutionError(Exception):
    """Standardized workflow execution errors"""

    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code  # "VALIDATION_ERROR", "EXECUTION_FAILED", "SESSION_ERROR", etc.
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")


class WorkflowMetrics:
    """Centralized execution monitoring and metrics"""

    def __init__(self):
        self.execution_counts: Dict[str, int] = {}
        self.execution_times: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = {}
        self.last_execution: Dict[str, datetime] = {}

    def record_execution(self, workflow_id: str, duration: float, success: bool):
        """Record execution metrics"""
        self.execution_counts[workflow_id] = self.execution_counts.get(workflow_id, 0) + 1
        self.execution_times[workflow_id] = self.execution_times.get(workflow_id, 0) + duration
        self.last_execution[workflow_id] = datetime.now()

        if not success:
            self.error_counts[workflow_id] = self.error_counts.get(workflow_id, 0) + 1

    def get_execution_stats(self, workflow_id: str) -> Dict[str, Any]:
        """Get execution statistics for a workflow"""
        count = self.execution_counts.get(workflow_id, 0)
        total_time = self.execution_times.get(workflow_id, 0)
        errors = self.error_counts.get(workflow_id, 0)

        return {
            "total_executions": count,
            "average_time": total_time / count if count > 0 else 0,
            "error_rate": errors / count if count > 0 else 0,
            "last_execution": self.last_execution.get(workflow_id)
        }


# Global metrics instance
workflow_metrics = WorkflowMetrics()


class WorkflowExecutor:
    """
    Simplified workflow execution service with single entry point

    Simplified WebSocket Architecture & Eliminated Context Conversion

    This class provides a single streamlined interface for executing workflows
    using direct WorkflowSession integration with no context conversion complexity.
    """

    @staticmethod
    async def execute_workflow_request(
        workflow_id: str,
        user_message: str,
        request_state: Any,
        session_id: Optional[str] = None,
        logger_instance: Optional[Any] = None,
        ui_event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    ) -> Dict[str, Any]:
        """
        Single entry point for all workflow execution requests

        Args:
            workflow_id: The workflow identifier (e.g., 'A_agentic_rag')
            user_message: The user's input message
            request_state: Request state object containing user config
            session_id: Optional existing session ID
            logger_instance: Optional logger instance

        Returns:
            Standardized response dictionary

        Raises:
            WorkflowExecutionError: For execution failures
        """
        start_time = time.time()
        actual_logger = logger_instance or logger

        try:
            # Phase 1: Validation
            await WorkflowExecutor._validate_request(workflow_id, user_message, request_state)

            # Phase 2: Get configuration
            workflow_config = get_workflow_config(workflow_id)

            # Phase 3: Create execution context
            execution_context = await WorkflowExecutor._create_execution_context(
                workflow_id, user_message, request_state, session_id, workflow_config
            )

            # Phase 4: Execute workflow with event-specific processing
            actual_logger.info(f"[{workflow_id}] EXECUTE: user='{getattr(request_state, 'user_id', 'unknown')}' | query='{user_message[:50]}...'")

            # Initialize shared memory for this execution
            execution_shared_memory = SharedMemory(f"execution_{workflow_id}_{session_id}", 2048)

            # Execute workflow and process events with event-specific functions
            execution_result = await execute_workflow(
                workflow_config=workflow_config,
                execution_context=execution_context,
                logger=actual_logger,
                ui_event_callback=ui_event_callback
            )

            # Phase 5: Process and save results
            response_data = await WorkflowExecutor._process_execution_result(
                execution_result, execution_context, workflow_config, request_state
            )

            # Phase 5.5: Update active session (session with new content becomes active)
            if execution_context.session and execution_context.session.chat_manager:
                try:
                    # DEBUG: Log session_file_id before active session update
                    chat_manager = execution_context.session.chat_manager
                    execution_context.session.chat_manager.set_active_session(
                        workflow_id, chat_manager.session_file_id
                    )
                    actual_logger.info(f"Active session updated: {workflow_id} -> {chat_manager.session_file_id}")
                except Exception as active_session_error:
                    actual_logger.error(f"Failed to update active session for {workflow_id}: {active_session_error}")

            # Phase 6: Record metrics
            duration = time.time() - start_time
            workflow_metrics.record_execution(workflow_id, duration, True)

            actual_logger.info(f"[{workflow_id}] REQUEST_COMPLETE: duration={duration:.2f}s")
            return response_data

        except WorkflowExecutionError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            workflow_metrics.record_execution(workflow_id, duration, False)

            actual_logger.error(f"💥 WORKFLOW EXECUTION FAILED: {workflow_id} - {str(e)}")
            raise WorkflowExecutionError(
                code="EXECUTION_FAILED",
                message=f"Workflow execution failed: {str(e)}",
                details={"workflow_id": workflow_id, "error_type": type(e).__name__}
            )

    @staticmethod
    async def _validate_request(workflow_id: str, user_message: str, request_state: Any = None):
        """Validate incoming request parameters"""
        if not workflow_id or not workflow_id.strip():
            raise WorkflowExecutionError(
                code="VALIDATION_ERROR",
                message="Workflow ID is required",
                details={"provided_workflow_id": workflow_id}
            )

        # Allow empty messages for HITL workflow continuation or internal workflow requests
        if not user_message or not user_message.strip():
            # Check if this is a HITL workflow continuation request (dict with event_type)
            # Check for object attributes (MockRequestState, etc.)
            if hasattr(request_state, 'session_handler') or hasattr(request_state, 'user_config'):
                # Allow requests from internal workflow execution (WebSocket, etc.)
                # Don't modify user_message - let it be empty for internal execution
                pass
            else:
                raise WorkflowExecutionError(
                    code="VALIDATION_ERROR",
                    message="User message is required and cannot be empty"
                )

    @staticmethod
    async def _create_execution_context(
        workflow_id: str,
        user_message: str,
        request_state: Any,
        session_id: Optional[str],
        workflow_config: Any
    ) -> ExecutionContext:
        """
        SIMPLIFIED ARCHITECTURE: Direct WorkflowSession integration

        PHASE 3: Eliminate context conversion - WorkflowSession IS the context
        PHASE 2: Simplify WebSocket architecture - single execution path
        """
        try:
            # Get WorkflowSession from request state (required for all execution paths)
            workflow_session = getattr(request_state, 'session_handler', None)
            if not workflow_session:
                raise WorkflowExecutionError(
                    code="SESSION_ERROR",
                    message="WorkflowSession required for execution"
                )

            # PHASE 3: ELIMINATE CONTEXT CONVERSION
            # WorkflowSession contains all necessary data - no conversion needed
            execution_context = ExecutionContext(
                user_message=user_message,
                chat_memory=workflow_session.chat_memory,
                logger=logger,

                # PHASE 3: Direct WorkflowSession integration (no duplication)
                user_config=workflow_session.user_config,
                workflow_config=workflow_session.workflow_config_data,
                workflow_factory=workflow_session.workflow_factory_func,
                session=workflow_session,  # WorkflowSession serves as session
                chat_manager=workflow_session.chat_manager
            )

            # Direct Session Integration
            return execution_context

        except WorkflowExecutionError:
            raise
        except Exception as e:
            raise WorkflowExecutionError(
                code="CONTEXT_CREATION_FAILED",
                message=f"Failed to create execution context: {str(e)}",
                details={"workflow_id": workflow_id, "session_id": session_id}
            )

    @staticmethod
    async def _process_execution_result(
        execution_result: Dict[str, Any],
        execution_context: ExecutionContext,
        workflow_config: Any,
        request_state: Any
    ) -> Dict[str, Any]:
        """Process execution result and save to session"""
        try:
            # Extract result components
            workflow_response = execution_result.get('response', '')
            artifacts = execution_result.get('artifacts', [])
            enhanced_metadata = execution_result.get('enhanced_metadata', {})

            # Generate synthetic response if needed
            if not workflow_response.strip():
                num_artifacts = len(artifacts) if artifacts else 0
                display_name = getattr(workflow_config, 'display_name', getattr(workflow_config, 'workflow_ID', 'Workflow'))
                if num_artifacts > 0:
                    workflow_response = f"✅ **{display_name} Complete!** Generated {num_artifacts} result{'s' if num_artifacts > 1 else ''} (see panel for details)"
                else:
                    workflow_response = f"✅ **{display_name} Complete!** Request processed successfully"

            # Process citations if present in the response
            source_nodes = execution_result.get('source_nodes', [])
            if source_nodes and workflow_response:
                try:
                    # Apply citation processing: RAW [citation:uuid] → HTML anchors
                    processed_response, citations = _preprocess_citations(workflow_response, source_nodes)
                    workflow_response = processed_response

                    # Add citations to enhanced metadata
                    if citations:
                        enhanced_metadata['citations'] = citations
                    if citations:
                        enhanced_metadata['citations'] = citations
                        enhanced_metadata['citation_display_mode'] = getattr(workflow_config, 'show_citation', 'Short')

                        # NEW: Also populate citation_metadata field for frontend compatibility
                        citation_metadata = {}
                        for citation in citations:
                            citation_metadata[citation.uuid] = {
                                'file_name': citation.title.split(' | ')[0] if ' | ' in citation.title else citation.title,
                                'page': citation.metadata.get('page'),
                                'size': citation.metadata.get('size'),
                                'content_preview': citation.content_preview
                            }
                        enhanced_metadata['citation_metadata'] = citation_metadata

                    # PHASE 4: Add all workflow UI configuration options to enhanced_metadata
                    # These are standard display flags that control the chat window behavior
                    enhanced_metadata['ui_component'] = getattr(workflow_config, 'ui_component', 'SimpleWorkflowProgress')
                    enhanced_metadata['show_citation'] = getattr(workflow_config, 'show_citation', 'Short')
                    enhanced_metadata['show_tool_calls'] = getattr(workflow_config, 'show_tool_calls', True)
                    enhanced_metadata['show_followup_questions'] = getattr(workflow_config, 'show_followup_questions', True)
                    enhanced_metadata['show_workflow_states'] = getattr(workflow_config, 'show_workflow_states', True)
                    enhanced_metadata['artifacts_enabled'] = getattr(workflow_config, 'artifacts_enabled', True)

                except Exception as citation_error:
                    logger.warning(f"Citation processing failed: {citation_error}")
                    # Continue without citation processing if it fails

            # Save to session using ChatBotSession capabilities (ChatHistoryManager is internal)
            message_id = None
            session = getattr(execution_context, 'session', None)
            if session:
                # Use ChatBotSession's chat persistence capabilities
                # Session automatically manages ChatHistoryManager internally
                try:
                    # Save user message if not already saved
                    user_message = execution_context.user_message

                    # CORRECTED: Use unified ChatHistoryManager APIs instead of incorrect chat_session_data access
                    # FIXED: Ensure consistent message saving - save_workflow_conversation_turn handles both user and AI messages for artifacts
                    if artifacts:
                        # Use unified save_workflow_conversation_turn for complete conversation turns with artifacts
                        session.chat_manager.save_workflow_conversation_turn(
                            workflow_id=getattr(workflow_config, 'workflow_ID', None),
                            session_id=session.session_id,
                            user_message=user_message,
                            ai_response=workflow_response,
                            artifacts=artifacts,
                            workflow_config=workflow_config,
                            enhanced_metadata=enhanced_metadata
                        )
                    else:
                        # Save both user and AI messages consistently for non-artifact workflows
                        # Relaxed deduplication: Only skip if the VERY LAST message is the same user query
                        is_duplicate = False
                        if session.messages:
                            last_msg = session.messages[-1]
                            if last_msg.role == MessageRole.USER and last_msg.content == user_message:
                                is_duplicate = True

                        current_wf_id = getattr(workflow_config, 'workflow_ID', None)
                        if not is_duplicate:
                            user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
                            session.chat_manager.add_message_to_session_data(user_msg, workflow_id=current_wf_id)

                        # Save AI response without artifacts using unified API
                        ai_msg = create_chat_message(
                            role=MessageRole.ASSISTANT,
                            content=workflow_response,
                            enhanced_metadata=enhanced_metadata
                        )
                        session.chat_manager.add_message_to_session_data(ai_msg, workflow_id=current_wf_id)

                    # Get message_id from session (independent of save method) / the last saved message
                    if session.messages:
                        last_msg = session.messages[-1]
                        if last_msg and hasattr(last_msg, 'message_id'):
                            message_id = last_msg.message_id

                except Exception as save_error:
                    logger.warning(f"Failed to save chat messages through session: {save_error}")
                    # Continue without message_id

            # Format standardized response
            session_id = execution_context.session.session_id if execution_context.session else None
            return {
                "session_id": session_id,
                "message_id": message_id,  # Now includes the actual message ID from saved message
                "response": workflow_response,
                "artifacts": artifacts if artifacts else None,
                "enhanced_metadata": enhanced_metadata,
                "workflow": execution_context.workflow_config.display_name if execution_context.workflow_config else workflow_config.workflow_ID,
                "timestamp": datetime.now().isoformat() + "Z",
                "execution_time": execution_result.get('execution_time', 0.0),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to process execution result: {str(e)}")
            raise WorkflowExecutionError(
                code="RESULT_PROCESSING_FAILED",
                message=f"Failed to process execution result: {str(e)}"
            )



    # PHASE 2: REMOVED execute_workflow_with_session
    # Single execution path through execute_workflow_request eliminates duplication

    @staticmethod
    def get_execution_metrics(workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """Get execution metrics"""
        if workflow_id:
            return workflow_metrics.get_execution_stats(workflow_id)
        else:
            # Return metrics for all workflows
            return {
                workflow_id: workflow_metrics.get_execution_stats(workflow_id)
                for workflow_id in workflow_metrics.execution_counts.keys()
            }
