"""
Event System for Generate UI - Clean Separation of Concerns

This module implements a proper event-driven architecture to replace logger-based IPC.
It provides thread-safe event emission and handling for component communication.

Key Principles:
- Pure logging: Only for human debugging and monitoring
- Event-driven IPC: Dedicated system for machine communication
- Clear separation: Logging ≠ Communication
- Type safety: Structured event payloads with validation
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from threading import Lock

from ..shared.config_manager import ConfigManager


class EventType(Enum):
    """Standardized event types for the Generate UI system."""

    # Generation lifecycle events
    GENERATION_STARTED = "generation_started"
    GENERATION_PROGRESS = "generation_progress"
    GENERATION_COMPLETED = "generation_completed"
    GENERATION_FAILED = "generation_failed"

    # Parser events
    PARSER_STARTED = "parser_started"
    PARSER_PROGRESS = "parser_progress"
    PARSER_COMPLETED = "parser_completed"
    PARSER_FAILED = "parser_failed"

    # State synchronization events
    STATE_CHANGED = "state_changed"
    STATUS_UPDATED = "status_updated"
    METADATA_UPDATED = "metadata_updated"

    # WebSocket events
    WEBSOCKET_CONNECTED = "websocket_connected"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    WEBSOCKET_MESSAGE = "websocket_message"

    # Cache events
    CACHE_LOADED = "cache_loaded"
    CACHE_SAVED = "cache_saved"
    CACHE_INVALIDATED = "cache_invalidated"

    # System events
    SYSTEM_READY = "system_ready"
    SYSTEM_ERROR = "system_error"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class Event:
    """Structured event with type, payload, and metadata."""

    event_type: EventType
    payload: Dict[str, Any]
    timestamp: datetime
    source: str
    event_id: str

    def __init__(self, event_type: EventType, payload: Dict[str, Any], source: str):
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.now()
        self.source = source
        self.event_id = f"{event_type.value}_{int(self.timestamp.timestamp() * 1000)}_{source}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_id": self.event_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            payload=data["payload"],
            source=data["source"]
        )


class EventHandler(ABC):
    """Abstract base class for event handlers."""

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an incoming event asynchronously."""
        pass

    @property
    @abstractmethod
    def handled_event_types(self) -> Set[EventType]:
        """Return the set of event types this handler can process."""
        pass


