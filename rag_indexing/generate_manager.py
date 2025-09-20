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
import time

# Import DTOs for encapsulated data
from super_starter_suite.shared.dto import (
    ProgressData,
    StatusData
)

# Import centralized logging
from super_starter_suite.shared.config_manager import config_manager

# Import event system for clean IPC
from super_starter_suite.rag_indexing.event_system import (
    EventEmitter,
    EventHandler,
    EventType,
    Event,
    get_event_emitter
)

# Import new separated modules
from super_starter_suite.rag_indexing.progress_tracker import ProgressTracker

# Get logger for generate manager (pure logging only)
logger = config_manager.get_logger("gen_manager")


class GenerateManager(EventHandler):
    """
    Model for RAG generation progress tracking and business logic.

    Handles all progress detection, state management, and data processing
    that was previously done in the frontend JavaScript.

    Implements EventHandler to participate in the event-driven architecture.
    """

    def __init__(self, status_data: StatusData, user_config, config_manager=None):
        """
        Initialize the GenerateManager with StatusData and user config.

        Args:
            status_data: StatusData object (single source of truth)
            user_config: UserConfig containing paths and settings
            config_manager: ConfigManager instance for event system access
        """
        self.status_data = status_data
        self.user_config = user_config  # Store user config for metadata saving
        self.config_manager = config_manager or config_manager
        self.event_emitter = get_event_emitter()

        # Create ProgressTracker with StatusData for total_files access
        self._progress_tracker = ProgressTracker(self.status_data)

        self.reset(0)  # Keep backward compatibility for now

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
        elif event.event_type == EventType.GENERATION_COMPLETED:
            await self._handle_generation_completed_event(event.payload)
        elif event.event_type == EventType.GENERATION_FAILED:
            await self._handle_generation_failed_event(event.payload)
        elif event.event_type == EventType.STATE_CHANGED:
            self._handle_state_changed_event(event.payload)
        # Add more event handlers as needed

    def _handle_generation_started_event(self, payload: Dict[str, Any]) -> None:
        """Handle generation started event from external sources."""
        generation_id = payload.get('generation_id')
        logger.info(f"Generation started via event: {generation_id}")

    async def _handle_generation_completed_event(self, payload: Dict[str, Any]) -> None:
        """Handle generation completed event and save updated metadata."""
        # Check for success in the result object (per event system format)
        result = payload.get('result', {})
        if result.get('success', False):
            # Only save metadata if generation was successful
            await self._save_metadata_on_completion()
            logger.info("Metadata saved after successful RAG generation completion")
        else:
            logger.warning("Generation failed, skipping metadata save")

    async def _handle_generation_failed_event(self, payload: Dict[str, Any]) -> None:
        """Handle generation failed event (no metadata saving for failures)."""
        error_message = payload.get('error', 'Unknown error')
        logger.error(f"Generation failed: {error_message}")
        # Don't save metadata on failure

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

        DELEGATES TO: Session's encapsulated ProgressTracker for pattern detection and progress calculation.
        This method acts as a clean facade to the session-based progress_tracker.

        Args:
            raw_line: Raw console output line to parse
            task_id: Optional task identifier for the progress data
            rag_type: RAG type for context

        Returns:
            ProgressData object with encapsulated data, or None if no progress update
        """
        # DEBUG: Log current state
        logger.debug(f"GenerateManager.process_console_output: self.total_files={self.total_files}")

        # Use session-encapsulated progress tracker (mandatory injection)
        if not hasattr(self, '_progress_tracker'):
            raise RuntimeError("ProgressTracker not injected - session initialization incomplete")

        # No need to synchronize - ProgressTracker gets total_files from StatusData

        # Delegate all processing to progress tracker
        result = self._progress_tracker.parse_rag_output(raw_line, task_id, rag_type)

        # Synchronize state back from progress tracker after processing
        old_state = self.state
        if result is not None:
            self.state = self._progress_tracker.state
            self.progress = self._progress_tracker.progress
            self.processed_files = self._progress_tracker.processed_files
            self.parser_stage = self._progress_tracker.parser_stage
            self.generation_stage = self._progress_tracker.generation_stage
            self.last_raw_message = self._progress_tracker.last_raw_message

            # CRITICAL FIX: Emit GENERATION_COMPLETED event when state changes to ST_COMPLETED
            if old_state != 'ST_COMPLETED' and self.state == 'ST_COMPLETED':
                logger.debug("Generating COMPLETED state detected, emitting GENERATION_COMPLETED event")
                # Create event emission task (fire-and-forget)
                import asyncio
                asyncio.create_task(self.notify_generation_completed(success=True))

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

    def set_status_data(self, status_data: StatusData):
        """
        Update StatusData and recreate ProgressTracker when RAG type changes.

        Called by RAGGenerationSession when switching RAG types.
        GenerateManager owns ProgressTracker lifecycle and handles recreation internally.

        Args:
            status_data: New StatusData object for the current RAG type
        """
        self.status_data = status_data
        # GenerateManager owns ProgressTracker, so it handles recreation
        self._progress_tracker = ProgressTracker(self.status_data)
        # Reset MVC state for new StatusData
        self.reset(self.status_data.total_files)
        logger.debug(f"StatusData updated: total_files={self.status_data.total_files}")

    async def emit_generation_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        """
        Emit generation-related events for clean event-driven communication.

        GenerateManager emits events that other components can subscribe to,
        enabling clean MVC separation without tight coupling.

        Args:
            event_type: Type of event to emit
            payload: Event payload data
        """
        await self.event_emitter.emit(event_type, payload, "generate_manager")

    async def notify_generation_started(self, generation_id: str) -> None:
        """
        Notify that generation has started via event system.

        Args:
            generation_id: Unique identifier for the generation task
        """
        await self.emit_generation_event(EventType.GENERATION_STARTED, {
            'generation_id': generation_id,
            'total_files': self.total_files,
            'rag_type': self.status_data.rag_type
        })

    async def notify_generation_progress(self, progress: float, message: str) -> None:
        """
        Notify generation progress via event system.

        Args:
            progress: Current progress percentage (0-100)
            message: Progress message
        """
        await self.emit_generation_event(EventType.GENERATION_PROGRESS, {
            'progress': progress,
            'message': message,
            'processed_files': self.processed_files,
            'total_files': self.total_files
        })

    async def _save_metadata_on_completion(self) -> None:
        """Save updated metadata after successful generation completion."""
        try:
            # Scan current data to get updated info for metadata
            data_info = self.status_data.data_files  # Use current StatusData as base

            # Update metadata with new storage information from successful generation
            success = self.status_data.save_to_file(self.user_config)
            if success:
                logger.info(f"Metadata successfully saved after generation completion for RAG type {self.status_data.rag_type}")
            else:
                logger.warning(f"Failed to save metadata after generation completion for RAG type {self.status_data.rag_type}")

        except Exception as e:
            logger.error(f"Error saving metadata after generation completion: {e}")

    async def notify_generation_completed(self, success: bool, error_message: str = "") -> None:
        """
        Notify generation completion via event system.

        Args:
            success: Whether generation completed successfully
            error_message: Error message if generation failed
        """
        event_type = EventType.GENERATION_COMPLETED if success else EventType.GENERATION_FAILED

        # Event system expects specific payload format for GENERATION_COMPLETED
        current_timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds

        if success:
            payload = {
                'generation_id': f"{self.status_data.rag_type}_{self.processed_files}_{current_timestamp}",
                'result': {
                    'success': True,
                    'total_files': self.total_files,
                    'processed_files': self.processed_files,
                    'rag_type': self.status_data.rag_type
                }
            }
        else:
            # For failed generations, use GENERATION_FAILED with different payload format
            payload = {
                'generation_id': f"{self.status_data.rag_type}_failed_{current_timestamp}",
                'error': error_message or "Unknown error"
            }

        await self.emit_generation_event(event_type, payload)


# Global singletons removed - use session-based architecture instead
# All GenerateManager instances should be created by RAGGenerationSession
