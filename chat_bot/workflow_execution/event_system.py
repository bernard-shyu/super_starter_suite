"""
Workflow Event System - Clean Workflow Event Handling

Phase 5.8: Event-driven architecture for workflow execution transparency

Provides:
- EventCollector: Observes workflow events without interference
- WorkflowEventHandler: Processes events for UI/artifact extraction
- Clean separation between workflow execution and event processing
"""

from typing import Dict, Any, List, Optional
from llama_index.core.workflow.events import Event
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.chat_bot.workflow_execution.artifact_utils import extract_artifact_metadata, validate_artifacts

logger = config_manager.get_logger("workflow.ui_event")


class EventCollector:
    """
    OBSERVATION-ONLY Event Collector

    Observes workflow events without interfering with native STARTER_TOOLS behavior.
    Critical for maintaining artifact/citation preservation in adapted workflows.
    """

    def __init__(self):
        self.artifacts: List[Dict[str, Any]] = []
        self.citations: List[str] = []
        self.ui_events: List[Dict[str, Any]] = []
        self.progress_states: List[str] = []

        # Collection counters
        self.artifact_count = 0
        self.citation_count = 0
        self.ui_event_count = 0

        logger.debug("[EventCollector] Initialized observation-only collector")

    def collect_workflow_event(self, event: Event):
        """
        Process workflow event without interfering

        Maps different event types to collected data:
        - ArtifactEvent → artifacts
        - UIEvent → ui_events/progress_states
        """
        try:
            event_type = getattr(event, 'type', type(event).__name__)

            logger.debug(f"[EventCollector] Processing {event_type} event")

            if hasattr(event, 'data'):
                # Handle Artifact events
                if (hasattr(event, 'type') and getattr(event, 'type') == 'artifact_event') or \
                   type(event).__name__ == 'ArtifactEvent':

                    logger.debug(f"[EventCollector] Collecting artifact event: {event_type}")
                    artifact_data = extract_artifact_metadata(event)
                    if self._is_valid_artifact(artifact_data):
                        self.artifacts.append(artifact_data)
                        self.artifact_count += 1

                # Handle UI state events
                elif hasattr(event, 'data') and hasattr(event.data, 'state'):
                    ui_state = getattr(event.data, 'state', 'unknown')
                    self.ui_events.append({
                        'state': ui_state,
                        'requirement': getattr(event.data, 'requirement', ''),
                        'timestamp': getattr(event, 'created_at', None)
                    })
                    self.progress_states.append(f"{ui_state}: {getattr(event.data, 'requirement', '')}")
                    self.ui_event_count += 1

                    logger.debug(f"[EventCollector] UI state update: {ui_state}")

            elif hasattr(event, 'response') and hasattr(event.response, 'artifacts'):
                # Handle direct artifact responses (ported workflow pattern)
                for artifact_data in event.response.artifacts:
                    artifact_data = extract_artifact_metadata(artifact_data)
                    if self._is_valid_artifact(artifact_data):
                        self.artifacts.append(artifact_data)
                        self.artifact_count += 1

        except Exception as e:
            logger.warning(f"[EventCollector] Failed to process event {type(event).__name__}: {e}")

    def _is_valid_artifact(self, artifact_data: Dict[str, Any]) -> bool:
        """Validate artifact has required content"""
        return bool(
            artifact_data.get('type') and
            (artifact_data.get('code') or artifact_data.get('content'))
        )

    def reset(self):
        """Reset all collected data"""
        self.artifacts.clear()
        self.citations.clear()
        self.ui_events.clear()
        self.progress_states.clear()
        self.artifact_count = 0
        self.citation_count = 0
        self.ui_event_count = 0


class WorkflowEventHandler:
    """
    WORKFLOW EVENT HANDLER - Processes collected events for UI integration

    Handles streaming events from workflow execution and formats them for frontend consumption.
    Key: Extracts artifacts and progress without interfering with native workflow behavior.
    """

    def __init__(self, event_collector: EventCollector, workflow_config: Dict, logger):
        self.event_collector = event_collector
        self.workflow_config = workflow_config
        self.logger = logger
        self.response_content = ""

    def handle_stream_event(self, event):
        """
        Process streaming event from workflow

        Called for each event in workflow stream to observe execution.
        """
        try:
            # Extract any readable response content
            if hasattr(event, 'response'):
                content = getattr(event.response, 'response', '') or \
                         getattr(event.response, 'content', "") or \
                         getattr(event, 'response', "")
                if content and content.strip():
                    self.response_content += content + " "

            # Collect event for artifacts/ui updates
            self.event_collector.collect_workflow_event(event)

        except Exception as e:
            self.logger.warning(f"[WorkflowEventHandler] Stream event processing failed: {e}")

    def extract_response_content(self, final_response) -> str:
        """
        Extract final response content from workflow completion

        Handles different workflow return patterns
        """
        try:
            if hasattr(final_response, 'response'):
                content = getattr(final_response.response, 'response', '') or \
                         getattr(final_response.response, 'content', '')
            elif hasattr(final_response, 'content'):
                content = final_response.content
            else:
                content = str(final_response)

            return content.strip() or self.response_content.strip() or "Workflow completed successfully"

        except Exception as e:
            self.logger.error(f"[WorkflowEventHandler] Response content extraction failed: {e}")
            return "Workflow execution completed"


def validate_workflow_events(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    VALIDATE WORKFLOW EVENTS

    Clean and validate captured artifacts for frontend consumption
    """
    try:
        # Validate and clean artifacts
        validated_artifacts = validate_artifacts(artifacts)

        return {
            'artifacts': validated_artifacts,
            'validation_summary': {
                'total_events': len(artifacts),
                'valid_artifacts': len(validated_artifacts),
                'artifacts_with_content': len([a for a in validated_artifacts if a.get('code') or a.get('content')])
            }
        }

    except Exception as e:
        logger.error(f"[WorkflowEventSystem] Validation failed: {e}")
        return {
            'artifacts': [],
            'validation_summary': {'error': str(e)}
        }


# DARTO COMPATIBILITY - Simple shared utilities only
def create_event_collector():
    """Simple factory for EventCollector - no complex business logic"""
    return EventCollector()


def process_workflow_events(handler, workflow_name: str):
    """
    Process workflow events into final results

    Returns: response_content, artifacts_collected, progress_states
    """
    try:
        artifacts = handler.event_collector.artifacts
        response_content = handler.response_content
        progress_states = handler.event_collector.progress_states

        logger.info(f"[WorkflowEventSystem] Processed workflow {workflow_name}: {len(artifacts)} artifacts, {len(progress_states)} progress states")

        return response_content, artifacts, progress_states

    except Exception as e:
        logger.error(f"[WorkflowEventSystem] Event processing failed: {e}")
        return "Workflow processing failed", [], []