class EventEmitter:
    """
    Thread-safe event emitter for the Generate UI system.

    This class provides:
    - Thread-safe event emission and handling
    - Async event processing
    - Event subscription/unsubscription
    - Event payload validation
    - Component isolation through source identification
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = config_manager.get_logger("gen_event")

        # Thread-safe storage for event handlers
        self._handlers: Dict[EventType, Set[EventHandler]] = {}
        self._lock = Lock()

        # Event processing queue for async handling
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Event history for debugging (limited size)
        self._event_history: List[Event] = []
        self._max_history_size = 1000

        self.logger.info("EventEmitter initialized with thread-safe architecture")

    async def start(self) -> None:
        """Start the event processing system."""
        if self._is_running:
            self.logger.warning("EventEmitter is already running")
            return

        self._is_running = True
        self._processing_task = asyncio.create_task(self._process_events())
        self.logger.debug("EventEmitter started - processing events asynchronously")

        # Emit system ready event
        await self.emit(EventType.SYSTEM_READY, {}, "event_system")

    async def stop(self) -> None:
        """Stop the event processing system."""
        if not self._is_running:
            return

        self._is_running = False

        # Emit shutdown event
        await self.emit(EventType.SYSTEM_SHUTDOWN, {}, "event_system")

        # Cancel processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        self.logger.info("EventEmitter stopped")

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe an event handler to relevant event types."""
        with self._lock:
            for event_type in handler.handled_event_types:
                if event_type not in self._handlers:
                    self._handlers[event_type] = set()
                self._handlers[event_type].add(handler)

        self.logger.debug(f"Handler {handler.__class__.__name__} subscribed to {len(handler.handled_event_types)} event types")

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe an event handler from all event types."""
        with self._lock:
            for event_type in handler.handled_event_types:
                if event_type in self._handlers:
                    self._handlers[event_type].discard(handler)

        self.logger.debug(f"Handler {handler.__class__.__name__} unsubscribed from all event types")

    async def emit(self, event_type: EventType, payload: Dict[str, Any], source: str) -> None:
        """Emit an event to all subscribed handlers."""
        if not self._is_running:
            self.logger.warning(f"EventEmitter not running, dropping event {event_type.value} from {source}")
            return

        # Validate payload structure
        if not self._validate_payload(event_type, payload):
            self.logger.error(f"Invalid payload for event {event_type.value}: {payload}")
            return

        event = Event(event_type, payload, source)

        # Add to history for debugging
        self._add_to_history(event)

        # Queue for async processing
        await self._event_queue.put(event)

        self.logger.debug(f"Event emitted: {event.event_type.value} from {event.source}")

    def _validate_payload(self, event_type: EventType, payload: Dict[str, Any]) -> bool:
        """Validate event payload structure based on event type."""
        # Add specific validation rules for each event type as needed
        required_fields = {
            EventType.GENERATION_STARTED: ["generation_id"],
            EventType.GENERATION_PROGRESS: ["generation_id", "progress"],
            EventType.GENERATION_COMPLETED: ["generation_id", "result"],
            EventType.GENERATION_FAILED: ["generation_id", "error"],
            EventType.PARSER_STARTED: ["file_count"],
            EventType.PARSER_PROGRESS: ["file_count", "processed_count"],
            EventType.PARSER_COMPLETED: ["file_count", "processed_count"],
            EventType.STATE_CHANGED: ["component", "old_state", "new_state"],
            EventType.STATUS_UPDATED: ["component", "status"],
            EventType.WEBSOCKET_CONNECTED: ["client_id"],
            EventType.WEBSOCKET_DISCONNECTED: ["client_id"],
        }

        if event_type in required_fields:
            missing_fields = [field for field in required_fields[event_type] if field not in payload]
            if missing_fields:
                self.logger.error(f"Missing required fields for {event_type.value}: {missing_fields}")
                return False

        return True

    def _add_to_history(self, event: Event) -> None:
        """Add event to history with size limit."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)

    async def _process_events(self) -> None:
        """Async event processing loop."""
        while self._is_running:
            try:
                # Wait for event with timeout to allow shutdown
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._dispatch_event(event)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                # Check if we should continue running
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                continue

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all relevant handlers."""
        handlers_to_notify = []

        with self._lock:
            if event.event_type in self._handlers:
                handlers_to_notify = list(self._handlers[event.event_type])

        # Dispatch to handlers asynchronously
        tasks = []
        for handler in handlers_to_notify:
            try:
                task = asyncio.create_task(handler.handle_event(event))
                tasks.append(task)
            except Exception as e:
                self.logger.error(f"Error creating task for handler {handler.__class__.__name__}: {e}")

        # Wait for all handlers to complete (fire-and-forget style)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_event_history(self, limit: int = 100) -> List[Event]:
        """Get recent event history for debugging."""
        return list(self._event_history[-limit:])

    def get_handler_count(self, event_type: EventType) -> int:
        """Get number of handlers subscribed to an event type."""
        with self._lock:
            return len(self._handlers.get(event_type, set()))

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Global event emitter instance (will be initialized by the application)
_event_emitter: Optional[EventEmitter] = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance."""
    if _event_emitter is None:
        raise RuntimeError("EventEmitter not initialized. Call initialize_event_system() first.")
    return _event_emitter


def initialize_event_system(config_manager: ConfigManager) -> EventEmitter:
    """Initialize the global event system."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = EventEmitter(config_manager)
    return _event_emitter
