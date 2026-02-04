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

@dataclass
class WorkflowEvent:
    pass
from llama_index.core.base.llms.types import MessageRole

# UNIFIED LOGGING SYSTEM - Replace global logging
server_logger = config_manager.get_logger("workflow.utils")


@dataclass
class WorkflowExecutionResult:
    """Result of workflow execution"""
    success: bool
    result: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowRegistry:
    """
    Registry to manage workflow classes, their event types, and their initializers.
    """
    def __init__(self):
        self.workflows = {}
        self.events = {}
        self.initializers = {} # New: Store workflow initializers

    def register_workflow(self, name: str, workflow_class: Type[Any], event_class: Optional[Type[Any]], initializer: Optional[Type[Any]]):
        self.workflows[name] = workflow_class
        self.events[name] = event_class
        self.initializers[name] = initializer # Register the initializer

    def get_workflow(self, name: str) -> Type[Any]:
        if name not in self.workflows:
            raise ValueError(f"Workflow '{name}' not found in registry.")
        return self.workflows[name]

    def get_event(self, name: str) -> Type[Any]:
        event_class = self.events.get(name)
        if event_class is None:
            # If event class is None, try to create a default WorkflowEvent
            return WorkflowEvent
        return event_class

    def get_initializer(self, name: str) -> Optional[Type[Any]]:
        """
        Get the initializer class/method for a specific workflow.
        """
        return self.initializers.get(name)

class WorkflowServer:
    """
    Bridge/Adapter between FastAPI and LlamaIndex workflows

    This class provides a standardized interface for executing LlamaIndex workflows
    from FastAPI endpoints, handling the complexities of event management and
    framework compliance internally. Now supports dynamic workflow loading.
    """

    def __init__(self, settings, workflow_configs=None):
        """
        Initialize the WorkflowServer with LlamaIndex settings and optional workflow configs.

        Args:
            settings: The LlamaIndex settings to use.
            workflow_configs: Optional dict of workflow configurations for dynamic loading.
        """
        self.settings = settings
        self.logger = server_logger
        self.registry = WorkflowRegistry()

        # Dynamic workflow loading if configs provided
        if workflow_configs:
            self._load_dynamic_workflows(workflow_configs)
        else:
            # Fallback to legacy registry population for backward compatibility
            self.logger.warning("No workflow configurations provided. Using backward compatibility mode.")

    def _load_dynamic_workflows(self, workflow_configs):
        """
        Dynamically load workflows from configuration and populate the registry.

        Args:
            workflow_configs: Dict of workflow configurations keyed by workflow_id
        """
        from super_starter_suite.shared.workflow_loader import load_workflow_module

        for workflow_id, workflow_config in workflow_configs.items():
            try:
                # Load the workflow module, router, and classes, including the initializer
                _, workflow_class, event_class, initializer = load_workflow_module(workflow_id, workflow_config)

                # Register in our workflow registry if we have the classes
                if workflow_class:
                    self.registry.register_workflow(workflow_id, workflow_class, event_class, initializer)
                    self.logger.info(f"Registered workflow '{workflow_id}' dynamically")
                else:
                    self.logger.warning(f"Could not register workflow '{workflow_id}': missing workflow class")

            except Exception as e:
                self.logger.error(f"Failed to load workflow '{workflow_id}': {e}")
                # Continue loading other workflows

    def _extract_user_question(self, request_payload: Dict[str, Any]) -> Optional[str]:
        """Extract user question from request payload"""
        return request_payload.get("question", "").strip()

    def _create_chat_request(self, user_question: str) -> ChatRequest:
        """Create ChatRequest using established patterns from STARTER_TOOLS"""
        return ChatRequest(
            messages=[ChatAPIMessage(role=MessageRole.USER, content=user_question)],
            id="chat_request_id"  # Required parameter for framework
        )

    def _initialize_workflow(self, workflow_name: str, chat_request: ChatRequest, chat_memory: Optional[Any] = None, user_config: Optional[UserConfig] = None) -> Workflow:
        """
        Initialize workflow using the WorkflowRegistry, leveraging specific initializers if available.
        """
        initializer = self.registry.get_initializer(workflow_name)
        if initializer:
            self.logger.debug(f"Using specific initializer for workflow '{workflow_name}'")
            # Call the static initialize method on the initializer class
            workflow, _ = initializer.initialize(
                settings=self.settings,
                chat_request=chat_request,
                user_question=chat_request.messages[0].content, # Assuming first message is user question
                user_config=user_config,
                chat_memory=chat_memory
            )
            return workflow
        else:
            self.logger.debug(f"Using generic initialization for workflow '{workflow_name}'")
            workflow_class = self.registry.get_workflow(workflow_name)
            if not workflow_class:
                raise ValueError(f"Workflow {workflow_name} not found in registry")

            # Generic initialization for workflows without a specific initializer
            return workflow_class(
                llm=self.settings.llm,
                chat_request=chat_request,
                timeout=240.0 # Default timeout
            )

    def _create_framework_event(self, workflow_name: str, user_question: str, chat_memory: Optional[Any] = None, user_config: Optional[UserConfig] = None):
        """
        Create framework-compliant events using the WorkflowRegistry, leveraging specific initializers if available.
        """
        initializer = self.registry.get_initializer(workflow_name)
        if initializer:
            self.logger.debug(f"Using specific initializer for event creation for workflow '{workflow_name}'")
            # If an initializer exists, it should also handle event creation
            # We already get the workflow and event from initializer.initialize, so we just need the event
            _, start_event = initializer.initialize(
                settings=self.settings,
                chat_request=ChatRequest(messages=[ChatAPIMessage(role=MessageRole.USER, content=user_question)]),
                user_question=user_question,
                user_config=user_config,
                chat_memory=chat_memory
            )
            return start_event
        else:
            self.logger.debug(f"Using generic event creation for workflow '{workflow_name}'")
            event_class = self.registry.get_event(workflow_name)
            if not event_class:
                raise ValueError(f"Event for workflow {workflow_name} not found in registry")

            # Generic event creation for workflows without a specific initializer
            try:
                return event_class(user_msg=user_question, context="")
            except TypeError:
                try:
                    return event_class(user_msg=user_question)
                except TypeError:
                    start_event = event_class()
                    if hasattr(start_event, 'user_msg'):
                        start_event.user_msg = user_question
                    if hasattr(start_event, 'message'):
                        start_event.message = user_question
                    if hasattr(start_event, 'question'):
                        start_event.question = user_question
                    return start_event

# Global instance for easy access
# workflow_server = WorkflowServer()
