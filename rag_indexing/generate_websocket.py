"""
WebSocket Module for Real-time RAG Generation Progress (MVC Controller)

This module implements the Controller layer of the MVC pattern for RAG generation.
It orchestrates communication between the Model (GenerateManager) and View (frontend).

MVC Flow:
Raw Console Output → Controller → Model → Structured JSON → View
"""

import asyncio
import json
import os
import logging
from typing import Dict, List, Optional, Any, Set, Union
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import DTOs for encapsulated data
from super_starter_suite.shared.dto import (
    ProgressData,
    StatusData,
    GenerationState,
    create_progress_data,
    create_status_data
)

# Import GenerateManager and ProgressTracker for proper instantiation
from super_starter_suite.rag_indexing.generate_manager import GenerateManager
from super_starter_suite.rag_indexing.progress_tracker import ProgressTracker

# UNIFIED LOGGING SYSTEM - Replace global logging
from super_starter_suite.shared.config_manager import config_manager

# Import event system for clean IPC
from super_starter_suite.rag_indexing.event_system import (
    EventEmitter,
    EventHandler,
    EventType,
    Event,
    get_event_emitter,
    initialize_event_system
)

# Get logger for MVC WebSocket controller
ws_logger = logging.getLogger("MVC_websocket")

router = APIRouter()

# ============================================================================
# WEBSOCKET CONNECTION MANAGEMENT
# ============================================================================

