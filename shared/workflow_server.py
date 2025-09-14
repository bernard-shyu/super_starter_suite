"""
Workflow Server - Bridge between FastAPI and LlamaIndex workflows

This module provides a standardized bridge/adapter layer between FastAPI endpoints
and LlamaIndex workflow execution, leveraging existing framework patterns.
"""

from typing import Dict, Any, Type, Optional, Union
from dataclasses import dataclass

from llama_index.core.settings import Settings
from llama_index.server.api.models import ChatRequest, ChatAPIMessage
from llama_index.core.workflow import Workflow
from dataclasses import dataclass
from super_starter_suite.shared.config_manager import config_manager, UserConfig
from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager

@dataclass
class WorkflowEvent:
    pass
from llama_index.core.base.llms.types import MessageRole

# UNIFIED LOGGING SYSTEM - Replace global logging
server_logger = config_manager.get_logger("server")


@dataclass
class WorkflowExecutionResult:
    """Result of workflow execution"""
    success: bool
    result: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowRegistry:
    """
    Registry to manage workflow classes and their event types
    """
    def __init__(self):
        self.workflows = {}
        self.events = {}

    def register_workflow(self, name, workflow_class, event_class):
        self.workflows[name] = workflow_class
        self.events[name] = event_class

    def get_workflow(self, name):
        if name not in self.workflows:
            raise ValueError(f"Workflow '{name}' not found in registry.")
        return self.workflows.get(name)

    def get_event(self, name):
        if name not in self.events:
            raise ValueError(f"Event type for workflow '{name}' not found in registry.")
        return self.events.get(name)

