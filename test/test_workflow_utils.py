import pytest
import logging
from unittest.mock import MagicMock
from super_starter_suite.shared.workflow_utils import (
    create_workflow_factory,
    create_event_factory,
    validate_workflow_payload,
    create_error_response,
    log_workflow_execution
)

def test_create_workflow_factory():
    workflow_server_mock = MagicMock()
    workflow_factory = create_workflow_factory(workflow_server_mock)
    workflow_instance = workflow_factory("DummyWorkflow")
    assert isinstance(workflow_instance, MagicMock)
    workflow_server_mock.registry.get_workflow.assert_called_once_with("DummyWorkflow")

def test_create_event_factory():
    workflow_server_mock = MagicMock()
    event_factory = create_event_factory(workflow_server_mock)
    event_instance = event_factory("DummyWorkflow", "Test question")
    assert isinstance(event_instance, MagicMock)
    workflow_server_mock.registry.get_event.assert_called_once_with("DummyWorkflow")

def test_validate_workflow_payload():
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

def test_create_error_response():
    error_html, status_code = create_error_response("Test error", "DummyWorkflow")
    assert "Error in DummyWorkflow Workflow" in error_html
    assert status_code == 500

def test_log_workflow_execution(caplog):
    # Configure the logger to work with caplog
    logger = logging.getLogger('super_starter_suite.shared.workflow_utils')
    logger.setLevel(logging.INFO)

    log_workflow_execution("DummyWorkflow", "Test question", True, 1.23)
    assert "DummyWorkflow workflow executed successfully" in caplog.text
    assert "1.23 seconds" in caplog.text
    assert "Test question" in caplog.text

    log_workflow_execution("DummyWorkflow", "Test question", False, 0.56)
    assert "DummyWorkflow workflow executed unsuccessfully" in caplog.text
    assert "0.56 seconds" in caplog.text
    assert "Test question" in caplog.text
