"""
Multi-Agent Orchestration Shared Logic

This module provides the core components for building multi-agent workflows.
Shared logic extracted from legacy multi_agent.py.
"""

from typing import Dict, Any, List, Optional, Union, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import uuid

from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.dto import MessageRole, ChatMessageDTO
from super_starter_suite.shared.workflow_loader import get_workflow_factory_function
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Event, StartEvent, StopEvent, Workflow, step, Context
from llama_index.server.api.models import ChatAPIMessage, ChatRequest
from llama_index.core.llms import ChatMessage, MessageRole as LlamaMessageRole

# UNIFIED LOGGING SYSTEM
logger = config_manager.get_logger("workflow.meta")

class PipelineResult(Enum):
    """Result status of pipeline execution"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


class AgentTransition(Enum):
    """How to transition between agents in a pipeline"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class AgentStep:
    """Configuration for a single agent step in the pipeline"""
    agent_id: str
    workflow_name: str
    input_transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    output_transform: Optional[Callable[[Any], Dict[str, Any]]] = None
    timeout_seconds: float = 300.0
    retry_count: int = 0
    conditional_next: Optional[str] = None


@dataclass
class SharedMemoryContext:
    """Shared memory and context across multiple agents in a pipeline"""
    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_memory: ChatMemoryBuffer = field(default_factory=lambda: ChatMemoryBuffer.from_defaults())
    shared_variables: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def add_step_result(self, step_id: str, result: Any, success: bool = True):
        self.step_results[step_id] = {
            'result': result,
            'success': success,
            'timestamp': datetime.now()
        }
        self.last_updated = datetime.now()
        self.execution_log.append({
            'step_id': step_id,
            'success': success,
            'timestamp': datetime.now(),
            'result_type': type(result).__name__
        })

    def get_step_result(self, step_id: str) -> Optional[Any]:
        return self.step_results.get(step_id, {}).get('result')

    def set_shared_variable(self, key: str, value: Any):
        self.shared_variables[key] = value
        self.last_updated = datetime.now()

    def get_shared_variable(self, key: str, default: Any = None) -> Any:
        return self.shared_variables.get(key, default)

    def merge_into_memory(self, messages: List[Dict[str, Any]]):
        for msg_dict in messages:
            if isinstance(msg_dict, dict) and 'role' in msg_dict and 'content' in msg_dict:
                try:
                    role_str = msg_dict['role']
                    if role_str == 'user':
                        llama_role = LlamaMessageRole.USER
                    elif role_str == 'assistant':
                        llama_role = LlamaMessageRole.ASSISTANT
                    elif role_str == 'system':
                        llama_role = LlamaMessageRole.SYSTEM
                    else:
                        continue

                    chat_message = ChatMessage(role=llama_role, content=msg_dict['content'])
                    self.session_memory.put(chat_message)
                    logger.debug(f"[MEMORY] Merged {role_str} message into pipeline memory")
                except Exception as e:
                    logger.warning(f"Invalid message format in merge_into_memory: {e}")
        self.last_updated = datetime.now()


@dataclass
class PipelineConfig:
    """Configuration for a multi-agent pipeline"""
    pipeline_name: str
    agent_steps: List[AgentStep]
    transition_type: AgentTransition = AgentTransition.SEQUENTIAL
    max_execution_time: float = 900.0
    failure_policy: str = "fail_fast"
    output_aggregation: str = "last_step"

    def validate(self) -> bool:
        if not self.pipeline_name or not self.agent_steps:
            return False
        step_ids = [step.agent_id for step in self.agent_steps]
        if len(step_ids) != len(set(step_ids)):
            return False
        for step in self.agent_steps:
            if step.conditional_next and step.conditional_next not in step_ids:
                return False
        return True


