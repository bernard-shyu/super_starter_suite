"""
Workflow Execution Engine

Core execution functions for running workflows with unified interface.
Handles both adapted (STARTER_TOOLS) and ported workflows.
"""

import time
from typing import Callable, Any, Dict, Type, Tuple, List, Optional
from datetime import datetime
from super_starter_suite.chat_bot.workflow_execution.artifact_utils import extract_artifact_metadata
from super_starter_suite.chat_bot.workflow_execution.ui_enhancer import enhance_workflow_execution_for_ui
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.dto import WorkflowConfig, ExecutionContext, ExecutionResult, StructuredMessage, MessageMetadata
from super_starter_suite.shared.workflow_utils import create_structured_message
from super_starter_suite.shared.llama_utils import init_llm
from llama_index.server.api.models import ArtifactEvent
from llama_index.core import Settings

# UNIFIED LOGGING SYSTEM
workflow_logger = config_manager.get_logger("workflow.executor")

# THREAD-LOCAL STORAGE for execution context (to support ported workflows)
import threading
_execution_context_local = threading.local()

def _set_current_execution_context(execution_context):
    """Set the current execution context for ported workflows to access"""
    _execution_context_local.execution_context = execution_context

def _get_current_execution_context():
    """Get the current execution context (for ported workflows)"""
    return getattr(_execution_context_local, 'execution_context', None)


