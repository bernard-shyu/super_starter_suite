"""
Multi-Agent Orchestration Framework

This module implements the MultiAgentCoordinator for Phase 5.4, enabling
coordinated multi-agent workflows where agents can share memory and work in pipelines.

Provides:
- MultiAgentCoordinator: Orchestrates multiple agents in sequences/pipelines
- SharedMemoryContext: Cross-agent memory and context sharing
- AgentPipeline: Chain of agents that pass results and context
- PipelineConfig: Configuration for multi-agent pipelines
"""

from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge
from super_starter_suite.shared.dto import MessageRole, create_chat_message, ChatSession
from llama_index.core.memory import ChatMemoryBuffer

# UNIFIED LOGGING SYSTEM
logger = config_manager.get_logger("workflow.multi_agent")

class PipelineResult(Enum):
    """Result status of pipeline execution"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


class AgentTransition(Enum):
    """How to transition between agents in a pipeline"""
    SEQUENTIAL = "sequential"  # Agent N+1 receives output from Agent N
    PARALLEL = "parallel"      # All agents run simultaneously
    CONDITIONAL = "conditional" # Agent N+1 runs based on Agent N result


@dataclass
class AgentStep:
    """
    Configuration for a single agent step in the pipeline
    """
    agent_id: str  # Unique identifier for this step
    workflow_name: str  # Which base workflow to use (e.g., 'agentic_rag', 'code_generator')
    input_transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    output_transform: Optional[Callable[[Any], Dict[str, Any]]] = None
    timeout_seconds: float = 300.0  # 5 minute default timeout
    retry_count: int = 0
    conditional_next: Optional[str] = None  # ID of next step for conditional transition


@dataclass
class SharedMemoryContext:
    """
    Shared memory and context across multiple agents in a pipeline

    Provides:
    - Unified chat memory across all agents
    - Shared variables and context data
    - Agent-to-agent message passing
    - Pipeline execution state
    """
    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_memory: ChatMemoryBuffer = field(default_factory=lambda: WorkflowSessionBridge.initialize_memory_buffer())
    shared_variables: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now())
    last_updated: datetime = field(default_factory=lambda: datetime.now())

    def add_step_result(self, step_id: str, result: Any, success: bool = True):
        """Add result of a pipeline step"""
        self.step_results[step_id] = {
            'result': result,
            'success': success,
            'timestamp': datetime.now()
        }
        self.last_updated = datetime.now()

        # Log execution
        self.execution_log.append({
            'step_id': step_id,
            'success': success,
            'timestamp': datetime.now(),
            'result_type': type(result).__name__
        })

    def get_step_result(self, step_id: str) -> Optional[Any]:
        """Get result of a completed step"""
        return self.step_results.get(step_id, {}).get('result')

    def set_shared_variable(self, key: str, value: Any):
        """Set a shared variable accessible by all agents"""
        self.shared_variables[key] = value
        self.last_updated = datetime.now()

    def get_shared_variable(self, key: str, default: Any = None) -> Any:
        """Get a shared variable value"""
        return self.shared_variables.get(key, default)

    def merge_into_memory(self, messages: List[Dict[str, Any]]):
        """Merge messages into shared session memory"""
        # Convert message dicts into proper chat messages and add to memory
        from llama_index.core.llms import ChatMessage, MessageRole as LlamaMessageRole

        for msg_dict in messages:
            if isinstance(msg_dict, dict) and 'role' in msg_dict and 'content' in msg_dict:
                try:
                    # Convert our string role to LlamaIndex's MessageRole
                    role_str = msg_dict['role']
                    if role_str == 'user':
                        llama_role = LlamaMessageRole.USER
                    elif role_str == 'assistant':
                        llama_role = LlamaMessageRole.ASSISTANT
                    elif role_str == 'system':
                        llama_role = LlamaMessageRole.SYSTEM
                    else:
                        raise ValueError(f"Unknown role: {role_str}")

                    # Create ChatMessage for LlamaIndex
                    chat_message = ChatMessage(role=llama_role, content=msg_dict['content'])
                    # Add to chat memory buffer
                    self.session_memory.put(chat_message)
                except ValueError:
                    logger.warning(f"Invalid message format in merge_into_memory: {msg_dict}")
        self.last_updated = datetime.now()


@dataclass
class PipelineConfig:
    """
    Configuration for a multi-agent pipeline
    """
    pipeline_name: str
    agent_steps: List[AgentStep]
    transition_type: AgentTransition = AgentTransition.SEQUENTIAL
    max_execution_time: float = 900.0  # 15 minutes default
    failure_policy: str = "fail_fast"  # 'fail_fast', 'continue', 'retry'
    output_aggregation: str = "last_step"  # 'last_step', 'all_steps', 'custom'

    def validate(self) -> bool:
        """Validate pipeline configuration"""
        if not self.pipeline_name or not self.agent_steps:
            return False

        # Check that all step IDs are unique
        step_ids = [step.agent_id for step in self.agent_steps]
        if len(step_ids) != len(set(step_ids)):
            return False

        # Check conditional references
        for step in self.agent_steps:
            if step.conditional_next and step.conditional_next not in step_ids:
                return False

        return True


class MultiAgentCoordinator:
    """
    Orchestrates multi-agent workflows with shared memory and coordinated execution

    Features:
    - Pipeline orchestration of multiple agents
    - Shared memory context across agents
    - Result passing and transformation between agents
    - Error handling and coordination
    - Timeout and retry management
    """
    def __init__(self, user_config: Any):
        self.user_config = user_config

    async def execute_pipeline(self, pipeline_config: PipelineConfig,
                              initial_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a multi-agent pipeline

        Args:
            pipeline_config: Configuration for the pipeline
            initial_input: Initial input data for the first agent

        Returns:
            dict: Pipeline execution results including final output and execution log
        """
        if not pipeline_config.validate():
            raise ValueError("Invalid pipeline configuration")

        # Initialize shared memory context
        shared_context = SharedMemoryContext()
        shared_context.set_shared_variable('initial_input', initial_input)
        shared_context.set_shared_variable('pipeline_config', pipeline_config)

        logger.info(f"Starting pipeline execution: {pipeline_config.pipeline_name}")

        # Execute based on transition type
        if pipeline_config.transition_type == AgentTransition.SEQUENTIAL:
            return await self._execute_sequential_pipeline(pipeline_config, shared_context)
        elif pipeline_config.transition_type == AgentTransition.PARALLEL:
            return await self._execute_parallel_pipeline(pipeline_config, shared_context)
        elif pipeline_config.transition_type == AgentTransition.CONDITIONAL:
            return await self._execute_conditional_pipeline(pipeline_config, shared_context)
        else:
            raise ValueError(f"Unsupported transition type: {pipeline_config.transition_type}")

    async def _execute_sequential_pipeline(self, pipeline_config: PipelineConfig,
                                         shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Execute agents sequentially, passing results along the chain"""
        current_input = shared_context.get_shared_variable('initial_input')
        execution_results = []

        for step in pipeline_config.agent_steps:
            try:
                # Apply input transformation if specified
                if step.input_transform:
                    current_input = step.input_transform(current_input)

                # Execute the step
                step_result = await self._execute_agent_step(step, current_input, shared_context)

                # Apply output transformation if specified
                if step.output_transform:
                    step_result = step.output_transform(step_result)

                # Add to execution results
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': True,
                    'result': step_result,
                    'timestamp': datetime.now()
                })

                # Prepare input for next step
                current_input = step_result

                # Handle failure policy
                if not step_result.get('success', True):
                    if pipeline_config.failure_policy == "fail_fast":
                        return self._create_failure_result(pipeline_config, shared_context, execution_results, "Step failed")
                    elif pipeline_config.failure_policy == "continue":
                        continue  # Continue to next step
                    # retry logic would go here

            except Exception as e:
                logger.error(f"Step {step.agent_id} failed: {e}")
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now()
                })

                if pipeline_config.failure_policy == "fail_fast":
                    return self._create_failure_result(pipeline_config, shared_context, execution_results, str(e))

        # Aggregate final results
        final_result = self._aggregate_results(pipeline_config, execution_results, shared_context)

        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.SUCCESS.value,
            'execution_results': execution_results,
            'final_result': final_result,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }

    async def _execute_parallel_pipeline(self, pipeline_config: PipelineConfig,
                                       shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Execute all agents in parallel"""
        initial_input = shared_context.get_shared_variable('initial_input')

        # Execute all steps concurrently
        tasks = []
        for step in pipeline_config.agent_steps:
            # Prepare input for each step (could be modified later to allow per-step inputs)
            step_input = initial_input.copy()
            task = self._execute_agent_step(step, step_input, shared_context)
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        execution_results = []
        for i, result in enumerate(results):
            step = pipeline_config.agent_steps[i]
            if isinstance(result, Exception):
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': False,
                    'error': str(result),
                    'timestamp': datetime.now()
                })
            else:
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': True,
                    'result': result,
                    'timestamp': datetime.now()
                })

        # Aggregate results for parallel execution
        final_result = self._aggregate_parallel_results(pipeline_config, execution_results, shared_context)

        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.SUCCESS.value,
            'execution_results': execution_results,
            'final_result': final_result,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }

    async def _execute_conditional_pipeline(self, pipeline_config: PipelineConfig,
                                          shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Execute agents based on conditional logic"""
        # This is a simplified implementation - could be extended with more complex logic
        current_step = pipeline_config.agent_steps[0] if pipeline_config.agent_steps else None
        current_input = shared_context.get_shared_variable('initial_input')
        execution_results = []

        while current_step:
            try:
                step_result = await self._execute_agent_step(current_step, current_input, shared_context)

                execution_results.append({
                    'step_id': current_step.agent_id,
                    'success': True,
                    'result': step_result,
                    'timestamp': datetime.now()
                })

                # Determine next step based on result
                next_step_id = self._evaluate_condition(current_step, step_result)

                if next_step_id:
                    # Find the next step by ID
                    next_step = None
                    for step in pipeline_config.agent_steps:
                        if step.agent_id == next_step_id:
                            next_step = step
                            break

                    if next_step:
                        current_step = next_step
                        current_input = step_result  # Pass result to next step
                        continue

                # No more steps or condition not met
                break

            except Exception as e:
                logger.error(f"Conditional step {current_step.agent_id} failed: {e}")
                execution_results.append({
                    'step_id': current_step.agent_id,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now()
                })
                break

        final_result = self._aggregate_results(pipeline_config, execution_results, shared_context)

        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.SUCCESS.value,
            'execution_results': execution_results,
            'final_result': final_result,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }

    async def _execute_agent_step(self, step: AgentStep, step_input: Dict[str, Any],
                                shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Execute a single agent step"""
        logger.info(f"Executing step {step.agent_id} with workflow {step.workflow_name}")

        # Create a session for this step
        session_data = WorkflowSessionBridge.ensure_chat_session(
            step.workflow_name, self.user_config
        )

        try:
            # Get the workflow adapter
            workflow_module = WorkflowAdapterFactory.get_adapter(step.workflow_name)
            if not workflow_module:
                raise ValueError(f"No adapter found for workflow: {step.workflow_name}")

            # Prepare the chat request with shared context
            from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
            from llama_index.core.llms.types import MessageRole as LlamaMessageRole

            # Add shared memory context to the input
            enriched_input = step_input.copy()
            enriched_input['shared_context'] = {
                'pipeline_id': shared_context.pipeline_id,
                'shared_variables': shared_context.shared_variables.copy(),
                'previous_results': {k: v for k, v in shared_context.step_results.items()}
            }

            # Format input as expected by workflow
            user_message = enriched_input.get('question', str(enriched_input))

            chat_request = ChatRequest(
                id=self.user_config.user_id,
                messages=[ChatAPIMessage(role=LlamaMessageRole.USER, content=user_message)]
            )

            # Create workflow and execute
            workflow = workflow_module.create_workflow(chat_request=chat_request)
            parameters = self._create_workflow_parameters(workflow_module, user_message, session_data['memory'])

            # Execute with timeout - FLAW #1 fix: direct parameters, not start_event
            result = await asyncio.wait_for(
                workflow.run(**parameters),
                timeout=step.timeout_seconds
            )

            # Format result
            response_content = str(result) if result else "No response generated"

            # Save to session
            WorkflowSessionBridge.add_message_and_save_response(
                step.workflow_name, self.user_config,
                session_data['session'], user_message, response_content
            )

            # Store result in shared context
            step_result = {
                'success': True,
                'content': response_content,
                'session_id': session_data['session'].session_id,
                'workflow': step.workflow_name,
                'shared_context_used': enriched_input['shared_context']
            }

            shared_context.add_step_result(step.agent_id, step_result, True)

            # Merge any new messages into shared memory
            shared_context.merge_into_memory([
                {'role': 'user', 'content': user_message},
                {'role': 'assistant', 'content': response_content}
            ])

            return step_result

        except asyncio.TimeoutError:
            error_msg = f"Step {step.agent_id} timed out after {step.timeout_seconds} seconds"
            logger.error(error_msg)
            step_result = {'success': False, 'error': error_msg, 'timeout': True}
            shared_context.add_step_result(step.agent_id, step_result, False)
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Step {step.agent_id} failed: {str(e)}"
            logger.error(error_msg)
            step_result = {'success': False, 'error': error_msg}
            shared_context.add_step_result(step.agent_id, step_result, False)
            raise

    def _create_workflow_parameters(self, workflow_module, user_message: str, memory: Optional[ChatMemoryBuffer]):
        """Create parameters for workflow.run() call - FLAW #1 fix: direct parameters instead of StartEvent"""
        return {
            'user_msg': user_message,
            'chat_history': None,
            'memory': memory,
            'max_iterations': None
        }

    def _evaluate_condition(self, current_step: AgentStep, step_result: Dict[str, Any]) -> Optional[str]:
        """Evaluate conditional logic for next step selection"""
        # Simple condition evaluation - can be extended with more complex logic
        if current_step.conditional_next:
            # Check if step was successful
            if step_result.get('success', False):
                return current_step.conditional_next
        return None

    def _aggregate_results(self, pipeline_config: PipelineConfig, execution_results: List[Dict],
                          shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Aggregate results from execution based on pipeline configuration"""
        if pipeline_config.output_aggregation == "last_step":
            # Return the result of the last successful step
            for result in reversed(execution_results):
                if result.get('success', False):
                    return result.get('result', {})
            return {}
        elif pipeline_config.output_aggregation == "all_steps":
            # Return all results
            return {
                'all_results': execution_results,
                'shared_variables': shared_context.shared_variables
            }
        else:  # custom or default
            # Return results in a structured format
            return {
                'execution_results': execution_results,
                'shared_context': shared_context.shared_variables
            }

    def _aggregate_parallel_results(self, pipeline_config: PipelineConfig, execution_results: List[Dict],
                                   shared_context: SharedMemoryContext) -> Dict[str, Any]:
        """Aggregate results from parallel execution"""
        successful_results = [r for r in execution_results if r.get('success', False)]

        if pipeline_config.output_aggregation == "all_steps":
            return {
                'parallel_results': execution_results,
                'successful_results': successful_results,
                'shared_variables': shared_context.shared_variables
            }
        else:
            # For parallel execution, default to successful results
            return {
                'successful_agents': len(successful_results),
                'total_agents': len(execution_results),
                'results': successful_results
            }

    def _create_failure_result(self, pipeline_config: PipelineConfig, shared_context: SharedMemoryContext,
                              execution_results: List[Dict], error_msg: str) -> Dict[str, Any]:
        """Create a failure result structure"""
        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.FAILURE.value,
            'error': error_msg,
            'partial_results': execution_results,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }


class WorkflowAdapterFactory:
    """Factory for creating workflow adapters"""

    @staticmethod
    def get_adapter(workflow_name: str) -> Optional[Any]:
        """Get workflow adapter module by name"""
        # Import the appropriate workflow from STARTER_TOOLS
        workflow_map = {
            'agentic_rag': 'super_starter_suite.STARTER_TOOLS.agentic_rag.app.workflow',
            'code_generator': 'super_starter_suite.STARTER_TOOLS.code_generator.workflow',
            'deep_research': 'super_starter_suite.STARTER_TOOLS.deep_research.workflow',
            'document_generator': 'super_starter_suite.STARTER_TOOLS.document_generator.workflow',
            'financial_report': 'super_starter_suite.STARTER_TOOLS.financial_report.workflow',
            'human_in_the_loop': 'super_starter_suite.STARTER_TOOLS.human_in_the_loop.workflow'
        }

        if workflow_name not in workflow_map:
            logger.error(f"Unknown workflow: {workflow_name}")
            return None

        try:
            import importlib
            module_path = workflow_map[workflow_name]
            module = importlib.import_module(module_path)
            return module
        except Exception as e:
            logger.error(f"Failed to load workflow {workflow_name}: {e}")
            return None
