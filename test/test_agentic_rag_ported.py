import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request
from fastapi.responses import HTMLResponse
from super_starter_suite.workflow_porting.agentic_rag import chat_endpoint as AgenticRagPortedWorkflow
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
import logging
import time

logger = logging.getLogger(__name__)

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
def agentic_rag_ported_workflow():
    return AgenticRagPortedWorkflow

@pytest.mark.asyncio
async def test_agentic_rag_ported_workflow_execute(agentic_rag_ported_workflow, mock_request):
    payload = {"question": "test query"}
    with patch('super_starter_suite.workflow_porting.agentic_rag.validate_workflow_payload', return_value=(True, None)):
        with patch('super_starter_suite.workflow_porting.agentic_rag.create_workflow') as mock_create_workflow:
            mock_workflow = AsyncMock()
            # Mock the new result format with response.content structure
            mock_result = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "test result"
            mock_result.response = mock_response
            mock_workflow.run.return_value = mock_result
            mock_create_workflow.return_value = mock_workflow

            result = await agentic_rag_ported_workflow(mock_request, payload)
            assert result.status_code == 200
            assert "test result" in result.body.decode()

@pytest.mark.asyncio
async def test_agentic_rag_ported_workflow_execute_error(agentic_rag_ported_workflow, mock_request):
    payload = {"question": "test query"}
    with patch('super_starter_suite.workflow_porting.agentic_rag.validate_workflow_payload', return_value=(True, None)):
        with patch('super_starter_suite.workflow_porting.agentic_rag.create_workflow') as mock_create_workflow:
            mock_workflow = AsyncMock()
            mock_workflow.run.side_effect = Exception("Workflow execution failed")
            mock_create_workflow.return_value = mock_workflow

            result = await agentic_rag_ported_workflow(mock_request, payload)
            assert result.status_code == 500
            assert "Workflow execution failed" in result.body.decode()

@pytest.mark.asyncio
async def test_agentic_rag_ported_workflow_validate_payload():
    payload = {"question": "Test question"}
    is_valid, error_message = validate_workflow_payload(payload)
    assert is_valid is True
    assert error_message == ""

    invalid_payload = {}
    is_valid, error_message = validate_workflow_payload(invalid_payload)
    assert is_valid is False
    assert error_message == "Request must contain a 'question' field"

    empty_question_payload = {"question": "   "}
    is_valid, error_message = validate_workflow_payload(empty_question_payload)
    assert is_valid is False
    assert error_message == "Question field cannot be empty"

@pytest.mark.asyncio
async def test_agentic_rag_ported_workflow_create_error_response():
    error_html, status_code = create_error_response("Test error", "Agentic RAG")
    assert "Error in Agentic RAG Workflow" in error_html
    assert status_code == 500

@pytest.mark.asyncio
async def test_agentic_rag_ported_workflow_log_execution(caplog):
    with caplog.at_level(logging.INFO):
        log_workflow_execution("Agentic RAG", "Test question", True, 1.23)
        assert "Agentic RAG workflow executed successfully" in caplog.text
        assert "1.23 seconds" in caplog.text
        assert "Test question" in caplog.text

        log_workflow_execution("Agentic RAG", "Test question", False, 0.56)
        assert "Agentic RAG workflow executed unsuccessfully" in caplog.text
        assert "0.56 seconds" in caplog.text
        assert "Test question" in caplog.text