async def process_workflow_events(handler, workflow_config: WorkflowConfig, session_id: Optional[str] = None, ui_event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None) -> Tuple[str, List[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]], List[Any]]:
    """
    Generic workflow event processing for consistent artifact extraction and response handling.

    This function processes ALL events during workflow execution, including artifacts sent after StopEvent,
    to handle workflows where artifacts are generated after completion (like deep_research).

    Detection and interception of CLIHumanInputEvent prevents blocking await handler call for HITL workflows.

    Args:
        handler: Async workflow handler from workflow.run()
        workflow_config: Complete workflow configuration with display_name, workflow_ID, hie_enabled
        session_id: Session identifier for WebSocket broadcasting
        ui_event_callback: Optional callback for UI event streaming

    Returns:
        Tuple of (conversation_response, artifacts_collected, planning_response, hie_data)
        Where hie_data is populated if CLIHumanInputEvent was intercepted during streaming
    """
    artifacts_collected = []
    source_nodes = []
    response_content = ""
    planning_response = ""
    hie_data = None  # Initialize hie_data for proper context preservation

    workflow_name = workflow_config.display_name
    workflow_id = workflow_config.workflow_ID

    # Process ALL events - don't stop on StopEvent, continue to catch delayed artifacts
    async for event in handler.stream_events():
        event_type = type(event).__name__
        # LOGGING BALANCED PRECISION: Variable info on 1 line (metadata), critical content on separate line.
        # Silencing noisy generic "Processing event" logs in regular operation.
        # workflow_logger.debug(f"[{workflow_name}] Processing event: {event_type}")

        try:
            # Generic UIEvent processing - attribute-wise, not state-wise
            from llama_index.server.api.models import UIEvent
            if isinstance(event, UIEvent) and hasattr(event, 'data'):
                planning_response = _process_ui_event_attributes(event, workflow_name, planning_response)

                # Call UI event callback if provided (for WebSocket streaming)
                if ui_event_callback:
                    try:
                        # Extract event data for callback - handle unified UIEventData with progressive conversion
                        event_data = {}
                        # Unified conversion for all UIEventData formats (both ported and adapted workflows)
                        event_data = _convert_ui_event_to_progressive(event.data, workflow_logger)
                        # Standard progressive event streaming (Standardized format)
                        await ui_event_callback('progressive_event', event_data)
                    except Exception as callback_error:
                        import traceback
                        workflow_logger.warning(f"[{workflow_name}] UI callback traceback: {traceback.format_exc()}")
                else:
                    workflow_logger.debug(f"[{workflow_name}] No UI event callback provided - skipping progressive event streaming")

            # Generic ArtifactEvent processing - capture artifacts ANYTIME during execution
            elif isinstance(event, ArtifactEvent):
                try:
                    artifact_data = extract_artifact_metadata(event.data)
                    artifacts_collected.append(artifact_data)
                    workflow_logger.info(f"[{workflow_name}] ARTIFACT: {artifact_data['type']} ({len(artifact_data.get('content', ''))} chars)")

                except IndexError as idx_error:
                    workflow_logger.error(f"[{workflow_name}] LIST INDEX ERROR in artifact extraction: {idx_error}")
                    workflow_logger.error(f"[{workflow_name}] Event data type: {type(event.data)}")
                    workflow_logger.error(f"[{workflow_name}] Event data repr: {repr(event.data)}")
                    # Log the full traceback for debugging
                    import traceback
                    workflow_logger.error(f"[{workflow_name}] Full traceback: {traceback.format_exc()}")
                    # Skip this bad artifact and continue processing
                    continue
                except Exception as e:
                    workflow_logger.error(f"[{workflow_name}] Artifact extraction failed: {e}")
                    import traceback
                    workflow_logger.error(f"[{workflow_name}] Full traceback: {traceback.format_exc()}")

            # Track StopEvent but continue processing (artifacts may come after)
            elif 'StopEvent' in event_type:
                workflow_logger.debug(f"[{workflow_name}] STOP: Handler finished (awaiting delayed artifacts)")

            # 🚨 HIE INTERCEPTION (Human Input Event) - Delegated to human_input module
            elif event_type == 'CLIHumanInputEvent' and getattr(workflow_config, 'hie_enabled', False):
                # Import and delegate HIE input event processing - PRESERVE SESSION CONTEXT
                try:
                    from super_starter_suite.chat_bot.human_input.hie_event_processor import process_hie_input_event
                    hie_data = await process_hie_input_event(event, workflow_config, session_id, ui_event_callback)
                    if hie_data:
                        workflow_logger.info(f"[{workflow_name}] HIE intercepted - continuing to preserve session context")
                        # DO NOT RETURN EARLY - Preserve session context for complete workflow execution
                        # hie_data handling moved to process_workflow_response() level
                        hie_intercepted = True  # Flag for downstream processing
                except ImportError as import_error:
                    workflow_logger.error(f"[{workflow_name}] Failed to import HIE processor: {import_error}")
                except Exception as proc_error:
                    workflow_logger.error(f"[{workflow_name}] HIE input processing failed: {proc_error}")

            # 🚨 HIE RESPONSE PROCESSING - Delegated to human_input module
            elif event_type == 'CLIHumanResponseEvent' and getattr(workflow_config, 'hie_enabled', False):
                # Import and delegate HIE response processing
                try:
                    from super_starter_suite.chat_bot.human_input.hie_event_processor import process_hie_response_event
                    await process_hie_response_event(event, workflow_config, ui_event_callback)
                except ImportError as import_error:
                    workflow_logger.error(f"[{workflow_name}] Failed to import HIE processor: {import_error}")
                except Exception as proc_error:
                    workflow_logger.error(f"[{workflow_name}] HIE response processing failed: {proc_error}")

            # Fallback for streaming content
            elif hasattr(event, 'delta') and event.delta:
                response_content += event.delta
            elif hasattr(event, 'content') and event.content:
                response_content += event.content

            # 🛠️ AGENT EVENTS: Handle agent-related events to prevent "Unknown event type" logs
            elif event_type in ["AgentStream", "AgentInput", "AgentSetup", "AgentToolCall", "AgentToolOutput", "AgentOutput", "ToolCall", "ToolCallResult", "AgentRunEvent"]:
                # Log metadata succinctly
                if event_type in ["AgentToolCall", "AgentToolOutput", "ToolCall", "ToolCallResult"]:
                    workflow_logger.debug(f"[{workflow_name}] AGENT_{event_type.upper()}: (id={getattr(event, 'tool_id', 'N/A')})")
                
                # Separate line for content if it exists
                if hasattr(event, "content") and event.content:
                    workflow_logger.debug(f"[{workflow_name}] CONTENT: {str(event.content)[:100]}...")
            
            # 🛠️ SOURCE NODES: Handle retrieval results
            elif event_type == "SourceNodesEvent":
                nodes = getattr(event, 'nodes', [])
                source_nodes.extend(nodes)
                workflow_logger.debug(f"[{workflow_name}] RETRIEVAL: {len(nodes)} nodes found")

            else:
                # Truncate repr to prevent terminal bloat
                event_repr = repr(event)
                if len(event_repr) > 500:
                    event_repr = event_repr[:500] + "..."
                workflow_logger.error(f"[{workflow_name}] ERROR: Unknown event '{event_type}' | Event: {event_repr}")

        except IndexError as idx_error:
            workflow_logger.error(f"[{workflow_name}] INDEX ERROR: {idx_error},  Event type: {event_type}, event: {repr(event)}")
            # Skip this bad event and continue processing
            continue
        except Exception as event_error:
            workflow_logger.error(f"[{workflow_name}] ERROR processing event {event_type}: {event_error}")
            # Log full traceback for debugging
            import traceback
            workflow_logger.error(f"[{workflow_name}] Event processing traceback: {traceback.format_exc()}")
            continue

    workflow_logger.debug(f"[{workflow_name}] Event processing complete: {len(artifacts_collected)} artifacts collected, {len(source_nodes)} nodes collected")
    return response_content, artifacts_collected, planning_response, hie_data, source_nodes

