"""
Model Layer for MVC Generate UI - Business Logic and State Management

This module implements the Model component of the MVC pattern for RAG generation.
It handles all business logic including:
- Progress pattern detection from console output
- State management (parser/generation stages)
- Progress calculation and file tracking
- Encapsulated data generation for the Controller layer

Uses Data Transfer Objects (DTOs) with essential/meta-properties separation.
Only essential properties are carried across MVC boundaries.
"""

import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime

# Import DTOs for encapsulated data
from super_starter_suite.shared.dto import (
    ProgressData,
    StatusData,
    GenerationState,
    create_progress_data,
    create_status_data
)

# Import centralized logging
from super_starter_suite.shared.config_manager import config_manager

# Import event system for clean IPC
from .event_system import (
    EventEmitter,
    EventHandler,
    EventType,
    Event,
    get_event_emitter,
    initialize_event_system
)

# Import new separated modules
from .progress_tracker import get_progress_tracker, ProgressTracker
from .terminal_output import get_terminal_manager, TerminalOutputManager

# Get logger for generate manager (pure logging only)
logger = config_manager.get_logger("generate_manager")


class GenerateManager(EventHandler):
    """
    Model for RAG generation progress tracking and business logic.

    Handles all progress detection, state management, and data processing
    that was previously done in the frontend JavaScript.

    Implements EventHandler to participate in the event-driven architecture.
    """

    def __init__(self, total_files: int = 0, config_manager=None):
        """
        Initialize the GenerateManager with initial state.

        Args:
            total_files: Total number of files to process (if known)
            config_manager: ConfigManager instance for event system access
        """
        self.config_manager = config_manager or config_manager
        self.event_emitter = get_event_emitter()
        self.reset(total_files)

        # Subscribe to relevant events
        self.event_emitter.subscribe(self)

    @property
    def handled_event_types(self) -> Set[EventType]:
        """Return event types this handler can process."""
        return {
            EventType.GENERATION_STARTED,
            EventType.GENERATION_COMPLETED,
            EventType.GENERATION_FAILED,
            EventType.PARSER_STARTED,
            EventType.PARSER_COMPLETED,
            EventType.PARSER_FAILED,
            EventType.STATE_CHANGED,
            EventType.STATUS_UPDATED,
        }

    async def handle_event(self, event: Event) -> None:
        """Handle incoming events from the event system."""
        logger.debug(f"GenerateManager received event: {event.event_type.value} from {event.source}")

        # Handle different event types
        if event.event_type == EventType.GENERATION_STARTED:
            self._handle_generation_started_event(event.payload)
        elif event.event_type == EventType.STATE_CHANGED:
            self._handle_state_changed_event(event.payload)
        # Add more event handlers as needed

    def _handle_generation_started_event(self, payload: Dict[str, Any]) -> None:
        """Handle generation started event from external sources."""
        generation_id = payload.get('generation_id')
        logger.info(f"Generation started via event: {generation_id}")

    def _handle_state_changed_event(self, payload: Dict[str, Any]) -> None:
        """Handle state changed event from external sources."""
        component = payload.get('component')
        old_state = payload.get('old_state')
        new_state = payload.get('new_state')
        logger.info(f"State changed: {component} from {old_state} to {new_state}")

    def reset(self, total_files: int = 0):
        """Reset the manager to initial state."""
        self.state = 'ST_READY'  # ST_READY, ST_PARSER, ST_GENERATION, ST_COMPLETED, ST_ERROR
        self.progress = 0
        self.processed_files = 0
        self.total_files = total_files
        self.current_stage = None
        self.parser_stage = 'idle'  # idle, parsing, completed
        self.generation_stage = 'idle'  # idle, parsing, generation, completed
        self.last_raw_message = ""

        logger.debug(f"GenerateManager reset: total_files={total_files}")

    def process_console_output(self, raw_line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> Optional[ProgressData]:
        """
        Parse single line of console output and return encapsulated ProgressData.

        DELEGATES TO: ProgressTracker for all pattern detection and progress calculation.
        This method acts as a clean facade to the separated progress_tracker module.

        Args:
            raw_line: Raw console output line to parse
            task_id: Optional task identifier for the progress data
            rag_type: RAG type for context

        Returns:
            ProgressData object with encapsulated data, or None if no progress update
        """
        # Get the global progress tracker instance
        progress_tracker = get_progress_tracker()

        # Synchronize state with progress tracker
        progress_tracker.set_total_files(self.total_files)

        # Delegate all processing to progress tracker
        result = progress_tracker.parse_rag_output(raw_line, task_id, rag_type)

        # Synchronize state back from progress tracker after processing
        if result is not None:
            self.state = progress_tracker.state
            self.progress = progress_tracker.progress
            self.processed_files = progress_tracker.processed_files
            self.parser_stage = progress_tracker.parser_stage
            self.generation_stage = progress_tracker.generation_stage
            self.last_raw_message = progress_tracker.last_raw_message

        return result

    def get_current_status(self) -> Dict[str, Any]:
        """Get current status for debugging/logging."""
        return {
            'state': self.state,
            'progress': self.progress,
            'processed_files': self.processed_files,
            'total_files': self.total_files,
            'parser_stage': self.parser_stage,
            'generation_stage': self.generation_stage,
            'last_message': self.last_raw_message
        }

    def set_total_files(self, total_files: int):
        """Update the total number of files to process."""
        self.total_files = total_files
        logger.debug(f"Total files updated to: {total_files}")


# Global instance for backward compatibility
_generate_manager = None

def get_generate_manager(total_files: int = 0) -> GenerateManager:
    """Get or create the global GenerateManager instance."""
    global _generate_manager
    if _generate_manager is None:
        _generate_manager = GenerateManager(total_files)
    return _generate_manager

def reset_generate_manager(total_files: int = 0) -> GenerateManager:
    """Reset and return the global GenerateManager instance."""
    global _generate_manager
    _generate_manager = GenerateManager(total_files)
    return _generate_manager
