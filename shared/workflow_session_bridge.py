"""
Workflow Session Bridge - Unified Chat History Session Management

This module provides a minimal bridge layer for unified session management
across all workflows, standardizing the "always create sessions" pattern
established by the working Agentic RAG workflow.

Provides:
- Unified session creation/loading that works consistently across all workflows
- Standardized chat memory integration for conversation context
- Consistent message persistence and response saving
- Cross-workflow Chat History support
"""

from typing import Optional, Dict, Any
from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from super_starter_suite.shared.config_manager import UserConfig, config_manager

# Import LlamaIndex ChatMemoryBuffer for unified memory integration
from llama_index.core.memory import ChatMemoryBuffer

# UNIFIED LOGGING SYSTEM
bridge_logger = config_manager.get_logger("workflow.utils")


class WorkflowSessionBridge:
    """
    Minimal bridge for unified session management across all workflows

    This bridge standardizes the session handling pattern established by
    Agentic RAG, providing consistent behavior across all 12 workflows
    without requiring major changes to existing workflow implementations.
    """

    @staticmethod
    def ensure_chat_session(workflow_name: str, user_config: UserConfig,
                           session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Unified session management - ALWAYS creates/loads session

        Standardizes the pattern used by working Agentic RAG workflow:
        - Always returns a valid session object
        - Consistent memory integration
        - No conditional logic based on session_id presence

        Args:
            workflow_name: Name of the workflow (e.g., 'agentic_rag', 'code_generator')
            user_config: UserConfig instance
            session_id: Optional existing session ID (will load or create new)

        Returns:
            dict: {
                'session': session,      # ChatSession object
                'is_new': bool,         # Whether this is a newly created session
                'memory': chat_memory   # LlamaIndex ChatMemoryBuffer or None
            }
        """
        try:
            chat_manager = ChatHistoryManager(user_config)
            user_id = getattr(user_config, 'user_id', 'Default')

            bridge_logger.debug(f"Setting up session for {workflow_name}")

            session = None
            is_new_session = False

            if session_id is not None and session_id != "new":
                # CRITICAL FIX: Load specific session if session_id provided and not 'new'
                # RESUME BEHAVIOR: Must load the requested session, not the active one
                bridge_logger.debug(f"Loading specific session {session_id} for workflow {workflow_name}")
                session = chat_manager.load_session(workflow_name, session_id)

                if session:
                    bridge_logger.debug(f"Successfully loaded session {session_id} for workflow {workflow_name}")
                    is_new_session = False
                else:
                    bridge_logger.warning(f"Session {session_id} not found in {workflow_name}, creating new session")
                    session = chat_manager.create_new_session(workflow_name)
                    is_new_session = True
            else:
                # NEW SESSION BEHAVIOR: When session_id is None or "new", find or create the active session for this workflow
                # This ensures ONE ACTIVE SESSION per workflow policy for spontaneous/continuing conversations
                from super_starter_suite.chat_bot.chat_history.chat_history_manager import SessionLifecycleManager

                session_lifecycle = SessionLifecycleManager(user_id, chat_manager)
                active_session_id = session_lifecycle.get_active_session_id(workflow_name)

                if active_session_id:
                    # Use existing active session
                    session = chat_manager.load_session(workflow_name, active_session_id)
                    if session:
                        bridge_logger.debug(f"Using existing active session {active_session_id} for {workflow_name}")
                        is_new_session = False
                    else:
                        # Active session mapping exists but session file is missing - create new one
                        bridge_logger.warning(f"Active session {active_session_id} file missing for {workflow_name}, creating new session")
                        session = chat_manager.create_new_session(workflow_name)
                        # Update the lifecycle mapping with the new session
                        session_lifecycle.workflow_sessions[workflow_name] = session.session_id
                        session_lifecycle._save_mappings()
                        is_new_session = True
                else:
                    # No active session - create new one and make it active
                    session = chat_manager.create_new_session(workflow_name)
                    session_lifecycle.workflow_sessions[workflow_name] = session.session_id
                    session_lifecycle._save_mappings()
                    bridge_logger.debug(f"Created new active session {session.session_id} for workflow {workflow_name}")
                    is_new_session = True

            # REGISTER SESSION WITH SessionAuthority FOR FRONTEND COORDINATION
            # This ensures SessionAuthority knows about sessions created by WorkflowSessionBridge
            # So frontend can get active session ID via /api/workflow_sessions/{workflow}/id
            user_id = getattr(user_config, 'user_id', 'Default')
            # Import locally to avoid circular import
            from super_starter_suite.chat_bot.session_authority import session_authority
            session_authority.registry.register_session(user_id, workflow_name, session.session_id)
            bridge_logger.debug(f"Registered session {session.session_id[:8]}... with SessionAuthority for {workflow_name}")

            # Always get memory for conversation context
            # Note: Each session gets its own memory object, so no sharing across sessions
            memory = chat_manager.get_llama_index_memory(session)

            return {
                'session': session,
                'is_new': session_id is None,  # True if no session_id was provided initially
                'memory': memory
            }

        except Exception as e:
            bridge_logger.error(f"Failed to ensure chat session for workflow {workflow_name}: {e}")
            raise

    @staticmethod
    def add_message_and_save_response(workflow_name: str, user_config: UserConfig,
                                    session, user_message: str, response_content: str):
        """
        Unified message handling and response saving

        Standardizes the pattern used by working Agentic RAG workflow:
        - Add user message to session
        - Save assistant response to session
        - Consistent error handling

        Args:
            workflow_name: Name of the workflow
            user_config: UserConfig instance
            session: ChatSession object
            user_message: User's question/message
            response_content: AI response content
        """
        try:
            chat_manager = ChatHistoryManager(user_config)

            # Add user message to session
            user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
            chat_manager.add_message_to_session(session, user_msg)

            # Save assistant response to session
            assistant_msg = create_chat_message(role=MessageRole.ASSISTANT, content=response_content)
            chat_manager.add_message_to_session(session, assistant_msg)

            bridge_logger.debug(f"Saved conversation exchange to session {session.session_id} for workflow {workflow_name}")

        except Exception as e:
            bridge_logger.error(f"Failed to save chat exchange for workflow {workflow_name}: {e}")
            raise

    @staticmethod
    def get_existing_session(workflow_name: str, user_config: UserConfig, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get existing session without creating new one (DECORATOR USE ONLY)

        This method retrieves an existing session that was created by ensure_chat_session().
        Used by decorators to reuse sessions created by executor endpoints.

        CRITICAL SECURITY: Validates session belongs to current user to prevent cross-contamination.

        Args:
            workflow_name: Name of the workflow
            user_config: UserConfig instance
            session_id: Session ID to retrieve (if known), or None to find active session

        Returns:
            session_data dict or None if session not found or access denied
        """
        try:
            chat_manager = ChatHistoryManager(user_config)
            current_user_id = getattr(user_config, 'user_id', 'Default')

            # If session_id provided, load specific session with ownership validation
            if session_id:
                session = chat_manager.load_session(workflow_name, session_id)
                if session:
                    # CRITICAL: Validate session ownership to prevent cross-contamination
                    if session.user_id != current_user_id:
                        bridge_logger.warning(f"Session {session_id} access denied: belongs to user '{session.user_id}' not '{current_user_id}'")
                        return None

                    memory = chat_manager.get_llama_index_memory(session)
                    return {
                        'session': session,
                        'memory': memory,
                        'is_existing': True
                    }
                return None

            # Find active session for this workflow with ownership validation
            from super_starter_suite.chat_bot.chat_history.chat_history_manager import SessionLifecycleManager

            session_lifecycle = SessionLifecycleManager(current_user_id, chat_manager)
            active_session_id = session_lifecycle.get_active_session_id(workflow_name)

            if active_session_id:
                session = chat_manager.load_session(workflow_name, active_session_id)
                if session:
                    # CRITICAL: Validate session ownership to prevent cross-contamination
                    if session.user_id != current_user_id:
                        bridge_logger.warning(f"Active session {active_session_id} access denied: belongs to user '{session.user_id}' not '{current_user_id}'")
                        return None

                    memory = chat_manager.get_llama_index_memory(session)
                    return {
                        'session': session,
                        'memory': memory,
                        'is_existing': True
                    }

            return None

        except Exception as e:
            bridge_logger.error(f"Failed to get existing session for {workflow_name}: {e}")
            return None

    @staticmethod
    def get_session_info(workflow_name: str, user_config: UserConfig, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information for frontend display

        Args:
            workflow_name: Name of the workflow
            user_config: UserConfig instance
            session_id: Session ID to retrieve

        Returns:
            dict: Session info with message count, timestamps, etc. or None if not found
        """
        try:
            chat_manager = ChatHistoryManager(user_config)
            session = chat_manager.load_session(workflow_name, session_id)

            if not session:
                return None

            # Get basic session information
            return {
                'session_id': session.session_id,
                'workflow': workflow_name,
                'message_count': len(session.messages),
                'created_at': getattr(session, 'created_at', None),
                'updated_at': getattr(session, 'updated_at', None)
            }

        except Exception as e:
            bridge_logger.error(f"Failed to get session info for {workflow_name}:{session_id}: {e}")
            return None

    @staticmethod
    def initialize_memory_buffer() -> ChatMemoryBuffer:
        """
        Create standardized LlamaIndex ChatMemoryBuffer for workflows

        Returns a properly configured ChatMemoryBuffer that works consistently
        across all workflows, matching the SessionManager.ChatMemoryBuffer pattern.

        Returns:
            ChatMemoryBuffer: Configured memory buffer for conversation context
        """
        return ChatMemoryBuffer.from_defaults()

    @staticmethod
    def prepare_workflow_memory(session_data: Dict[str, Any]) -> Optional[ChatMemoryBuffer]:
        """
        Prepare LlamaIndex memory from session data for workflow execution

        Args:
            session_data: Session data dict from ensure_chat_session()

        Returns:
            ChatMemoryBuffer or None: Ready-to-use memory for workflow
        """
        memory = session_data.get('memory')
        if memory and isinstance(memory, ChatMemoryBuffer):
            return memory
        return None

    @staticmethod
    def cleanup_memory(memory_object):
        """
        Explicit cleanup of chat memory objects to prevent CUDA memory leaks

        Args:
            memory_object: LlamaIndex ChatMemoryBuffer or similar memory object
        """
        if memory_object is not None:
            try:
                # Clear any cached data
                if hasattr(memory_object, 'clear'):
                    memory_object.clear()

                # Force explicit cleanup if available
                if hasattr(memory_object, 'cleanup'):
                    memory_object.cleanup()

                # Delete the object reference to free GPU memory
                del memory_object

                bridge_logger.debug("Memory object cleaned up successfully")

            except Exception as e:
                bridge_logger.warning(f"Failed to cleanup memory object: {e}")

    @staticmethod
    def cleanup_session_workflow(workflow_name: str, user_config: UserConfig, session_data: Dict[str, Any]):
        """
        Cleanup workflow session memory when workflow execution ends

        Should be called after workflow completes to prevent CUDA memory leaks.

        Args:
            workflow_name: Name of the workflow
            user_config: UserConfig instance
            session_data: Session data dict from ensure_chat_session()
        """
        try:
            memory_object = session_data.get('memory')
            if memory_object:
                WorkflowSessionBridge.cleanup_memory(memory_object)
                bridge_logger.debug(f"Cleaned up session memory for workflow {workflow_name}")

        except Exception as e:
            bridge_logger.error(f"Failed to cleanup session for workflow {workflow_name}: {e}")


class UnifiedWorkflowMixin:
    """
    Optional mixin class for workflows to adopt unified session handling

    Provides a clean interface for workflows that want to standardize
    their session handling without breaking existing patterns.
    """

    def __init__(self, workflow_name: str, user_config: UserConfig):
        self.workflow_name = workflow_name
        self.user_config = user_config

    def setup_chat_session(self, session_id: Optional[str] = None):
        """
        Workflow method to setup chat session using bridge

        Call this early in chat_endpoint method before workflow execution.

        Returns:
            dict: Session setup information {'session': session, 'memory': memory, etc.}
        """
        return WorkflowSessionBridge.ensure_chat_session(
            self.workflow_name, self.user_config, session_id
        )

    def persist_chat_exchange(self, user_message: str, response_content: str):
        """
        Workflow method to persist conversation using bridge

        Call this after workflow execution and response formatting.

        Assumes self.session is set from setup_chat_session()
        """
        # Type ignore because session attribute is set dynamically in setup_chat_session
        session = getattr(self, 'session', None)  # type: ignore
        if session is None:
            raise ValueError("setup_chat_session() must be called before persist_chat_exchange()")

        WorkflowSessionBridge.add_message_and_save_response(
            self.workflow_name, self.user_config, session,
            user_message, response_content
        )


# Usage Examples:
#
# 1. Direct usage (recommended for existing workflows):
#
#    session_data = WorkflowSessionBridge.ensure_chat_session(
#        "code_generator", user_config, session_id
#    )
#    session = session_data['session']
#    memory = session_data['memory']
#
#    # ... execute workflow ...
#
#    WorkflowSessionBridge.add_message_and_save_response(
#        "code_generator", user_config, session, user_message, response
#    )
#
# 2. Mixin usage (for new workflows):
#
#    class CodeGeneratorWorkflow(Workflow, UnifiedWorkflowMixin):
#        def __init__(self):
#            super().__init__("code_generator", user_config)
#
#        async def run(self, ctx):
#            # Session setup happens automatically
#            session_data = self.setup_chat_session(session_id)
#
#            # ... workflow logic ...
#
#            self.persist_chat_exchange(user_message, response)