class MultiAgentCoordinator:
    """Orchestrates multi-agent workflows"""
    def __init__(self, user_config: Any = None):
        self.user_config = user_config

    async def execute_pipeline(self, ctx: Context, pipeline_config: PipelineConfig,
                               initial_input: Dict[str, Any]) -> Dict[str, Any]:
        if not pipeline_config.validate():
            raise ValueError("Invalid pipeline configuration")

        shared_context = SharedMemoryContext()
        shared_context.set_shared_variable('initial_input', initial_input)
        shared_context.set_shared_variable('pipeline_config', pipeline_config)

        logger.info(f"[PIPELINE] START: {pipeline_config.pipeline_name}")

        if pipeline_config.transition_type == AgentTransition.SEQUENTIAL:
            return await self._execute_sequential_pipeline(ctx, pipeline_config, shared_context)
        elif pipeline_config.transition_type == AgentTransition.PARALLEL:
            return await self._execute_parallel_pipeline(ctx, pipeline_config, shared_context)
        elif pipeline_config.transition_type == AgentTransition.CONDITIONAL:
            return await self._execute_conditional_pipeline(ctx, pipeline_config, shared_context)
        else:
            raise ValueError(f"Unsupported transition type: {pipeline_config.transition_type}")

    async def _execute_sequential_pipeline(self, ctx: Context, pipeline_config: PipelineConfig,
                                         shared_context: SharedMemoryContext) -> Dict[str, Any]:
        current_input = shared_context.get_shared_variable('initial_input')
        execution_results = []

        for step in pipeline_config.agent_steps:
            try:
                if step.input_transform:
                    logger.debug(f"[PIPELINE] Transforming input for step {step.agent_id}")
                    current_input = step.input_transform(current_input)

                step_result = await self._execute_agent_step(ctx, step, current_input, shared_context)

                if step.output_transform:
                    logger.debug(f"[PIPELINE] Transforming output for step {step.agent_id}")
                    step_result = step.output_transform(step_result)

                execution_results.append({
                    'step_id': step.agent_id,
                    'success': True,
                    'result': step_result,
                    'workflow': step.workflow_name,
                    'timestamp': datetime.now()
                })

                current_input = step_result

                if not step_result.get('success', True):
                    if pipeline_config.failure_policy == "fail_fast":
                        return self._create_failure_result(pipeline_config, shared_context, execution_results, "Step failed")
                    elif pipeline_config.failure_policy == "continue":
                        continue

            except Exception as e:
                logger.error(f"Step {step.agent_id} failed: {e}")
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': False,
                    'error': str(e),
                    'workflow': step.workflow_name,
                    'timestamp': datetime.now()
                })

                if pipeline_config.failure_policy == "fail_fast":
                    return self._create_failure_result(pipeline_config, shared_context, execution_results, str(e))

        final_result = self._aggregate_results(pipeline_config, execution_results, shared_context)

        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.SUCCESS.value,
            'execution_results': execution_results,
            'final_result': final_result,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }

    async def _execute_parallel_pipeline(self, ctx: Context, pipeline_config: PipelineConfig,
                                       shared_context: SharedMemoryContext) -> Dict[str, Any]:
        initial_input = shared_context.get_shared_variable('initial_input')
        tasks = []
        for step in pipeline_config.agent_steps:
            step_input = initial_input.copy()
            task = self._execute_agent_step(ctx, step, step_input, shared_context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_results = []
        for i, result in enumerate(results):
            step = pipeline_config.agent_steps[i]
            if isinstance(result, Exception):
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': False,
                    'error': str(result),
                    'workflow': step.workflow_name,
                    'timestamp': datetime.now()
                })
            else:
                execution_results.append({
                    'step_id': step.agent_id,
                    'success': True,
                    'result': result,
                    'workflow': step.workflow_name,
                    'timestamp': datetime.now()
                })

        final_result = self._aggregate_parallel_results(pipeline_config, execution_results, shared_context)

        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.SUCCESS.value,
            'execution_results': execution_results,
            'final_result': final_result,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }

    async def _execute_conditional_pipeline(self, ctx: Context, pipeline_config: PipelineConfig,
                                          shared_context: SharedMemoryContext) -> Dict[str, Any]:
        current_step = pipeline_config.agent_steps[0] if pipeline_config.agent_steps else None
        current_input = shared_context.get_shared_variable('initial_input')
        execution_results = []

        while current_step:
            try:
                step_result = await self._execute_agent_step(ctx, current_step, current_input, shared_context)
                execution_results.append({
                    'step_id': current_step.agent_id,
                    'success': True,
                    'result': step_result,
                    'workflow': current_step.workflow_name,
                    'timestamp': datetime.now()
                })

                next_step_id = self._evaluate_condition(current_step, step_result)
                if next_step_id:
                    next_step = next((s for s in pipeline_config.agent_steps if s.agent_id == next_step_id), None)
                    if next_step:
                        current_step = next_step
                        current_input = step_result
                        continue
                break
            except Exception as e:
                logger.error(f"Conditional step {current_step.agent_id} failed: {e}")
                execution_results.append({
                    'step_id': current_step.agent_id,
                    'success': False,
                    'error': str(e),
                    'workflow': current_step.workflow_name,
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

    async def _execute_agent_step(self, ctx: Context, step: AgentStep, step_input: Dict[str, Any],
                                shared_context: SharedMemoryContext) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] STEP: id='{step.agent_id}' | {step.workflow_name}")
        memory = shared_context.session_memory

        try:
            workflow_factory = get_workflow_factory_function(step.workflow_name)
            if not workflow_factory:
                raise ValueError(f"No factory found for workflow: {step.workflow_name}")

            enriched_input = step_input.copy()
            enriched_input['shared_context'] = {
                'pipeline_id': shared_context.pipeline_id,
                'shared_variables': shared_context.shared_variables.copy(),
                'previous_results': {k: v for k, v in shared_context.step_results.items()}
            }

            user_message = enriched_input.get('query') or enriched_input.get('question') or str(enriched_input)
            user_id = 'unknown_user'
            if self.user_config:
                user_id = getattr(self.user_config, 'user_id', 'unknown_user')

            chat_request = ChatRequest(
                id=user_id,
                messages=[ChatAPIMessage(role=LlamaMessageRole.USER, content=user_message)]
            )

            logger.debug(f"[PIPELINE] Initializing sub-workflow: {step.workflow_name} for agent: {step.agent_id}")
            workflow = workflow_factory(chat_request=chat_request, timeout_seconds=step.timeout_seconds)
            parameters = self._create_workflow_parameters(user_message, memory)
            logger.debug(f"[PIPELINE] Running {step.workflow_name} with params: {list(parameters.keys())}")

            workflow_handler = workflow.run(**parameters)
            
            # Local collection for events that might not be in the final result dict
            streamed_artifacts = []
            streamed_citations = [] # Citations represent LlamaIndex source nodes

            async for ev in workflow_handler.stream_events():
                event_type = type(ev).__name__
                if isinstance(ev, (StartEvent, StopEvent)):
                    continue
                
                # Capture Artifacts and Citations (source nodes) from stream
                from llama_index.server.api.models import ArtifactEvent
                if isinstance(ev, ArtifactEvent):
                    from super_starter_suite.chat_bot.workflow_execution.artifact_utils import extract_artifact_metadata
                    try:
                        streamed_artifacts.append(extract_artifact_metadata(ev.data))
                    except Exception as e:
                        logger.warning(f"[PIPELINE] Failed to extract artifact from stream: {e}")
                elif event_type == "SourceNodesEvent":
                    nodes = getattr(ev, 'nodes', [])
                    streamed_citations.extend(nodes)
                    logger.debug(f"[PIPELINE] Collected {len(nodes)} citations (source nodes) from stream")

                ctx.send_event(ev)
            
            result = await asyncio.wait_for(
                workflow_handler, 
                timeout=step.timeout_seconds
            )

            from super_starter_suite.shared.workflow_utils import extract_workflow_response_content
            response_content = await extract_workflow_response_content(result, step.workflow_name, logger)

            # EXTRACT ARTIFACTS & CITATIONS: Merge streamed data with any found in result dict
            final_artifacts = streamed_artifacts
            final_citations = streamed_citations # Unified term for source nodes

            # ROBUST CHECK: Result might be an async_generator or other non-dict object
            if isinstance(result, dict):
                # Add artifacts from result dict if any
                res_artifacts = result.get('artifacts', [])
                for art in res_artifacts:
                    if art not in final_artifacts:
                        final_artifacts.append(art)
                
                # Add citations (source nodes) from result dict if any
                res_nodes = result.get('source_nodes', result.get('citations', []))
                final_citations.extend(res_nodes)
            
            if final_artifacts:
                logger.info(f"[PIPELINE] Total {len(final_artifacts)} artifacts for agent: {step.agent_id}")
            if final_citations:
                logger.debug(f"[PIPELINE] Total {len(final_citations)} citations (source nodes) for agent: {step.agent_id}")

            step_result = {
                'success': True,
                'content': response_content,
                'artifacts': final_artifacts,
                'citations': final_citations, # Unified term for source nodes
                'session_id': shared_context.pipeline_id,
                'workflow': step.workflow_name,
                'shared_context_used': enriched_input['shared_context']
            }

            shared_context.add_step_result(step.agent_id, step_result, True)
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
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Step {step.agent_id} failed: {str(e)}\nTraceback:\n{error_details}"
            logger.error(error_msg)
            step_result = {'success': False, 'error': str(e), 'traceback': error_details}
            shared_context.add_step_result(step.agent_id, step_result, False)
            raise


    def _create_workflow_parameters(self, user_message: str, memory: Optional[ChatMemoryBuffer]):
        chat_history = []
        if memory:
            chat_history = memory.get()
        return {
            'user_msg': user_message,
            'chat_history': chat_history,
            'max_iterations': 50
        }

    def _evaluate_condition(self, current_step: AgentStep, step_result: Dict[str, Any]) -> Optional[str]:
        if current_step.conditional_next:
            if step_result.get('success', False):
                return current_step.conditional_next
        return None

    def _aggregate_results(self, pipeline_config: PipelineConfig, execution_results: List[Dict],
                          shared_context: SharedMemoryContext) -> Dict[str, Any]:
        # Collect all artifacts and citations (source nodes) from successful steps
        all_artifacts = []
        all_citations = []
        for res in execution_results:
            if res.get('success'):
                step_res = res.get('result', {})
                all_artifacts.extend(step_res.get('artifacts', []))
                all_citations.extend(step_res.get('citations', []))
        
        if pipeline_config.output_aggregation == "last_step":
            final_res = {}
            for result in reversed(execution_results):
                if result.get('success', False):
                    final_res = result.get('result', {}).copy()
                    break
            
            # Ensure all artifacts and citations are included
            final_res['artifacts'] = all_artifacts
            final_res['citations'] = all_citations
            return final_res
            
        elif pipeline_config.output_aggregation == "all_steps":
            return {
                'all_results': execution_results,
                'artifacts': all_artifacts,
                'citations': all_citations,
                'shared_variables': shared_context.shared_variables
            }
        else:
            return {
                'execution_results': execution_results,
                'artifacts': all_artifacts,
                'citations': all_citations,
                'shared_context': shared_context.shared_variables
            }

    def _aggregate_parallel_results(self, pipeline_config: PipelineConfig, execution_results: List[Dict],
                                   shared_context: SharedMemoryContext) -> Dict[str, Any]:
        successful_results = [r for r in execution_results if r.get('success', False)]
        all_artifacts = []
        all_citations = []
        for res in successful_results:
            step_res = res.get('result', {})
            all_artifacts.extend(step_res.get('artifacts', []))
            all_citations.extend(step_res.get('citations', []))

        if pipeline_config.output_aggregation == "all_steps":
            return {
                'parallel_results': execution_results,
                'successful_results': successful_results,
                'artifacts': all_artifacts,
                'citations': all_citations,
                'shared_variables': shared_context.shared_variables
            }
        else:
            return {
                'successful_agents': len(successful_results),
                'total_agents': len(execution_results),
                'results': successful_results,
                'artifacts': all_artifacts,
                'citations': all_citations
            }

    def _create_failure_result(self, pipeline_config: PipelineConfig, shared_context: SharedMemoryContext,
                               execution_results: List[Dict], error_msg: str) -> Dict[str, Any]:
        return {
            'pipeline_id': shared_context.pipeline_id,
            'status': PipelineResult.FAILURE.value,
            'error': error_msg,
            'partial_results': execution_results,
            'execution_log': shared_context.execution_log,
            'shared_variables': shared_context.shared_variables
        }


class BaseMultiAgentWorkflow(Workflow):
    """Base class for multi-agent workflows"""
    def __init__(self, chat_request: ChatRequest, user_config: Any = None, timeout: float = 300.0, **kwargs):
        super().__init__(timeout=timeout, **kwargs)
        self.chat_request = chat_request
        self.user_config = user_config
        self.coordinator = MultiAgentCoordinator(user_config=user_config)

    def get_query(self, ev: StartEvent) -> str:
        query = ev.get("query") or ""
        if not query and self.chat_request and self.chat_request.messages:
            query = self.chat_request.messages[-1].content
        return query

    def format_stop_event(self, pipeline_config: PipelineConfig, result: Dict[str, Any]) -> StopEvent:
        pipeline_info = {
            "pipeline_name": pipeline_config.pipeline_name,
            "status": result.get('status'),
            "step_count": len(result.get('execution_results', [])),
            "steps": []
        }
        
        for r in result.get('execution_results', []):
            pipeline_info["steps"].append({
                "agent_id": r.get('agent_id'),
                "workflow": r.get('workflow'),
                "success": r.get('success')
            })

        if result.get('status') == PipelineResult.SUCCESS.value:
            final_data = result.get('final_result', {})
            # Extract response: prefer content from final_data, fallback to last step result if missing
            response_text = final_data.get('content', "")
            if not response_text:
                outputs = result.get('execution_results', [])
                if outputs:
                    # Check if the result is a dict or string
                    last_res = outputs[-1].get('result', {})
                    if isinstance(last_res, dict):
                        response_text = last_res.get('content', "")
                    elif isinstance(last_res, str):
                        response_text = last_res
            
            if not response_text:
                response_text = "Pipeline executed but produced no output content."
            
            # Extract aggregated artifacts and citations from final_data (which came from aggregation logic)
            artifacts = final_data.get('artifacts', [])
            citations = final_data.get('citations', [])
        else:
            response_text = f"❌ Pipeline failed: {result.get('error', 'Unknown error')}"
            artifacts = []
            citations = []

        return StopEvent(result={
            "response": response_text,
            "artifacts": artifacts,
            "citations": citations, # Citations correspond to source nodes
            "pipeline_info": pipeline_info
        })