class WebSocketManager:
    """Manages WebSocket connections per generation task"""

    def __init__(self, max_connections_per_task: int = 5):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.max_connections_per_task = max_connections_per_task
        self.connection_counts: Dict[str, int] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> bool:
        """Connect a WebSocket for a specific task. Returns False if at limit."""
        current_count = self.connection_counts.get(task_id, 0)

        if current_count >= self.max_connections_per_task:
            return False  # Connection limit reached

        await websocket.accept()

        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
            self.connection_counts[task_id] = 0

        self.active_connections[task_id].append(websocket)
        self.connection_counts[task_id] += 1

        return True

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Disconnect a WebSocket for a specific task"""
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
                self.connection_counts[task_id] -= 1

            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
                del self.connection_counts[task_id]

    async def broadcast_to_task(self, task_id: str, message: Dict[str, Any]):
        """Broadcast message to all connections for a specific task"""
        if task_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(task_id, connection)

    async def broadcast_progress(self, task_id: str, state: str, progress: float, message: str = ""):
        """Broadcast progress update"""
        # State is already in the correct format (e.g., 'ST_PARSER') from ProgressData.state.value
        # No additional mapping needed - pass through directly to frontend
        await self.broadcast_to_task(task_id, {
            "type": "progress",
            "state": state,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_terminal(self, task_id: str, level: str, message: str):
        """Broadcast terminal output"""
        await self.broadcast_to_task(task_id, {
            "type": "terminal",
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_status(self, task_id: str, data_status: Optional[Dict[str, Any]] = None, rag_status: Optional[Dict[str, Any]] = None):
        """Broadcast status update"""
        message: Dict[str, Any] = {"type": "status", "timestamp": datetime.now().isoformat()}
        if data_status is not None:
            message["data_status"] = data_status
        if rag_status is not None:
            message["rag_status"] = rag_status
        await self.broadcast_to_task(task_id, message)

    def get_connection_count(self, task_id: str) -> int:
        """Get current connection count for a task"""
        return self.connection_counts.get(task_id, 0)

# Global WebSocket manager instance
websocket_manager = WebSocketManager(max_connections_per_task=5)  # Reserve 10% for others

# ============================================================================
# MVC CONTROLLER CLASS
# ============================================================================

class GenerateWebSocketController(EventHandler):
    """
    MVC Controller for RAG generation progress.

    Orchestrates communication between Model (GenerateManager) and View (frontend).
    Implements the MVC pipeline: Raw Console → Controller → Model → Structured JSON → View

    Uses event-driven architecture for clean IPC instead of logger-based communication.
    """

    def __init__(self, status_data=None):
        """
        Initialize MVC Controller with StatusData.

        Args:
            status_data: StatusData object (will create fresh if None)
        """
        # Create StatusData if not provided (for backward compatibility)
        if status_data is None:
            from super_starter_suite.shared.dto import StatusData
            status_data = StatusData(rag_type="RAG", total_files=0)

        # Create components with StatusData
        self.generate_manager = GenerateManager(status_data)
        self.task_id = "current_generation"
        self.event_emitter = get_event_emitter()

        # Subscribe to relevant events for event-driven communication
        self.event_emitter.subscribe(self)

    @property
    def handled_event_types(self) -> Set[EventType]:
        """Return event types this controller can handle."""
        return {
            EventType.GENERATION_STARTED,
            EventType.GENERATION_PROGRESS,
            EventType.GENERATION_COMPLETED,
            EventType.GENERATION_FAILED,
            EventType.PARSER_STARTED,
            EventType.PARSER_PROGRESS,
            EventType.PARSER_COMPLETED,
            EventType.PARSER_FAILED,
            EventType.STATE_CHANGED,
            EventType.STATUS_UPDATED,
            EventType.WEBSOCKET_CONNECTED,
            EventType.WEBSOCKET_DISCONNECTED,
        }

    async def handle_event(self, event: Event) -> None:
        """Handle incoming events and broadcast to WebSocket clients."""


        # Convert event to WebSocket message format
        websocket_message = self._event_to_websocket_message(event)

        if websocket_message:
            # Broadcast to all connected clients
            await websocket_manager.broadcast_to_task(self.task_id, websocket_message)

    def _event_to_websocket_message(self, event: Event) -> Optional[Dict[str, Any]]:
        """Convert event to WebSocket message format for frontend consumption."""
        payload = event.payload

        # Map event types to WebSocket message types
        if event.event_type == EventType.GENERATION_STARTED:
            return {
                "type": "progress",
                "state": "GENERATION",
                "progress": 0,
                "message": "Starting RAG generation...",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.GENERATION_PROGRESS:
            return {
                "type": "progress",
                "state": "GENERATION",
                "progress": payload.get("progress", 0),
                "message": payload.get("message", ""),
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.GENERATION_COMPLETED:
            return {
                "type": "progress",
                "state": "COMPLETED",
                "progress": 100,
                "message": "Generation completed successfully!",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.GENERATION_FAILED:
            return {
                "type": "progress",
                "state": "ERROR",
                "progress": 0,
                "message": f"Error: {payload.get('error', 'Unknown error')}",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.PARSER_STARTED:
            return {
                "type": "progress",
                "state": "PARSER",
                "progress": 0,
                "message": f"Starting parser for {payload.get('file_count', 0)} files...",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.PARSER_PROGRESS:
            return {
                "type": "progress",
                "state": "PARSER",
                "progress": payload.get("progress", 0),
                "message": payload.get("message", ""),
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.PARSER_COMPLETED:
            return {
                "type": "progress",
                "state": "GENERATION",
                "progress": 0,
                "message": "Parser completed, starting generation...",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.STATE_CHANGED:
            return {
                "type": "status",
                "component": payload.get("component", "unknown"),
                "old_state": payload.get("old_state", ""),
                "new_state": payload.get("new_state", ""),
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.WEBSOCKET_CONNECTED:
            return {
                "type": "system",
                "message": f"Client {payload.get('client_id', 'unknown')} connected",
                "timestamp": event.timestamp.isoformat()
            }

        elif event.event_type == EventType.WEBSOCKET_DISCONNECTED:
            return {
                "type": "system",
                "message": f"Client {payload.get('client_id', 'unknown')} disconnected",
                "timestamp": event.timestamp.isoformat()
            }

        return None

    def reset_manager(self, total_files: int = 0):
        """Reset the generate manager for a new generation task."""
        # Reset the existing generate manager instance
        self.generate_manager.set_total_files(total_files)
        self.generate_manager.reset(total_files)

    async def emit_generation_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        """Emit a generation-related event to the event system."""
        await self.event_emitter.emit(event_type, payload, "websocket_controller")

    async def handle_generation_output(self, raw_line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> None:
        """
        MVC Pipeline: Process raw console output through Model and broadcast to View.

        Args:
            raw_line: Raw console output line from generation process
            task_id: Optional task identifier for the progress data
            rag_type: RAG type for context
        """
        # CRITICAL FIX: Check if generation is already completed before processing
        # This prevents endless progress updates after completion
        current_status = self.generate_manager.get_current_status()
        if current_status.get('state') == 'completed':
            # Generation already completed, skipping further processing
            return

        # Step 1: Send raw output to Model for processing
        structured_data = self.generate_manager.process_console_output(raw_line, task_id, rag_type)

        # Step 2: If Model returns structured data, broadcast to View
        if structured_data:
            await self._broadcast_structured_data(structured_data)

    async def _broadcast_structured_data(self, model_data: Union[ProgressData, Dict[str, Any]]) -> None:
        """
        Format Model data for View consumption and broadcast via WebSocket.

        Control Point: Handles both encapsulated DTOs and legacy dictionaries.

        Args:
            model_data: Structured data from GenerateManager (Model) - ProgressData or Dict
        """
        # Handle encapsulated ProgressData objects
        if isinstance(model_data, ProgressData):
            # Control Point: Mark data as transformed by controller
            model_data.mark_transformed()

            # Convert encapsulated DTO to frontend format
            color_map = {
                GenerationState.READY.value: 'white',
                GenerationState.PARSER.value: 'green',
                GenerationState.GENERATION.value: 'orange',
                GenerationState.COMPLETED.value: 'green',
                GenerationState.ERROR.value: 'red'
            }

            # FIX: Use 'state' and 'progress' field names to match frontend expectations
            view_data = {
                'type': 'progress',
                'state': model_data.state.value,  # Changed from 'stage'
                'progress': model_data.progress,  # Changed from 'percentage'
                'message': model_data.message,
                'timestamp': model_data.timestamp.isoformat(),
                # Include meta-properties for debugging
                '_source': model_data._source,
                '_validated': model_data._validated,
                '_transformed': model_data._transformed
            }

        # Handle legacy dictionary format (backward compatibility)
        elif isinstance(model_data, dict):
            # Format for frontend consumption (View layer) - match expected format
            if model_data.get('type') == 'progress_update':
                # Convert MVC format to frontend expected format
                color_map = {
                    'ready': 'white',
                    'parser': 'green',
                    'generation': 'orange',
                    'completed': 'green',
                    'error': 'red'
                }

                # FIX: Use consistent field names for legacy format too
                view_data = {
                    'type': 'progress',
                    'state': model_data['state'],  # Changed from 'stage'
                    'progress': model_data['progress'],  # Changed from 'percentage'
                    'message': model_data['message'],
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # For other types, pass through as-is
                view_data = {
                    'type': model_data['type'],
                    'state': model_data.get('state'),
                    'progress': model_data.get('progress', 0),
                    'message': model_data.get('message', ''),
                    'metadata': model_data.get('metadata', {}),
                    'timestamp': datetime.now().isoformat()
                }
        else:
            ws_logger.warning(f"Unknown model_data type: {type(model_data)}")
            return

        # Broadcast structured data to connected frontend clients
        await websocket_manager.broadcast_to_task(self.task_id, view_data)

    async def broadcast_terminal_message(self, level: str, message: str) -> None:
        """
        Broadcast terminal message to View layer.

        Args:
            level: Message level (info, success, error, warning)
            message: Terminal message
        """
        terminal_data = {
            "type": "terminal",
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_task(self.task_id, terminal_data)

    async def broadcast_status_update(self, data_status: Optional[Dict[str, Any]] = None,
                                    rag_status: Optional[Dict[str, Any]] = None) -> None:
        """
        Broadcast status update to View layer.

        Args:
            data_status: Updated data status from backend
            rag_status: Updated RAG status from backend
        """
        # Send data status update
        if data_status:
            data_message = {
                "type": "status",
                "data_status": data_status,
                "timestamp": datetime.now().isoformat()
            }
            await websocket_manager.broadcast_to_task(self.task_id, data_message)

        # Send RAG status update
        if rag_status:
            rag_message = {
                "type": "status",
                "rag_status": rag_status,
                "timestamp": datetime.now().isoformat()
            }
            await websocket_manager.broadcast_to_task(self.task_id, rag_message)

    def get_current_status(self) -> Dict[str, Any]:
        """Get current generation status from Model."""
        return self.generate_manager.get_current_status()

# Global MVC Controller removed - using session-based GenerateManager for MVC processing
# No global state dependencies - all MVC through session's GenerateManager

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/ws/generate")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time terminal streaming during RAG generation

    Single-client design: Only one generation task runs at a time on this system.
    Task ID is passed via query parameter to ensure proper message routing.
    """
    # Use MVC internal logger
    ws_logger = logging.getLogger("MVC_websocket")

    ws_logger.info("WebSocket connection attempt for generation")

    # Get task_id from query parameter - fallback to default for compatibility
    query_params = websocket.query_params
    task_id = query_params.get('task_id', 'current_generation')

    ws_logger.info(f"WebSocket connection for task_id: {task_id}")

    # Attempt to connect
    connected = await websocket_manager.connect(task_id, websocket)

    if not connected:
        ws_logger.warning("Connection rejected - limit reached")
        await websocket.close(code=1008, reason="Connection limit reached")
        return

    ws_logger.info("WebSocket connected successfully for generation")

    try:
        # Send initial connection confirmation
        connection_msg = {
            "type": "connected",
            "message": "Connected to generation WebSocket",
            "timestamp": datetime.now().isoformat()
        }

        await websocket.send_json(connection_msg)

        # Keep connection alive and listen for client messages
        while True:
            try:
                # Set a reasonable timeout for receiving messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                ws_logger.info(f"📨 RECEIVED WebSocket message from client: {data}")

                try:
                    message_data = json.loads(data)
                    # Handle test messages by broadcasting them back
                    if message_data.get('type') == 'progress':
                        await websocket.send_json({
                            "type": "progress",
                            "state": message_data.get('state'),
                            "progress": message_data.get('progress'),
                            "message": f"ECHO: {message_data.get('message', 'Test message')}",
                            "timestamp": datetime.now().isoformat()
                        })

                except json.JSONDecodeError as e:
                    ws_logger.warning(f"❌ Failed to parse WebSocket message: {e}")

                # Handle any client messages if needed (ping/pong, etc.)
                if data == "ping":
                    pong_msg = {"type": "pong", "timestamp": datetime.now().isoformat()}
                    await websocket.send_json(pong_msg)

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                ping_msg = {"type": "ping", "timestamp": datetime.now().isoformat()}
                await websocket.send_json(ping_msg)
                continue

    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected")
        websocket_manager.disconnect(task_id, websocket)
    except Exception as e:
        ws_logger.error(f"WebSocket error: {str(e)}")
        websocket_manager.disconnect(task_id, websocket)

# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================

async def broadcast_generation_progress(task_id: str, stage: str, percentage: float, message: str = ""):
    """
    Broadcast generation progress update via WebSocket

    Args:
        task_id: Generation task ID
        stage: Progress stage (ready, parser, generation, error)
        percentage: Progress percentage (0-100)
        message: Progress message
    """
    await websocket_manager.broadcast_progress(task_id, stage, percentage, message)

async def broadcast_terminal_message(task_id: str, level: str, message: str):
    """
    Broadcast terminal message via WebSocket

    Args:
        task_id: Generation task ID
        level: Message level (info, success, error, warning)
        message: Terminal message
    """
    await websocket_manager.broadcast_terminal(task_id, level, message)

async def broadcast_status_update(task_id: str, data_status: Optional[Dict[str, Any]] = None, rag_status: Optional[Dict[str, Any]] = None):
    """
    Broadcast status update via WebSocket

    Args:
        task_id: Generation task ID
        data_status: Updated data status
        rag_status: Updated RAG status
    """
    await websocket_manager.broadcast_status(task_id, data_status, rag_status)

def get_task_connection_count(task_id: str) -> int:
    """
    Get current WebSocket connection count for a task

    Args:
        task_id: Generation task ID

    Returns:
        Number of active connections
    """
    return websocket_manager.get_connection_count(task_id)