def _convert_ui_event_to_progressive(event_data, logger) -> Dict[str, Any]:
    """
    Convert UIEventData to progressive frontend format.

    Handles adapted workflow format: event/state/id/question/answer
    Output: Message-driven progressive frontend format
    """
    progressive_data = {}

    # Handle both Pydantic objects and dict data
    def get_value(key):
        if isinstance(event_data, dict):
            return event_data.get(key, None)
        else:
            return getattr(event_data, key, None)

    # Handle adapted workflow format (current deep research workflows)
    event_type = get_value('event')
    state = get_value('state')
    event_id = get_value('id')
    question = get_value('question')
    answer = get_value('answer')

    if event_type and state:
        # Message-driven UI - Backend defines generic actions for dynamic UI structure
        progressive_data['event'] = event_type
        progressive_data['status'] = state

        # Generic message content (language/workflow agnostic) - fallback to default for simple panels
        message_parts = []
        if question: message_parts.append(question)
        if answer: message_parts.append(answer)
        if message_parts:
            progressive_data['message'] = ' | '.join(message_parts)
        else:
            # Generate meaningful default messages for simple panels that lack question/answer
            if event_type == 'retrieve':
                progressive_data['message'] = 'Retrieving relevant information...'
            elif event_type == 'analyze':
                progressive_data['message'] = 'Analyzing retrieved information...'
            elif event_type == 'answer':
                progressive_data['message'] = 'Generating answers...'
            else:
                progressive_data['message'] = f'{event_type.capitalize()} in progress...'

        if event_type == 'answer':
            # PHASE 5: Backend defines semantic actions for nested UI structure
            # Track state across events to properly handle nested panels
            current_context = _get_current_execution_context()
            if current_context == 'answer_panel_created' and event_id:
                # Sub-panels: Add question-specific panels within the nested container
                progressive_data['action'] = 'update_nested'
                progressive_data['panel_id'] = f"answer.{event_id}"
                # Message has the question text for sub-panel display
            else:
                # First answer event: Create the nested container
                _set_current_execution_context('answer_panel_created')
                progressive_data['action'] = 'create_nested'
                progressive_data['panel_id'] = 'answer'
        else:
            # Standard single panels
            progressive_data['action'] = 'create_panel'
            progressive_data['panel_id'] = event_type

        # Balanced precision: Metadata on 1-line, detail only if needed
        # logger.debug(f"[{event_type}/{state}] -> UI_ACTION: {progressive_data.get('action')}")

    # Remove any empty values to keep the data clean
    progressive_data = {k: v for k, v in progressive_data.items() if v is not None and str(v).strip()}

    return progressive_data

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

    # Extract conversational/planning content from text attributes
    text_attributes = ['requirement', 'analysis', 'findings', 'summary', 'content', 'description', 'message']
    conversational_text = None

    for attr_name in text_attributes:
        if attr_name in data_attrs and isinstance(data_attrs[attr_name], str) and data_attrs[attr_name].strip():
            conversational_text = data_attrs[attr_name]
            break

    # Format conversational text for better display if found
    if conversational_text:
        # Format lists and improve readability
        formatted_response = conversational_text.replace('. ', '\n• ').replace(', ', '\n• ')
        planning_response = formatted_response
        workflow_logger.debug(f"[{workflow_name}] Conversational response captured: {len(planning_response)} characters")

    return planning_response


