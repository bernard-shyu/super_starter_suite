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
from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from super_starter_suite.shared.config_manager import UserConfig, config_manager

# Import LlamaIndex ChatMemoryBuffer for unified memory integration
from llama_index.core.memory import ChatMemoryBuffer

# UNIFIED LOGGING SYSTEM
bridge_logger = config_manager.get_logger("workflow")


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

            # ALWAYS create/load session - no conditional logic
            if session_id is not None:
                # Load existing session if session_id provided
                session = chat_manager.load_session(workflow_name, session_id)
            else:
                session = None

            if not session:
                session = chat_manager.create_new_session(workflow_name)
                if session_id is None:
                    bridge_logger.debug(f"Created new session {session.session_id} for workflow {workflow_name}")
                else:
                    bridge_logger.debug(f"Session {session_id} not found, created new session {session.session_id} for workflow {workflow_name}")

            # Always get memory for conversation context
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
