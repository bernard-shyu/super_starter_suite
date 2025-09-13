import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request
from fastapi.responses import HTMLResponse
from super_starter_suite.workflow_adapters.agentic_rag import chat_endpoint as AgenticRagWorkflowAdapter
from super_starter_suite.shared.workflow_server import WorkflowServer

@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object with required state."""
    request = MagicMock(spec=Request)
    request.method = "POST"
    request.url = "http://testserver/chat"

    # Create a proper state object
    state = MagicMock()
    state.user_id = "Default"
    state.user_config = {"test": "config"}
    request.state = state
    return request

@pytest.fixture
def workflow_server_mock():
    return MagicMock(spec=WorkflowServer)

@pytest.fixture
def agentic_rag_adapter(workflow_server_mock):
    return AgenticRagWorkflowAdapter

@pytest.mark.asyncio
async def test_agentic_rag_adapter_execute(agentic_rag_adapter, mock_request):
    payload = {"question": "test query"}
    with patch('super_starter_suite.workflow_adapters.agentic_rag.create_workflow') as mock_create_workflow:
        mock_workflow = AsyncMock()
        # Create a proper mock result object
        mock_result = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "test result"
        mock_result.response = mock_response

        # Mock the __str__ method properly
        def mock_str(self):
            return "test result"
        mock_result.__str__ = mock_str

        mock_workflow.run.return_value = mock_result
        mock_create_workflow.return_value = mock_workflow

        result = await agentic_rag_adapter(mock_request, payload)
        assert result.status_code == 200
        assert "test result" in result.body.decode()

@pytest.mark.asyncio
async def test_agentic_rag_adapter_execute_error(agentic_rag_adapter, mock_request):
    payload = {"question": "test query"}
    with patch('super_starter_suite.workflow_adapters.agentic_rag.create_workflow') as mock_create_workflow:
        mock_workflow = AsyncMock()
        mock_workflow.run.side_effect = Exception("Workflow execution failed")
        mock_create_workflow.return_value = mock_workflow

        result = await agentic_rag_adapter(mock_request, payload)
        assert result.status_code == 500
        assert "Workflow execution failed" in result.body.decode()