class WorkflowServer:
    """
    Bridge/Adapter between FastAPI and LlamaIndex workflows

    This class provides a standardized interface for executing LlamaIndex workflows
    from FastAPI endpoints, handling the complexities of event management and
    framework compliance internally.
    """

    def __init__(self, settings, registry):
        """
        Initialize the WorkflowServer with LlamaIndex settings and registry.

        Args:
            settings: The LlamaIndex settings to use.
            registry: The WorkflowRegistry instance to use.
        """
        self.settings = settings
        self.logger = server_logger
        self.registry = registry

    async def execute_workflow(
        self,
        workflow_name: str,
        request_payload: Dict[str, Any],
        session_id: Optional[str] = None,
        user_config: Optional[UserConfig] = None
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow with proper event management and framework compliance

        Args:
            workflow_name: The name of the workflow to instantiate and execute
            request_payload: The request payload containing user input
            session_id: Optional session ID for conversation context

        Returns:
            WorkflowExecutionResult: The result of workflow execution
        """
        try:
            # Step 1: Validate and extract user input
            user_question = self._extract_user_question(request_payload)
            if not user_question:
                return WorkflowExecutionResult(
                    success=False,
                    result=None,
                    error="Request must contain a 'question' field"
                )

            # Step 2: Create ChatRequest using established patterns
            chat_request = self._create_chat_request(user_question)

            # Step 3: Get chat history memory if session_id is provided
            chat_memory = None
            if session_id and user_config:
                chat_manager = ChatHistoryManager(user_config)
                session = chat_manager.load_session(workflow_name, session_id)
                if session:
                    chat_memory = chat_manager.get_llama_index_memory(session)
                    if chat_memory:
                        self.logger.debug(f"Loaded chat memory for session {session_id}")
                    else:
                        self.logger.warning(f"Could not create chat memory for session {session_id}")

            # Step 4: Initialize workflow using reference patterns
            workflow = self._initialize_workflow(workflow_name, chat_request, chat_memory)

            # Step 5: Create framework-compliant event
            start_event = self._create_framework_event(workflow_name, user_question, chat_memory)

            # Step 5: Execute workflow with proper event handling
            result = await workflow.run(start_event)

            # Step 6: Format and return result
            return WorkflowExecutionResult(
                success=True,
                result=result,
                metadata={
                    "workflow_type": workflow_name,
                    "question_length": len(user_question)
                }
            )

        except ValueError:
            # Re-raise ValueError to indicate workflow not found
            raise
        except Exception as e:
            self.logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)

            # Log workflow execution failure using shared utility
            from super_starter_suite.shared.workflow_utils import log_workflow_execution
            log_workflow_execution(workflow_name, request_payload.get("question", ""), False, 0.0)

            return WorkflowExecutionResult(
                success=False,
                result=None,
                error=f"Workflow execution failed: {str(e)}"
            )

    def _extract_user_question(self, request_payload: Dict[str, Any]) -> Optional[str]:
        """Extract user question from request payload"""
        return request_payload.get("question", "").strip()

    def _create_chat_request(self, user_question: str) -> ChatRequest:
        """Create ChatRequest using established patterns from STARTER_TOOLS"""
        return ChatRequest(
            messages=[ChatAPIMessage(role=MessageRole.USER, content=user_question)],
            id="chat_request_id"  # Required parameter for framework
        )

    def _initialize_workflow(self, workflow_name: str, chat_request: ChatRequest, chat_memory=None) -> Workflow:
        """
        Initialize workflow using the WorkflowRegistry
        """
        workflow_class = self.registry.get_workflow(workflow_name)
        if not workflow_class:
            raise ValueError(f"Workflow {workflow_name} not found in registry")

        if workflow_name == "DeepResearchWorkflow":
            from super_starter_suite.shared.index_utils import get_rag_index
            index = get_rag_index(user_config=None)  # type: ignore
            return workflow_class(
                index=index,  # type: ignore
                timeout=400.0
            )
        return workflow_class(
            llm=self.settings.llm,
            chat_request=chat_request,
            timeout=240.0
        )

    def _create_framework_event(self, workflow_name: str, user_question: str, chat_memory=None):
        """
        Create framework-compliant events using the WorkflowRegistry
        """
        event_class = self.registry.get_event(workflow_name)
        if not event_class:
            raise ValueError(f"Event for workflow {workflow_name} not found in registry")

        if workflow_name == "DeepResearchWorkflow":
            start_event = event_class()
            start_event.user_msg = user_question
            start_event.chat_history = []
            return start_event

        return event_class(user_msg=user_question, context="")

    def get_supported_workflows(self) -> Dict[str, Type[Workflow]]:
        """Get mapping of supported workflow types"""
        return {
            "code_generator": self._get_code_generator_workflow(),
            "document_generator": self._get_document_generator_workflow(),
            "deep_research": self._get_deep_research_workflow(),
            "financial_report": self._get_financial_report_workflow(),
            "human_in_the_loop": self._get_human_in_the_loop_workflow(),
        }

    def _get_code_generator_workflow(self):
        """Get CodeArtifactWorkflow class"""
        from super_starter_suite.STARTER_TOOLS.code_generator.app.workflow import CodeArtifactWorkflow
        return CodeArtifactWorkflow

    def _get_document_generator_workflow(self):
        """Get DocumentArtifactWorkflow class"""
        from super_starter_suite.STARTER_TOOLS.document_generator.app.workflow import DocumentArtifactWorkflow
        return DocumentArtifactWorkflow

    def _get_deep_research_workflow(self):
        """Get DeepResearchWorkflow class"""
        from super_starter_suite.STARTER_TOOLS.deep_research.app.workflow import DeepResearchWorkflow
        return DeepResearchWorkflow

    def _get_financial_report_workflow(self):
        """Get FinancialReportWorkflow class (placeholder)"""
        # This will be implemented based on actual workflow structure
        from llama_index.core.workflow import Workflow
        return Workflow  # Placeholder

    def _get_human_in_the_loop_workflow(self):
        """Get HumanInTheLoopWorkflow class (placeholder)"""
        # This will be implemented based on actual workflow structure
        from llama_index.core.workflow import Workflow
        return Workflow  # Placeholder


# Global instance for easy access
# workflow_server = WorkflowServer()