# 🎯 UNIFIED WORKFLOW EXECUTION: Consolidated function replaces execute_adapted_simple + execute_ported_logic
# 80% parameter reduction: from 8 parameters to 3 unified objects

async def execute_workflow(
    workflow_config: WorkflowConfig,
    execution_context: ExecutionContext,
    logger: Optional[Any] = None,
    ui_event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
) -> Dict[str, Any]:
    """
    🎯 UNIFIED WORKFLOW EXECUTOR: Single entry point for all workflow types

    Eliminates parameter explosion by consolidating execution context:

    BEFORE: 8+ parameters
    execute_adapted_simple( workflow_factory, workflow_config, user_message, user_config, chat_manager, session, chat_memory, logger)
    execute_ported_logic(   workflow_factory, workflow_config, user_message, user_config, chat_manager, session, chat_memory, logger)

    AFTER: 3 unified parameters
    execute_workflow(workflow_config, execution_context, logger=None)

    Routing determined by workflow_config.integrate_type:
    - "adapted" → STARTER_TOOLS native execution (citations/artifacts preserved)
    - "ported" → Custom business logic reimplementation

    Args:
        workflow_config: Complete workflow config + injected factory
        execution_context: Consolidated execution parameters
        logger: Optional logger override

    Returns:
        Dict: Unified response format across all workflow types

    Raises:
        ValueError: Unknown integrate_type
    """
    import time
    start_time = time.time()

    # 🎯 DETERMINE LOGGER
    actual_logger = logger or workflow_logger

    try:
        # 🎯 ROUTE BY INTEGRATION TYPE (pre-determined by config, no runtime if-else)
        integrate_type = workflow_config.integrate_type or "adapted"

        actual_logger.debug(f"🎯 Executing {integrate_type} workflow: {workflow_config.display_name} ({workflow_config.workflow_ID})")

        # 🎯 INITIALIZE USER DATA PATH: Set up workflow-specific working directory
        workflow_config.set_user_data_path(execution_context.user_config)

        # Set execution context for ported workflows to access
        _set_current_execution_context(execution_context)

        # 🎯 EXECUTE WORKFLOW HANDLER
        handler = await execute_workflow_handler(workflow_config, execution_context, actual_logger, integrate_type)

        # 🔄 PROCESS RESPONSE
        result = await process_workflow_response(workflow_config, execution_context, actual_logger, handler, ui_event_callback)

        # ✅ LOG SUCCESS
        execution_time = time.time() - start_time
        actual_logger.info(f"[{workflow_config.workflow_ID}] COMPLETE: {workflow_config.display_name} in {execution_time:.2f}s")

        return result

    except Exception as e:
        execution_time = time.time() - start_time
        actual_logger.error(f"❌ Workflow execution failed ({execution_time:.2f}s): {workflow_config.display_name} - {str(e)}")

        return {
            "response": f"Workflow execution failed: {str(e)}",
            "artifacts": [],
            "enhanced_metadata": {}
        }

