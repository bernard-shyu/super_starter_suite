"""
Tests for Multi-Agent Coordinator

This module contains unit tests for the MultiAgentCoordinator and related components.
Tests cover:
- Pipeline configuration validation
- Sequential pipeline execution
- Parallel pipeline execution
- Error handling and fault tolerance
- Shared memory context management
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from super_starter_suite.shared.multi_agent_coordinator import (
    MultiAgentCoordinator,
    PipelineConfig,
    AgentStep,
    AgentTransition,
    SharedMemoryContext,
    WorkflowAdapterFactory,
    PipelineResult
)
from super_starter_suite.shared.config_manager import config_manager


class TestPipelineConfig:
    """Test PipelineConfig functionality"""

    def test_valid_pipeline_config(self):
        """Test pipeline configuration validation with valid data"""
        config = PipelineConfig(
            pipeline_name="test_pipeline",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag"),
                AgentStep(agent_id="step2", workflow_name="code_generator")
            ],
            transition_type=AgentTransition.SEQUENTIAL
        )

        assert config.validate() == True

    def test_invalid_pipeline_config_empty_name(self):
        """Test pipeline configuration validation with empty name"""
        config = PipelineConfig(
            pipeline_name="",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag")
            ]
        )

        assert config.validate() == False

    def test_invalid_pipeline_config_duplicate_step_ids(self):
        """Test pipeline configuration validation with duplicate step IDs"""
        config = PipelineConfig(
            pipeline_name="test_pipeline",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag"),
                AgentStep(agent_id="step1", workflow_name="code_generator")  # Duplicate ID
            ]
        )

        assert config.validate() == False

    def test_invalid_pipeline_config_invalid_conditional_reference(self):
        """Test pipeline configuration validation with invalid conditional reference"""
        config = PipelineConfig(
            pipeline_name="test_pipeline",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag", conditional_next="nonexistent")
            ]
        )

        assert config.validate() == False


class TestSharedMemoryContext:
    """Test SharedMemoryContext functionality"""

    def test_shared_memory_initialization(self):
        """Test shared memory context initialization"""
        context = SharedMemoryContext()

        assert context.pipeline_id is not None
        assert isinstance(context.shared_variables, dict)
        assert len(context.execution_log) == 0
        assert len(context.step_results) == 0

    def test_add_step_result(self):
        """Test adding step results to shared memory"""
        context = SharedMemoryContext()

        result = {"content": "test response", "success": True}
        context.add_step_result("step1", result, True)

        assert len(context.step_results) == 1
        assert context.step_results["step1"]["result"] == result
        assert context.step_results["step1"]["success"] == True
        assert len(context.execution_log) == 1

    def test_get_step_result(self):
        """Test retrieving step results from shared memory"""
        context = SharedMemoryContext()

        result = {"content": "test response"}
        context.add_step_result("step1", result)

        retrieved = context.get_step_result("step1")
        assert retrieved == result

        # Test non-existent step
        retrieved = context.get_step_result("nonexistent")
        assert retrieved is None

    def test_shared_variables(self):
        """Test shared variable management"""
        context = SharedMemoryContext()

        # Set variables
        context.set_shared_variable("key1", "value1")
        context.set_shared_variable("key2", {"nested": "data"})

        # Get variables
        assert context.get_shared_variable("key1") == "value1"
        assert context.get_shared_variable("key2") == {"nested": "data"}
        assert context.get_shared_variable("nonexistent") is None
        assert context.get_shared_variable("nonexistent", "default") == "default"

    def test_merge_into_memory(self):
        """Test merging messages into shared memory"""
        context = SharedMemoryContext()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        context.merge_into_memory(messages)

        # Check that messages were added to memory
        # (This would normally check the ChatMemoryBuffer contents)
        assert len(context.execution_log) == 0  # This shouldn't add to execution log


class TestMultiAgentCoordinator:
    """Test MultiAgentCoordinator functionality"""

    @pytest.fixture
    def mock_user_config(self):
        """Create a mock user configuration"""
        config = Mock()
        config.user_id = "test_user"
        config.get_user_setting = Mock(return_value="RAG")
        return config

    @pytest.fixture
    def coordinator(self, mock_user_config):
        """Create a coordinator instance"""
        return MultiAgentCoordinator(mock_user_config)

    def test_coordinator_initialization(self, coordinator, mock_user_config):
        """Test coordinator initialization"""
        assert coordinator.user_config == mock_user_config

    def test_execute_pipeline_invalid_config(self, coordinator):
        """Test pipeline execution with invalid configuration"""
        invalid_config = PipelineConfig(
            pipeline_name="",  # Invalid: empty name
            agent_steps=[]
        )

        # Test that invalid config fails validation
        assert not invalid_config.validate()

    @pytest.mark.asyncio
    @patch('super_starter_suite.shared.multi_agent_coordinator.WorkflowAdapterFactory.get_adapter')
    async def test_execute_sequential_pipeline(self, mock_get_adapter, coordinator):
        """Test sequential pipeline execution"""
        # Mock workflow adapter
        mock_workflow = Mock()
        mock_workflow.create_workflow.return_value.run = Mock(return_value=asyncio.Future())
        mock_workflow.create_workflow.return_value.run.return_value = "Test response"

        mock_get_adapter.return_value = mock_workflow

        # Create a simple pipeline configuration
        config = PipelineConfig(
            pipeline_name="test_pipeline",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag")
            ],
            transition_type=AgentTransition.SEQUENTIAL
        )

        # Execute pipeline
        with patch.object(coordinator, '_execute_agent_step') as mock_execute_step:
            mock_execute_step.return_value = {"content": "Step 1 result", "success": True}

            result = await coordinator.execute_pipeline(config, {"question": "Test query"})

            # Verify result structure
            assert result['status'] == 'success'
            assert result['pipeline_id'] is not None
            assert len(result['execution_results']) == 1
            assert result['execution_results'][0]['step_id'] == 'step1'

    @pytest.mark.asyncio
    @patch('super_starter_suite.shared.multi_agent_coordinator.WorkflowAdapterFactory.get_adapter')
    async def test_execute_parallel_pipeline(self, mock_get_adapter, coordinator):
        """Test parallel pipeline execution"""
        # Mock workflow adapter
        mock_workflow = Mock()
        mock_workflow.create_workflow.return_value.run = Mock(return_value=asyncio.Future())
        mock_workflow.create_workflow.return_value.run.return_value = "Test response"

        mock_get_adapter.return_value = mock_workflow

        # Create a parallel pipeline configuration
        config = PipelineConfig(
            pipeline_name="parallel_test",
            agent_steps=[
                AgentStep(agent_id="step1", workflow_name="agentic_rag"),
                AgentStep(agent_id="step2", workflow_name="code_generator")
            ],
            transition_type=AgentTransition.PARALLEL
        )

        # Execute pipeline
        with patch.object(coordinator, '_execute_agent_step') as mock_execute_step:
            mock_execute_step.side_effect = [
                {"content": "Step 1 result", "success": True},
                {"content": "Step 2 result", "success": True}
            ]

            result = await coordinator.execute_pipeline(config, {"question": "Test query"})

            # Verify result structure
            assert result['status'] == 'success'
            assert len(result['execution_results']) == 2

    def test_aggregate_results_last_step(self, coordinator):
        """Test result aggregation with last_step policy"""
        config = PipelineConfig(
            pipeline_name="test",
            agent_steps=[],
            output_aggregation="last_step"
        )

        execution_results = [
            {"step_id": "step1", "success": True, "result": {"content": "First result"}},
            {"step_id": "step2", "success": False, "result": {"content": "Failed result"}},
            {"step_id": "step3", "success": True, "result": {"content": "Last result"}}
        ]

        shared_context = SharedMemoryContext()

        result = coordinator._aggregate_results(config, execution_results, shared_context)
        assert result == {"content": "Last result"}

    def test_aggregate_results_all_steps(self, coordinator):
        """Test result aggregation with all_steps policy"""
        config = PipelineConfig(
            pipeline_name="test",
            agent_steps=[],
            output_aggregation="all_steps"
        )

        execution_results = [
            {"step_id": "step1", "success": True, "result": "Result 1"},
            {"step_id": "step2", "success": True, "result": "Result 2"}
        ]

        shared_context = SharedMemoryContext()
        shared_context.set_shared_variable("var1", "value1")

        result = coordinator._aggregate_results(config, execution_results, shared_context)

        assert "all_results" in result
        assert "shared_variables" in result
        assert result["all_results"] == execution_results
        assert result["shared_variables"]["var1"] == "value1"

    def test_aggregate_parallel_results(self, coordinator):
        """Test parallel result aggregation"""
        config = PipelineConfig(
            pipeline_name="test",
            agent_steps=[],
            output_aggregation="all_steps",
            transition_type=AgentTransition.PARALLEL
        )

        execution_results = [
            {"step_id": "step1", "success": True, "result": "Result 1"},
            {"step_id": "step2", "success": False, "result": "Result 2"}
        ]

        shared_context = SharedMemoryContext()

        result = coordinator._aggregate_parallel_results(config, execution_results, shared_context)

        assert "parallel_results" in result
        assert "successful_results" in result
        assert len(result["successful_results"]) == 1


class TestWorkflowAdapterFactory:
    """Test WorkflowAdapterFactory functionality"""

    @patch('importlib.import_module')
    def test_get_adapter_success(self, mock_import):
        """Test successful adapter retrieval"""
        # Mock the module with a create_workflow function
        mock_module = Mock()
        mock_module.create_workflow.return_value = Mock()
        mock_import.return_value = mock_module

        result = WorkflowAdapterFactory.get_adapter("agentic_rag")

        assert result == mock_module
        mock_import.assert_called_once_with('super_starter_suite.STARTER_TOOLS.agentic_rag.app.workflow')

    @patch('importlib.import_module')
    def test_get_adapter_unknown_workflow(self, mock_import):
        """Test retrieval of unknown workflow"""
        result = WorkflowAdapterFactory.get_adapter("unknown_workflow")

        assert result is None
        mock_import.assert_not_called()

    @patch('importlib.import_module')
    def test_get_adapter_import_failure(self, mock_import):
        """Test adapter retrieval with import failure"""
        mock_import.side_effect = ImportError("Module not found")

        result = WorkflowAdapterFactory.get_adapter("agentic_rag")

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
