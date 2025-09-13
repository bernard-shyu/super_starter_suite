import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from super_starter_suite.shared.workflow_server import WorkflowRegistry, WorkflowServer, WorkflowEvent
from super_starter_suite.shared.workflow_utils import create_workflow_factory
from llama_index.core.settings import Settings

# Define dummy workflow classes and event types for testing
@dataclass
class DummyWorkflowEvent(WorkflowEvent):
    user_msg: str = ""
    context: str = ""

@dataclass
class AnotherDummyWorkflowEvent(WorkflowEvent):
    user_msg: str = ""
    context: str = ""

class DummyWorkflow:
    def __init__(self, llm=None, chat_request=None, timeout=240.0):
        self.llm = llm
        self.chat_request = chat_request
        self.timeout = timeout

    async def run(self, event):
        return f"Success: {event.user_msg}"

class AnotherDummyWorkflow:
    def __init__(self, llm=None, chat_request=None, timeout=240.0):
        self.llm = llm
        self.chat_request = chat_request
        self.timeout = timeout

    async def run(self, event):
        return f"Another Success: {event.user_msg}"

@pytest.fixture
def workflow_registry():
    registry = WorkflowRegistry()
    # Register dummy workflows for testing
    registry.register_workflow("DummyWorkflow", DummyWorkflow, DummyWorkflowEvent)
    registry.register_workflow("AnotherDummyWorkflow", AnotherDummyWorkflow, AnotherDummyWorkflowEvent)
    return registry

@pytest.fixture
def workflow_server(workflow_registry):
    settings_mock = MagicMock()
    settings_mock.llm = MagicMock()
    return WorkflowServer(settings_mock, workflow_registry)

def test_workflow_registry_register_and_get_workflow():
    workflow_registry = WorkflowRegistry()
    workflow_registry.register_workflow("DummyWorkflow", DummyWorkflow, DummyWorkflowEvent)
    retrieved_workflow = workflow_registry.get_workflow("DummyWorkflow")
    assert retrieved_workflow == DummyWorkflow

def test_workflow_registry_get_event_type():
    workflow_registry = WorkflowRegistry()
    workflow_registry.register_workflow("DummyWorkflow", DummyWorkflow, DummyWorkflowEvent)
    retrieved_event_type = workflow_registry.get_event("DummyWorkflow")
    assert retrieved_event_type == DummyWorkflowEvent

def test_workflow_registry_workflow_not_found():
    workflow_registry = WorkflowRegistry()
    with pytest.raises(ValueError, match="Workflow 'NonExistentWorkflow' not found in registry."):
        workflow_registry.get_workflow("NonExistentWorkflow")
        workflow_registry.register_workflow("NonExistentWorkflow", DummyWorkflow, DummyWorkflowEvent)

def test_workflow_registry_event_type_not_found():
    workflow_registry = WorkflowRegistry()
    with pytest.raises(ValueError, match="Event type for workflow 'NonExistentWorkflow' not found in registry."):
        workflow_registry.get_event("NonExistentWorkflow")
        workflow_registry.register_workflow("NonExistentWorkflow", DummyWorkflow, DummyWorkflowEvent)

@pytest.mark.asyncio
async def test_execute_workflow_success(workflow_server):
    payload = {"question": "test query"}
    result = await workflow_server.execute_workflow("DummyWorkflow", payload)
    assert result.success
    assert result.result == "Success: test query"

@pytest.mark.asyncio
async def test_execute_workflow_not_found(workflow_server):
    payload = {"question": "test query"}
    with pytest.raises(ValueError, match="Workflow 'NonExistentWorkflow' not found in registry."):
        await workflow_server.execute_workflow("NonExistentWorkflow", payload)

@pytest.mark.asyncio
async def test_execute_workflow_exception_handling(workflow_server):
    @dataclass
    class ErrorWorkflowEvent(WorkflowEvent):
        user_msg: str = ""
        context: str = ""

    class ErrorWorkflow:
        workflow_name = "ErrorWorkflow"
        event_type = ErrorWorkflowEvent

        def __init__(self, llm=None, chat_request=None, timeout=240.0):
            self.llm = llm
            self.chat_request = chat_request
            self.timeout = timeout

        async def run(self, event):
            raise Exception("Workflow execution failed")

    workflow_server.registry.register_workflow("ErrorWorkflow", ErrorWorkflow, ErrorWorkflowEvent)
    payload = {"question": "error test"}

    with patch('super_starter_suite.shared.workflow_utils.log_workflow_execution') as mock_log:
        result = await workflow_server.execute_workflow("ErrorWorkflow", payload)
        assert result.success == False
        assert "Workflow execution failed" in result.error
        mock_log.assert_called_once()
        assert "ErrorWorkflow" in mock_log.call_args[0][0] # Check workflow name in log

@pytest.mark.asyncio
async def test_initialize_workflow(workflow_server):
    chat_request = MagicMock()
    workflow_instance = workflow_server._initialize_workflow("DummyWorkflow", chat_request)
    assert isinstance(workflow_instance, DummyWorkflow)
    assert workflow_instance.llm == workflow_server.settings.llm
    assert workflow_instance.chat_request == chat_request

@pytest.mark.asyncio
async def test_create_framework_event(workflow_server):
    payload = {"question": "test question"}
    event = workflow_server._create_framework_event("DummyWorkflow", payload["question"])
    assert isinstance(event, DummyWorkflowEvent)
    assert event.user_msg == "test question"
