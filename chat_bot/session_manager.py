"""
ChatBot Session Manager

Implements unified chat session classes with BaseSessionHandler integration:
- ChatBotSession: Common functionality for WorkflowSession and HistorySession
- WorkflowSession: Active workflow conversation management (ONE ACTIVE per workflow)
- HistorySession: Administrative ALL sessions management (OLD conversations only)

Provides chat history and workflow state tracking with conversational boundaries.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import uuid
from datetime import datetime

from super_starter_suite.shared.dto import ChatMessageDTO, ChatSessionData
from super_starter_suite.shared.session_utils import BaseSessionHandler, BasicUserSession
from super_starter_suite.shared.config_manager import UserConfig, config_manager
from super_starter_suite.shared.workflow_loader import get_workflow_config

logger = config_manager.get_logger("sess_manager")


class ChatBotSession(BasicUserSession):
    """
    COMBINED CHAT FUNCTIONALITY: Inherits from BasicUserSession and provides chat-specific functionality

    COMBINES what used to be BaseChatSessionHandler + ChatBotSession into one class.
    Provides common chat functionality for WorkflowSession and HistorySession.

    ChatHistoryManager is created immediately at construction time when workflow context is available.
    """

    def __init__(self, user_config: any, session_type: str, session_id: str,
                 chat_access_level: str = "read"):
        # Initialize BasicUserSession first (provides user awareness)
        super().__init__(user_config, session_type, session_id)

        # CHAT-SPECIFIC INITIALIZATION (from BaseChatSessionHandler)
        self.chat_access_level = chat_access_level  # "read", "admin", "active"
        self.session_registry: Dict[str, Any] = {}

        # CHAT MANAGER ACCESS (from BaseChatSessionHandler)
        # Create ChatHistoryManager immediately with session ownership
        try:
            from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
            self.chat_manager = ChatHistoryManager(self.user_config, session_owner=self)
            logger.debug(f"ChatHistoryManager created immediately for {session_type} session {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to initialize chat access for session {self.session_id}: {e}")
            self.chat_manager = None

    def get_sessions_for_workflow(self, workflow_name: str) -> List[Any]:
        """SHARED: Get sessions for workflow (from BaseChatSessionHandler)"""
        if self.chat_manager:
            return self.chat_manager.get_all_sessions(workflow_name)
        return []

    def get_session_health_status(self) -> Dict[str, Any]:
        """ENHANCED: Include inherited user awareness + chat-specific health"""
        base = super().get_session_health_status()
        return {
            **base,
            "chat_access_level": self.chat_access_level,
            "chat_manager_available": self.chat_manager is not None,
            "session_registry_size": len(self.session_registry)
        }

    def perform_session_health_check(self) -> bool:
        """ENHANCED: Validate both BasicUserSession health and chat-specific requirements"""
        try:
            # Validate chat-specific requirements
            assert self.chat_access_level in ["read", "admin", "active"]
            # Validate BasicUserSession requirements (inherited)
            return super().perform_session_health_check()
        except AssertionError:
            logger.warning(f"Health check failed for chat session {self.session_id}")
            return False

    def initialize_session_resources(self):
        """ENHANCED: Initialize both BasicUserSession resources and chat resources"""
        # Initialize BasicUserSession resources first
        super().initialize_session_resources()

        logger.info(f"ChatBotSession {self.session_id} fully initialized")

    def dispose(self):
        """ENHANCED: Cleanup both BasicUserSession and chat resources"""
        # Cleanup chat resources
        self.session_registry.clear()
        self.chat_manager = None

        # Cleanup BasicUserSession resources
        super().dispose()


class HistorySession(ChatBotSession):
    """
    FULLY INTEGRATED HistorySession: Encapsulates legacy chat management

    Encapsulates all legacy chat management modules:
    - chat_history_manager.py: Core chat persistence and LlamaIndex integration
    - data_crud_endpoint.py: FastAPI endpoints for chat history CRUD operations
    """

    def __init__(self, user_config, session_type: str, session_id: str):
        super().__init__(user_config, session_type, session_id, chat_access_level="admin")

        # History sessions work across all workflows - set to None to indicate global access
        self.active_workflow_id = None

        # Admin permissions for all sessions
        self.history_permissions = {
            "can_read_all_sessions": True,
            "can_delete_sessions": True,
            "can_export_sessions": True,
            "can_view_all_workflows": True,
            "can_create_new_conversations": False,
        }

    def dispose(self):
        """Clean up history session resources"""
        # History sessions are read-only admin sessions
        # Clear any temporary browsing data
        logger.info(f"HistorySession {self.session_id} disposed")

    def persist_session_data(self) -> bool:
        """Read-only admin session - no persistence needed"""
        return True


class WorkflowSession(ChatBotSession):
    """
    MASTER WORKFLOW CONTAINER: Contains BOTH static config and dynamic runtime state

    Architecture: Workflow endpoints start with static workflow_config, build dynamic ExecutionContext.
    WorkflowSession holds everything persistently while ExecutionContext is per-request.
    """

    def __init__(self, user_config, session_type: str, session_id: str, workflow_id: Optional[str] = None):
        # CRITICAL FIX: Set active_workflow_id BEFORE calling parent __init__
        # This ensures ChatHistoryManager gets the correct workflow_id
        self.active_workflow_id = workflow_id

        super().__init__(user_config, session_type, session_id)

        # If workflow_id provided, load workflow configuration immediately (SRR)
        # WorkflowFactory is already set in WorkflowConfig - don't recreate it
        if workflow_id:
            try:
                self.workflow_config_data = get_workflow_config(workflow_id)

                # workflow_factory_func is already set in workflow_config_data.workflow_factory
                self.workflow_factory_func = getattr(self.workflow_config_data, 'workflow_factory', None)
                self.workflow_loaded_at = datetime.now().isoformat()

                # STRENGTHEN WORKFLOW CONTEXT: Ensure workflow_config_data.workflow_ID matches active_workflow_id
                if self.workflow_config_data and hasattr(self.workflow_config_data, 'workflow_ID'):
                    if self.workflow_config_data.workflow_ID != self.active_workflow_id:
                        logger.warning(f"WorkflowConfig.workflow_ID mismatch: config has '{self.workflow_config_data.workflow_ID}', session has '{self.active_workflow_id}' - using session value")
                        # Force the config to match the session's workflow_id
                        self.workflow_config_data.workflow_ID = self.active_workflow_id

            except Exception as e:
                logger.error(f"Failed to load workflow config for {workflow_id}: {e}")
                # STRENGTHEN WORKFLOW CONTEXT: Create minimal config to prevent None assignment
                logger.warning(f"Creating minimal workflow config for {workflow_id} to prevent context loss")
                try:
                    from super_starter_suite.shared.dto import WorkflowConfig
                    self.workflow_config_data = WorkflowConfig(
                        code_path="",  # Minimal required fields
                        timeout=60.0,
                        display_name=workflow_id,
                        workflow_ID=workflow_id  # CRITICAL: Ensure workflow_ID is set
                    )
                except Exception as config_error:
                    logger.error(f"Failed to create minimal workflow config: {config_error}")
                    self.workflow_config_data = None

                self.workflow_factory_func = None
                self.workflow_loaded_at = None

        # RUNTIME PROPERTIES (built during execution - dynamic per-request)
        self.user_message: str = ""    # Current user input (from ExecutionContext)
        self.execution_context: Optional[Any] = None  # Lightweight runtime ExecutionContext

        # SESSION PERSISTENCE (survives across requests)
        self.chat_history: List[ChatMessageDTO] = []
        self.workflow_context: Dict[str, Any] = {}
        self.workflow_state: Dict[str, Any] = {}
        self.title: str = ""  # Title for session (generated from first user message)

        # LEGACY COMPATIBILITY (moved from request.state - single source of truth)
        self.chat_memory: Optional[Dict[str, Any]] = None  # Unified conversation memory

    # BACKWARD COMPATIBILITY: WorkflowSession provides workflow_name for ChatSessionData-like interface
    @property
    def workflow_name(self) -> Optional[str]:
        """Map active_workflow_id to workflow_name for backward compatibility with ChatSessionData interface"""
        return self.active_workflow_id

    @property
    def messages(self):
        """Standardized messages property for workflow compatibility. 
        Always returns current session messages from ChatHistoryManager.
        """
        if self.chat_manager:
            try:
                session_data = self.chat_manager.get_active_session_data()
                return session_data.messages
            except Exception as e:
                logger.warning(f"Failed to retrieve messages from ChatManager: {e}")
        
        return self.chat_history

    # EXTERNAL EXECUTION CONTEXT METHODS - Class-level methods for HITL workflow context management
    @classmethod
    def set_external_execution_context(cls, session_id: str, execution_context: Dict[str, Any]) -> bool:
        """
        Set external execution context for a workflow session.

        Allows external systems to inject execution context into HITL workflows
        through the unified session management system.

        Args:
            session_id: Target session identifier
            execution_context: External execution context data

        Returns:
            bool: True if context was set successfully
        """
        try:
            from super_starter_suite.shared.session_utils import get_session_handler
            session = get_session_handler(session_id)
            if not isinstance(session, WorkflowSession):
                logger.warning(f"[WorkflowSession] Cannot set external context - session {session_id} is not a WorkflowSession")
                return False

            # Set external execution context
            session.execution_context = execution_context.copy()
            logger.info(f"[WorkflowSession] Set external execution context for session {session_id}: {len(execution_context)} fields")
            return True

        except Exception as e:
            logger.error(f"[WorkflowSession] Failed to set external execution context for {session_id}: {e}")
            return False

    @classmethod
    def get_external_execution_context(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get external execution context from a workflow session.

        Args:
            session_id: Session identifier

        Returns:
            External execution context dict or None if not available
        """
        try:
            from super_starter_suite.shared.session_utils import get_session_handler
            session = get_session_handler(session_id)
            if not isinstance(session, WorkflowSession):
                return None

            return session.execution_context if session.execution_context else None

        except Exception as e:
            logger.warning(f"[WorkflowSession] Failed to get external execution context for {session_id}: {e}")
            return None

    @classmethod
    def associate_workflow_with_session(cls, workflow_id: str, session_id: str) -> bool:
        """
        Associate a workflow with a specific session for external context injection.

        Args:
            workflow_id: Workflow identifier
            session_id: Target session identifier

        Returns:
            bool: True if association was successful
        """
        try:
            from super_starter_suite.shared.session_utils import get_session_handler
            session = get_session_handler(session_id)
            if not isinstance(session, WorkflowSession):
                logger.warning(f"[WorkflowSession] Cannot associate workflow - session {session_id} is not a WorkflowSession")
                return False

            session.active_workflow_id = workflow_id
            logger.info(f"[WorkflowSession] Associated workflow {workflow_id} with session {session_id}")
            return True

        except Exception as e:
            logger.error(f"[WorkflowSession] Failed to associate workflow {workflow_id} with session {session_id}: {e}")
            return False

    def initialize_session_resources(self):
        """Initialize complete workflow session with static config references"""
        super().initialize_session_resources()  # Initialize parent ChatBotSession resources

        # Initialize workflow context
        self.workflow_context = {
            "initialized": True,
            "init_time": datetime.now().isoformat()
        }

        # Initialize legacy compatibility properties (now WorkflowSession properties)
        self.chat_memory = {
            'conversation_id': self.session_id,
            'workflow_name': self.active_workflow_id or 'unknown',
            'messages': self.chat_history
        }

        logger.info(f"WorkflowSession {self.session_id} initialized with static config ready")

    def bind_chat_session_id(self, chat_session_id: Optional[str]):
        """
        Binds the WorkflowSession's ChatHistoryManager to a specific chat_session_id.
        This is used when reusing an existing infrastructure session for a new/selected chat session.
        """
        if self.chat_manager:
            # FIX: If chat_session_id is None, reset to the session's own ID
            # This ensures a fresh chat session is created on the next message
            self.chat_manager.session_file_id = chat_session_id or self.session_id
            logger.debug(f"WorkflowSession {self.session_id}: ChatManager session_file_id updated to {self.chat_manager.session_file_id}")
        else:
            logger.warning(f"WorkflowSession {self.session_id}: Cannot bind chat session, chat_manager not available.")

    def capture_execution_context(self, execution_context_data: Dict[str, Any]) -> None:
        """
        FULL EXECUTION CONTEXT INTEGRATION - Capture ExecutionContext data into WorkflowSession

        Converts ExecutionContext class properties into persistent WorkflowSession state.
        This replaces the need for a separate ExecutionContext class since all data
        belongs to the workflow session's execution context.

        Args:
            execution_context_data: Full ExecutionContext data that would have been passed
                                   to separate ExecutionContext class
        """
        # DIRECT PROPERTY MAPPING - ExecutionContext properties become WorkflowSession properties
        self.user_message = execution_context_data.get('user_message', '')
        self.workflow_config_data = execution_context_data.get('workflow_config')
        self.workflow_factory_func = execution_context_data.get('workflow_factory')

        # CRITICAL FIX: Update active_workflow_id from workflow config when execution context is captured
        # This ensures ChatHistoryManager uses correct workflow_id for session saving
        if self.workflow_config_data and hasattr(self.workflow_config_data, 'workflow_ID'):
            self.active_workflow_id = self.workflow_config_data.workflow_ID
            logger.debug(f"WorkflowSession {self.session_id}: Updated active_workflow_id to {self.active_workflow_id}")

        # Store execution logger for workflow operations
        self.execution_logger = execution_context_data.get('logger')

        logger.debug(f"WorkflowSession {self.session_id}: ExecutionContext captured - user_message length: {len(self.user_message)}")

    def dispose(self):
        """Clean up workflow-specific resources and CUDA memory"""
        from super_starter_suite.shared.workflow_utils import cleanup_workflow_cuda_resources

        # Cleanup CUDA memory for workflow session
        cleanup_workflow_cuda_resources(self.session_id, {
            "session_type": "workflow_session",
            "workflow_id": self.active_workflow_id
        })

        # Clear session-specific resources
        self.chat_history.clear()
        self.workflow_context.clear()
        self.workflow_state.clear()

        # Call parent dispose method
        super().dispose()

        logger.info(f"WorkflowSession {self.session_id} disposed")

    def get_session_health_status(self) -> dict:
        """Return health metrics for monitoring"""
        base = super().get_session_health_status()
        return {
            **base,
            "active_workflow": self.active_workflow_id,
            "chat_messages": len(self.chat_history),
            "execution_context_active": self.execution_context is not None,
            "workflow_context_valid": bool(self.workflow_context),
            "workflow_state": self.workflow_state
        }

    def perform_session_health_check(self) -> bool:
        """Perform actual health validation"""
        try:
            # Validate session ID
            uuid.UUID(self.session_id)
            # Validate user config
            assert self.user_config and self.user_id
            # Validate session type string
            assert isinstance(self.session_type, str) and self.session_type == "workflow_session"
            # Validate workflow contexts if active workflow exists
            if self.active_workflow_id:
                assert self.workflow_context
            return True
        except (ValueError, AssertionError):
            logger.warning(f"Health check failed for session {self.session_id}")
            return False

    def add_message(self, message: ChatMessageDTO):
        """Add a message to chat history with proper SRR delegation"""
        # Add to local workflow session cache
        self.chat_history.append(message)
        self.workflow_context["last_message_time"] = datetime.now().isoformat()

        # SRR DELEGATION: WorkflowSession always delegates to ChatHistoryManager for data operations
        # Use ChatHistoryManager as SRR for session_data operations
        if self.chat_manager:
            try:
                # Find or create the proper ChatSessionData via ChatHistoryManager
                session_data = self.chat_manager._find_or_create_session_data(
                    self.active_workflow_id or "unknown", self.session_id
                )
                if session_data:
                    self.chat_manager.add_message_to_session_data(message)
                    logger.debug(f"Added message to workflow session {self.session_id}, total messages: {len(self.chat_history)}")
                else:
                    logger.warning(f"Could not find ChatSessionData for workflow session {self.session_id}")
            except Exception as e:
                logger.error(f"Failed to add message to ChatHistoryManager: {e}")
        else:
            logger.warning(f"No ChatHistoryManager available for session {self.session_id}")

    def matches(self, user_id: str, session_type: str, **kwargs) -> bool:
        """Override matches for workflow-specific semantic matching"""
        # Call parent match (user_id and session_type)
        if not super().matches(user_id, session_type, **kwargs):
            return False
        
        # Check workflow_id if provided
        requested_workflow_id = kwargs.get('workflow_id')
        if requested_workflow_id and self.active_workflow_id != requested_workflow_id:
            return False
            
        return True

    def bind_context(self, **kwargs):
        """Override bind_context to handle chat_session_id binding"""
        # FIX: Check if chat_session_id is present in kwargs, even if it's None
        if 'chat_session_id' in kwargs:
            chat_session_id = kwargs.get('chat_session_id')
            self.bind_chat_session_id(chat_session_id)

    def generate_title(self):
        """Generate a title from the first user message (for ChatHistoryManager compatibility)"""
        from super_starter_suite.shared.dto import MessageRole
        if not self.title and self.chat_history:
            # Find the first user message
            for message in self.chat_history:
                if hasattr(message, 'role') and message.role == MessageRole.USER:
                    content = getattr(message, 'content', '').strip()
                    if content:
                        self.title = content[:50] + "..." if len(content) > 50 else content
                        break
        return self.title

    def to_dict(self) -> Dict[str, Any]:
        """Convert WorkflowSession to dictionary for JSON serialization"""
        # Construct dictionary directly from WorkflowSession properties.
        # The ChatHistoryManager (self.chat_manager) handles the actual persistence.
        
        session_data_from_manager: Optional[ChatSessionData] = None
        if self.chat_manager and self.active_workflow_id and self.chat_manager.session_file_id:
            try:
                # Load the specific chat session from the chat_manager
                session_data_from_manager = self.chat_manager.load_session(self.active_workflow_id, self.chat_manager.session_file_id)
            except Exception as e:
                logger.warning(f"WorkflowSession {self.session_id}: Could not load session data from chat_manager: {e}")

        base_dict = {
            "session_id": self.chat_manager.session_file_id if self.chat_manager and self.chat_manager.session_file_id else self.session_id, # Use chat_manager's file_id for external representation
            "user_id": self.user_id,
            "workflow_name": self.active_workflow_id or "unknown",
            "created_at": getattr(session_data_from_manager, 'created_at', datetime.now().isoformat()),
            "updated_at": getattr(session_data_from_manager, 'updated_at', datetime.now().isoformat()),
            "title": self.title or getattr(session_data_from_manager, 'title', ""),
            "messages": [msg.to_dict() for msg in self.chat_history] if self.chat_history else [],
            "metadata": getattr(session_data_from_manager, 'metadata', {}) or {},
            "active_workflow_id": self.active_workflow_id,
            "workflow_state": self.workflow_state,
            "execution_context_active": self.execution_context is not None
        }

        return base_dict

    def update_workflow_state(self, state_update: Dict[str, Any]):
        """Update workflow execution state"""
        self.workflow_state.update(state_update)
        self.workflow_context["last_state_update"] = datetime.now().isoformat()
        logger.debug(f"Updated workflow state for session {self.session_id}: {state_update}")

    def persist_session_data(self) -> bool:
        """Preserve active session mapping for resumability"""
        import json
        import os
        from pathlib import Path

        if not self.active_workflow_id:
            return True

        try:
            # Get storage path: USER_RAG_ROOT/chat_history/<workflow_id>/active_mapping.json
            storage_path = Path(self.user_config.get('my_rag_root', '/data/default')) / "chat_history" / self.active_workflow_id
            storage_path.mkdir(parents=True, exist_ok=True)
            mapping_file = storage_path / "active_mapping.json"

            # Save active session mapping
            active_mapping = {
                "workflow_id": self.active_workflow_id,
                "user_id": self.user_id,
                "last_updated": datetime.now().isoformat(),
                "session_context": {
                    "messages_count": len(self.chat_history),
                    "workflow_state": self.workflow_state,
                    "last_message_time": self.workflow_context.get("last_message_time")
                }
            }

            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(active_mapping, f, indent=2)

            logger.debug(f"Persisted active session mapping for workflow {self.active_workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to persist active session mapping: {e}")
            return False

    def get_workflow_info(self) -> Dict[str, Any]:
        """Get workflow session information"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "active_workflow_id": self.active_workflow_id,
            "message_count": len(self.chat_history),
            "workflow_state": self.workflow_state,
            "initialized": "initialized" in self.workflow_context and self.workflow_context["initialized"]
        }

    # REMOVED: from_request method with broken variable references (session/memory not defined)

    @classmethod
    def create_execution_context(cls,
        # COMMON PARAMETERS (HTTP/FastAPI layer - always present)
        request_state,              # FastAPI request.state object
        user_message: str,          # User's input message
        user_config,                # User configuration
        workflow_config,            # WorkflowConfig object
        chat_session_data,
        chat_memory
    ) -> Any:
        """
        Create complete ExecutionContext with clear parameter separation.

        Follows the healthy version's pattern where create_workflow API is directly passed
        and centrally processed in core function: execute_workflow.

        Args:
            request_state: FastAPI request.state object containing HTTP session data
            user_message: The user's input message
            user_config: User's configuration settings
            workflow_config: Complete workflow configuration object
            chat_session_data: Chat session object
            chat_memory: Chat memory manager

        Returns:
            ExecutionContext: Fully configured context for unified workflow execution
        """
        # Create ExecutionContext
        from super_starter_suite.shared.dto import ExecutionContext
        return ExecutionContext(
            # COMMON parameters
            user_message=user_message,
            user_config=user_config,

            # WORKFLOW-SPECIFIC parameters
            workflow_config=workflow_config,
            workflow_factory=None,  # Will be set by workflow loader

            # HTTP-specific parameters
            session=chat_session_data,
            chat_memory=chat_memory,
            chat_manager=None,  # Will be created if needed
        )

    def create_chat_request(self) -> Any:
        """
        Create standardized ChatRequest for ALL workflow types.

        Follows healthy version's _create_chat_request pattern:
        - Single message with USER role containing user_message
        - User ID extracted from user_config
        - Consistent format across all workflow types (adapted/ported/meta)
        """
        from llama_index.server.api.models import ChatRequest, ChatAPIMessage
        from llama_index.core.base.llms.types import MessageRole

        # Get user_message from execution_context if available, otherwise use self.user_message
        user_message = ""
        if self.execution_context and hasattr(self.execution_context, 'user_message'):
            user_message = self.execution_context.user_message
        else:
            user_message = self.user_message if hasattr(self, 'user_message') else ""

        user_id = getattr(self.user_config, 'user_id', 'default_user')

        return ChatRequest(
            messages=[ChatAPIMessage(
                role=MessageRole.USER,
                content=user_message
            )],
            id=user_id
        )

    @classmethod
    def _find_existing_chat_session_id(cls, workflow_id: str, user_config: Dict[str, Any]) -> Optional[str]:
        """Find existing chat session ID from filesystem (session_abc123.json → 'abc123')"""
        try:
            # Use scoped ChatHistoryManager by creating temporary session context
            from super_starter_suite.shared.session_utils import SessionBinder
            bound_session = SessionBinder.bind_session(user_config, "workflow_session", {"workflow_id": workflow_id})
            chat_manager = bound_session.session_handler.chat_manager
            chat_sessions = chat_manager.get_all_sessions(workflow_id)

            if chat_sessions:
                # ACTIVE DETERMINATION: Find active session or use most recent
                active_session = next((s for s in chat_sessions if getattr(s, 'is_active', False)), chat_sessions[0])
                return active_session.session_id  # ← EXTRACTED FROM FILE

        except Exception as e:
            logger.debug(f"No existing chat history for {workflow_id}: {e}")

        return None  # No existing history

    def save_to_chat_history(self, user_message: str, ai_response: Dict[str, Any], metadata: Dict = None) -> None:
        """ENHANCED: Save message with proper workflow context using ChatHistoryManager"""
        # Use inherited chat manager
        if self.chat_manager:
            from super_starter_suite.shared.dto import create_chat_message, MessageRole

            # 1. Save user message
            user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
            self.chat_manager.add_message_to_session_data(user_msg, auto_save=False)

            # 2. Save AI response with metadata
            ai_content = ai_response.get('response', '')
            ai_msg = create_chat_message(
                role=MessageRole.ASSISTANT,
                content=ai_content,
                enhanced_metadata=metadata or {}
            )
            self.chat_manager.add_message_to_session_data(ai_msg, auto_save=True) # Persist after both added

            # Update workflow state tracking
            self.workflow_state['last_interaction'] = datetime.now().isoformat()

            logger.debug(f"Saved message exchange to chat history for session {self.session_id}")
        else:
            logger.warning(f"Cannot save to chat history: ChatHistoryManager not available for session {self.session_id}")