async def execute_workflow_handler(workflow_config: WorkflowConfig, execution_context: ExecutionContext, logger: Any, integrate_type: str):
    """Create and execute workflow handler for specified integration type"""
    user_message = execution_context.user_message
    chat_memory = execution_context.chat_memory

    if integrate_type == "adapted":
        # 🛡️ SAFETY NET: Ensure LLM is initialized for adapted workflows
        if execution_context.user_config:
            # Pass force_text_mode from workflow configuration (Solution F)
            force_text = getattr(workflow_config, 'force_text_structured_predict', False)
            init_llm(execution_context.user_config, force_text_mode=force_text)
            logger.debug(f"[EXECUTION] LLM initialized for adapted workflow {workflow_config.workflow_ID} (force_text={force_text})")

        # 🎯 ADAPTED WORKFLOWS: Call create_workflow(chat_request, timeout)
        workflow_factory = workflow_config.workflow_factory
        if workflow_factory is None:
            raise ValueError(f"No workflow_factory injected for {workflow_config.workflow_ID}")

        chat_request = execution_context.create_chat_request()
        timeout_seconds = getattr(workflow_config, 'timeout', 90.0)
        workflow = workflow_factory(chat_request, timeout_seconds)

        # 🏷️ HITL WORKFLOW INSTANCE REGISTRATION (HIE-enabled workflows only)
        from super_starter_suite.chat_bot.human_input.hitl_workflow_manager import register_hitl_workflow_instance, cleanup_expired_instances
        if getattr(workflow_config, 'hie_enabled', False) and workflow_config.workflow_ID:
            session_id = execution_context.session.session_id if execution_context.session else None
            if session_id:
                register_hitl_workflow_instance(workflow_config.workflow_ID, session_id, workflow)
                logger.debug(f"[{workflow_config.display_name}] Registered HITL workflow instance")

                # Only run cleanup for actual HITL workflows (not non-HITL workflows)
                try:
                    cleanup_count = cleanup_expired_instances()
                    if cleanup_count > 0:
                        logger.info(f"[HITL] Cleaned up {cleanup_count} expired workflow instances")
                except Exception as e:
                    logger.debug(f"[{workflow_config.display_name}] HITL cleanup skipped: {e}")
            else:
                logger.warning(f"[{workflow_config.display_name}] Cannot register HITL workflow - no session ID")

        handler = workflow.run(
            user_msg=user_message,
            chat_history=chat_memory.get('messages', []) if chat_memory else None,
            max_iterations=50
        )

    elif integrate_type == "ported":
        # 🎯 PORTED WORKFLOWS: Standard workflow execution
        workflow_factory = workflow_config.workflow_factory
        if workflow_factory is None:
            raise ValueError(f"No workflow_factory injected for {workflow_config.workflow_ID}")

        chat_request = execution_context.create_chat_request()
        timeout_seconds = getattr(workflow_config, 'timeout', 90.0)
        workflow = workflow_factory(chat_request, timeout_seconds)

        handler = workflow.run(
            user_msg=user_message,
            chat_history=chat_memory.get('messages', []) if chat_memory else None
        )

    elif integrate_type == "meta":
        # 🎭 META: Multi-agent orchestration workflows
        workflow_factory = workflow_config.workflow_factory
        if workflow_factory is None:
            raise ValueError(f"No workflow_factory injected for {workflow_config.workflow_ID}")

        chat_request = execution_context.create_chat_request()
        timeout_seconds = getattr(workflow_config, 'timeout', 300.0)
        
        # Meta workflows typically need user_config for sub-agent coordination
        workflow = workflow_factory(
            chat_request=chat_request, 
            timeout_seconds=timeout_seconds,
            user_config=execution_context.user_config
        )

        handler = workflow.run(
            query=user_message,
            chat_history=chat_memory.get('messages', []) if chat_memory else None
        )

    else:
        raise ValueError(f"Unknown integrate_type: {integrate_type}")

    return handler