# ============================================================================
# MONITORING FUNCTIONS
# ============================================================================

def get_websocket_stats() -> Dict[str, Any]:
    """
    Get WebSocket connection statistics

    Returns:
        Dictionary with connection statistics
    """
    total_connections = sum(websocket_manager.connection_counts.values())
    active_tasks = len(websocket_manager.connection_counts)

    return {
        "total_connections": total_connections,
        "active_tasks": active_tasks,
        "connections_per_task": dict(websocket_manager.connection_counts),
        "max_connections_per_task": websocket_manager.max_connections_per_task
    }

# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

async def cleanup_task_connections(task_id: str):
    """
    Clean up all WebSocket connections for a completed task

    Args:
        task_id: Generation task ID to clean up
    """
    if task_id in websocket_manager.active_connections:
        # Send final completion message to all connections
        await websocket_manager.broadcast_to_task(task_id, {
            "type": "task_completed",
            "task_id": task_id,
            "message": "RAG generation completed successfully",
            "timestamp": datetime.now().isoformat()
        })

        # Give frontend time to process the completion message before closing
        await asyncio.sleep(0.5)

        # Close all connections for this task
        for connection in websocket_manager.active_connections[task_id][:]:  # Copy list
            try:
                await connection.close(code=1000, reason="Task completed")
            except Exception:
                pass  # Connection may already be closed

        # Remove from active connections
        del websocket_manager.active_connections[task_id]
        del websocket_manager.connection_counts[task_id]

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "router",
    "broadcast_generation_progress",
    "broadcast_terminal_message",
    "broadcast_status_update",
    "get_task_connection_count",
    "get_websocket_stats",
    "cleanup_task_connections",
    "GenerateWebSocketController"
]