async def process_workflow_response(workflow_config: WorkflowConfig, execution_context: ExecutionContext, logger: Any, handler, ui_event_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """Process workflow events and create final response"""


    # �🔍 OBSERVATION-ONLY PROCESSING: Collect without callback interference
    response_content, artifacts_collected, planning_response, hie_info, source_nodes = await process_workflow_events(
        handler, workflow_config, execution_context.session.session_id if execution_context.session else None, ui_event_callback
    )

    # 🚨 CHECK FOR HIE INTERCEPTION - WORKFLOW SHOULD COMPLETE WITHOUT CONTINUING
    if hie_info and hie_info.get("HIE_intercepted"):
        logger.info(f"[{workflow_config.display_name}] HIE intercepted during streaming - workflow should complete here: {hie_info.get('HIE_command', '')}")

        # Generate completion response for HIE interception
        hie_response = f"✅ **Human-in-the-Loop Command Ready**\n\nThe workflow has prepared a CLI command that requires your approval:\n\n**Command:** `{hie_info['HIE_command']}`\n\nPlease review and approve the command in the modal dialog."

        return {
            "response": hie_response,
            "artifacts": artifacts_collected,
            "enhanced_metadata": {
                "HIE_intercepted": True,
                "HIE_type": hie_info.get("HIE_type"),
                "HIE_command": hie_info.get("HIE_command"),
                "workflow_id": hie_info.get("workflow_id"),
                "workflow_completed": True  # Mark workflow as completed
            },
            "hie_active": True,
            "status": "completed"
        }

    # Get workflow result
    final_result = await handler
    logger.debug(f"Workflow execution completed: {type(final_result)}")

    # 🎯 EXTRACT RESPONSE CONTENT FROM final_result
    if not response_content or len(response_content.strip()) < 10:
        from super_starter_suite.shared.workflow_utils import extract_workflow_response_content
        extracted_content = await extract_workflow_response_content(final_result, workflow_config.display_name, logger)
        if extracted_content and len(extracted_content.strip()) >= 10:
            response_content = extracted_content
            logger.info(f"[{workflow_config.display_name}] Used response content from final_result: {len(response_content)} chars")
        else:
            logger.warning(f"[{workflow_config.display_name}] No usable response content found")
            response_content = "Workflow completed but generated no response content. This may indicate an issue with the query or processing."

    # 🎯 ARTIFACT FALLBACK: If nothing collected from events, check final_result
    if not artifacts_collected:
        if hasattr(final_result, 'artifacts') and final_result.artifacts:
            artifacts_collected = final_result.artifacts
            logger.info(f"[{workflow_config.display_name}] Recovered {len(artifacts_collected)} artifacts from final_result attributes")
        elif isinstance(final_result, dict) and 'artifacts' in final_result:
            artifacts_collected = final_result['artifacts']
            logger.info(f"[{workflow_config.display_name}] Recovered {len(artifacts_collected)} artifacts from final_result dict")

    # 🎯 EXTRACT SOURCE NODES fallback from final_result if not collected from events
    if not source_nodes:
        if hasattr(final_result, 'citations') and final_result.citations:
            source_nodes = final_result.citations # Map unified citation term to source_nodes for processing
        elif hasattr(final_result, 'source_nodes') and final_result.source_nodes:
            source_nodes = final_result.source_nodes
        elif isinstance(final_result, dict):
            # Check both keys, preferring 'citations' (unified term)
            source_nodes = final_result.get('citations', final_result.get('source_nodes', []))

    # 🎯 COLLECT ENHANCED METADATA
    enriched_metadata = {}
    
    # 1. Add Model Info from Settings.llm
    current_llm = getattr(Settings, 'llm', None)
    if current_llm:
        enriched_metadata['model_provider'] = getattr(current_llm, '_sss_provider', 'unknown')
        enriched_metadata['model_id'] = getattr(current_llm, '_sss_model_id', 'unknown')
    
    # 2. Merge from final_result (especially for multi-agent pipelines)
    if isinstance(final_result, dict):
        # Propagate fields like pipeline_info, workflow_states, etc.
        for key in ['pipeline_info', 'workflow_states', 'workflow_id', 'agent_id']:
            if key in final_result:
                enriched_metadata[key] = final_result[key]
    
    # 3. Add UI Configuration from workflow_config
    if workflow_config:
        enriched_metadata['ui_component'] = getattr(workflow_config, 'ui_component', 'SimpleWorkflowProgress')
        # Propagate display flags
        for flag in ['show_citation', 'show_tool_calls', 'show_followup_questions', 'show_workflow_states', 'artifacts_enabled']:
            value = getattr(workflow_config, flag, None)
            if value is not None:
                enriched_metadata[flag] = value

    # 🎯 RETURN UNIFIED RESULT
    return {
        "response": response_content,
        "artifacts": artifacts_collected,
        "source_nodes": source_nodes,
        "enhanced_metadata": enriched_metadata,
        "status": "success"
    }


async def save_message_to_session(chat_manager, session, structured_message):
    """Clean session saving without complex workflow logic"""
    try:
        from super_starter_suite.shared.dto import MessageRole, ChatMessageDTO

        assistant_msg = ChatMessageDTO(
            role=MessageRole.ASSISTANT,
            content=structured_message.content,
            enhanced_metadata=structured_message.metadata.to_dict() if structured_message.metadata else {}
        )
        chat_manager.add_message_to_session_data(assistant_msg)
        workflow_logger.debug("Structured message saved to session")
    except Exception as e:
        workflow_logger.error(f"Failed to save message to session: {e}")
