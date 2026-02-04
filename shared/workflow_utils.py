# super_starter_suite/shared/workflow_utils.py

"""
Minimal shared utilities for workflow operations.

Contains basic validation, error handling, logging, and content processing functions
that are shared across different workflow components.
"""

import time
import re
import uuid
from typing import Callable, Any, Dict, Type, Tuple, List, Optional
from .config_manager import config_manager
from .dto import WorkflowConfig, StructuredMessage, MessageMetadata

# UNIFIED LOGGING SYSTEM - Replace global logging
workflow_logger = config_manager.get_logger("workflow.utils")


def validate_workflow_payload(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the workflow payload.

    Args:
        payload: The request payload containing user input.

    Returns:
        A tuple containing a boolean indicating if the payload is valid and an error message if not.
    """
    if "question" not in payload:
        return False, "Request must contain a 'question' field"
    if not payload["question"].strip():
        return False, "Question field cannot be empty"
    return True, ""


def create_error_response(error_message: str, workflow_name: str, status_code: int = 500) -> Tuple[str, int]:
    """
    Create an error response HTML content.

    Args:
        error_message: The error message to display.
        workflow_name: The name of the workflow that encountered the error.
        status_code: The HTTP status code to return.

    Returns:
        A tuple containing the error HTML content and the status code.
    """
    error_html = f"""
    <html>
    <head><title>Error</title></head>
    <body>
    <h1>Error in {workflow_name} Workflow</h1>
    <p>{error_message}</p>
    </body>
    </html>
    """
    return error_html, status_code


def log_workflow_execution(workflow_name: str, question: str, success: bool, duration: float):
    """
    Log the execution of a workflow.

    Args:
        workflow_name: The name of the workflow that was executed.
        question: The user question that was processed.
        success: A boolean indicating if the execution was successful.
        duration: The duration of the execution in seconds.
    """
    log_message = f"{workflow_name} workflow executed {'successfully' if success else 'unsuccessfully'}"
    workflow_logger.info(f"{log_message} in {duration:.2f} seconds for question: {question[:100]}...")


def create_structured_message(final_result: Any, response_content: str, workflow_name: str, model_provider: str = "", model_id: str = "") -> 'StructuredMessage':
    """
    SIMPLIFIED CITATION EXTRACTION: Preserve citation markers for frontend processing
    Pass 1: Extract all citations without content modification
    Pass 2: Clean content and transform grouped citations to individual markers

    Args:
        final_result: LlamaIndex workflow result (may contain raw metadata)
        response_content: Raw text from workflow (may contain citation markers)
        workflow_name: Context for rendering
        model_provider: Model provider for metadata
        model_id: Model ID for metadata

    Returns:
        StructuredMessage: Clean structured message with preserved citation markers
    """
    from .dto import MessageMetadata, StructuredMessage

    # Enhanced defensive validation
    try:
        if response_content is None:
            response_content = ""
        elif not isinstance(response_content, str):
            response_content = str(response_content)
    except Exception as e:
        workflow_logger.warning(f"[{workflow_name}] Failed to normalize response_content: {e}")
        response_content = ""

    # ===== PASS 1: CITATION EXTRACTION (from OLD architecture) =====
    citations = []
    citation_metadata = {}  # Store metadata for each citation UUID
    tool_calls = []
    followup_questions = []

    # FIRST: Extract citation metadata from workflow result if available
    try:
        # Try final_result.citations first
        if hasattr(final_result, 'citations') and final_result.citations:
            for citation_item in final_result.citations:
                if hasattr(citation_item, 'id') or hasattr(citation_item, 'uuid'):
                    citation_id = getattr(citation_item, 'id', getattr(citation_item, 'uuid', None))
                    if citation_id:
                        citation_metadata[citation_id] = {
                            'file_name': getattr(citation_item, 'file_name', getattr(citation_item, 'filename', 'Unknown')),
                            'page': getattr(citation_item, 'page', None),
                            'size': getattr(citation_item, 'size', None),
                            'content_preview': getattr(citation_item, 'content', getattr(citation_item, 'text', getattr(citation_item, 'content_preview', ''))),
                        }

        # Try tool_calls for citation metadata (llama_index stores it here)
        elif hasattr(final_result, 'tool_calls') and final_result.tool_calls:
            for tool_call in final_result.tool_calls:
                # Check if tool_call has citation data
                if hasattr(tool_call, 'tool_output') and tool_call.tool_output:
                    tool_output = tool_call.tool_output

                    # Try to extract citation info from tool output
                    # Check raw_output.source_nodes (where llama_index actually stores citation metadata)
                    if hasattr(tool_output, 'raw_output') and hasattr(tool_output.raw_output, 'source_nodes') and tool_output.raw_output.source_nodes:
                        for source_node in tool_output.raw_output.source_nodes:
                            # source_node is a NodeWithScore, get the actual node
                            node = getattr(source_node, 'node', source_node)
                            if hasattr(node, 'id') or hasattr(node, 'node_id'):
                                citation_id = getattr(node, 'id', getattr(node, 'node_id', None))
                                if citation_id:
                                    node_metadata = getattr(node, 'metadata', {})
                                    citation_metadata[citation_id] = {
                                        'file_name': node_metadata.get('file_name', node_metadata.get('filename', 'Unknown')),
                                        'page_num': node_metadata.get('page_num', None),
                                        'size': node_metadata.get('file_size', node_metadata.get('size', None)),
                                        'content_preview': getattr(node, 'content', getattr(node, 'text', ''))[:200] + '...' if getattr(node, 'content', getattr(node, 'text', '')) else '',
                                    }


    except Exception as e:
        workflow_logger.warning(f"[{workflow_name}] Failed to extract citation metadata from workflow result: {e}")
        import traceback
        workflow_logger.warning(f"[{workflow_name}] Citation extraction traceback: {traceback.format_exc()}")

    try:
        lines = response_content.split('\n')
        # NEW: Enhanced defensive validation
        if not isinstance(lines, list):
            lines = [str(response_content)]
    except Exception as e:
        workflow_logger.warning(f"[{workflow_name}] Failed to split response_content: {e}")
        lines = [str(response_content)]

    for line in lines:
        stripped = line.strip()

        # Tool calls: Extract from Action patterns
        if action_match := re.search(r'Action:\s*(\w+)', stripped):
            tool_name = action_match.group(1).strip()
            if tool_name and tool_name not in tool_calls:
                tool_calls.append(tool_name)

        # Citations: Extract multiple formats (from OLD architecture)
        elif citation_match := re.search(r'\[citation:[^\]]+\]', stripped):
            citation = citation_match.group(0)
            citation_id = citation.replace('[citation:', '').replace(']', '')

            # FILTER OUT FAKE CITATIONS: Only accept real UUIDs
            try:
                uuid.UUID(citation_id)
                if citation not in citations:
                    citations.append(citation)
            except ValueError:
                pass  # Skip invalid UUIDs

        elif grouped_match := re.search(r'\[citations?:\s*([^]]+)\]', stripped, re.IGNORECASE):
            citations_text = grouped_match.group(1)
            # Handle both comma and semicolon separators (adapted vs ported workflows)
            uuid_candidates = re.split(r'[;,]', citations_text)
            uuid_candidates = [uuid.strip() for uuid in uuid_candidates]
            for candidate in uuid_candidates:
                candidate = candidate.strip()
                try:
                    uuid.UUID(candidate)
                    citation = f'[citation:{candidate}]'
                    if citation not in citations:
                        citations.append(citation)
                except ValueError:
                    pass  # Skip invalid UUIDs

        else:
            # Also check for [uuid] format (ported workflows)
            uuid_match = re.search(r'\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]', stripped)
            if uuid_match:
                citation_id = uuid_match.group(1)
                citation = f'[citation:{citation_id}]'
                if citation not in citations:
                    citations.append(citation)

    # ===== PASS 2: CONTENT CLEANING & CITATION TRANSFORMATION (from OLD architecture) =====
    clean_lines = []
    in_answer_section = False

    for line in lines:
        stripped = line.strip()

        # START: Detect when we enter answer section
        if (stripped.startswith(('Answer:', 'Final Answer:')) or
            any(indicator in stripped.lower() for indicator in ['based on', 'according to', 'the standards', 'letters should'])):
            in_answer_section = True
            # Clean the answer header if present
            if stripped.startswith(('Answer:', 'Final Answer:')):
                clean_line = stripped.replace('Answer:', '').replace('Final Answer:', '').strip()
                if clean_line:
                    clean_lines.append(clean_line)
                continue

        # Keep main content, remove AI artifacts stringently
        should_keep = False

        if in_answer_section:
            # CRITICAL: Transform grouped citations with enhanced error handling
            if grouped_match := re.search(r'\[citations?:\s*([^]]+)\]', stripped, re.IGNORECASE):
                citations_text = grouped_match.group(1)
                # Handle both comma and semicolon separators (adapted vs ported workflows)
                uuid_candidates = re.split(r'[;,]', citations_text)
                uuid_candidates = [uuid.strip() for uuid in uuid_candidates]
                individual_markers = []
                for candidate in uuid_candidates:
                    candidate = candidate.strip()
                    try:
                        uuid.UUID(candidate)
                        individual_markers.append(f'[citation:{candidate}]')
                    except ValueError:
                        pass  # Skip invalid UUIDs
                if individual_markers:
                    # Replace the grouped citation with individual markers
                    stripped = re.sub(r'\[citations?:\s*([^]]+)\]', ' '.join(individual_markers), stripped, flags=re.IGNORECASE)
            should_keep = bool(stripped)

        # Allow main content lines that are informative responses
        elif (stripped and
              not stripped.startswith(('Thought:', 'Action:', 'Observation:', 'Thinking:', 'Reasoning:')) and
              not re.search(r'Action Input:', stripped) and
              not any(keyword in stripped.lower() for keyword in [
                  'calling tool', 'tool_call', 'query_index',
                  'based on the tool results', 'the search returned',
                  'suggested follow-up questions', 'follow-up questions:'
              ]) and
              # Filter out procedural/chain-of-thought phrases
              not (stripped.endswith(':') and len(stripped) < 40) and
              # Keep lines with image markdown or substantial text
              (len(stripped) > 5 or '![' in stripped)):
            should_keep = True

        if should_keep:
            # Clean up the line itself - remove internal assistant role labels
            cleaned_line = re.sub(r'(?i)\b(assistant:\s*)+', '', line)
            clean_lines.append(cleaned_line)

    clean_content = '\n'.join(clean_lines).strip()
    # Remove excessive blank lines while preserving structure
    clean_content = re.sub(r'\n\n\n+', '\n\n', clean_content)

    # MERGED: Enhanced metadata field (citations field for frontend compatibility)
    metadata = MessageMetadata(
        citations=citations,              # MERGED: citations field (was sources in old, but citations needed for frontend)
        citation_metadata=citation_metadata,  # NEW: Citation metadata mapping UUIDs to file info
        tool_calls=tool_calls,        # Tool names: ["query_index"]
        followup_questions=followup_questions,  # Currently empty, holds future AI-generated questions
        model_provider=model_provider,
        model_id=model_id
    )

    return StructuredMessage(
        content=clean_content,        # Clean human-readable text with transformed citations
        metadata=metadata,           # Separate machine metadata
        workflow_name=workflow_name  # Context for rendering
    )

    workflow_logger.debug(f"✅ [{workflow_name}] Created StructuredMessage: {len(clean_content)} chars, {len(citations)} citations, {len(tool_calls)} tools")
    workflow_logger.debug(f"📚 [{workflow_name}] Citation metadata extracted: {citation_metadata}, {metadata.citation_metadata}")
    return structured_message


def basic_content_cleaning(content: str) -> str:
    """
    Basic content cleaning that preserves citation markers.

    Unlike the complex version, this only removes obvious AI artifacts
    while keeping all citation markers intact for frontend processing.
    """
    if not content:
        return content

    lines = content.split('\n')
    clean_lines = []
    in_answer_section = False

    for line in lines:
        stripped = line.strip()

        # START: Detect when we enter answer section - keep everything after this
        if (stripped.startswith(('Answer:', 'Final Answer:')) or
            any(indicator in stripped.lower() for indicator in ['based on', 'according to', 'the standards', 'letters should'])):
            in_answer_section = True
            # Clean the answer header if present
            if stripped.startswith(('Answer:', 'Final Answer:')):
                clean_line = stripped.replace('Answer:', '').replace('Final Answer:', '').strip()
                if clean_line:
                    clean_lines.append(clean_line)
                continue

        # Keep main content, remove only obvious AI artifacts
        should_keep = False

        if in_answer_section:
            # In answer section: keep all non-empty lines (including citations)
            should_keep = bool(stripped)
        elif (stripped and
              not stripped.startswith(('Thought:', 'Action:', 'Observation:')) and
              not re.search(r'Action Input:', stripped) and
              len(stripped) > 5):  # Keep substantial content lines
            should_keep = True

        if should_keep:
            clean_lines.append(line)

    clean_content = '\n'.join(clean_lines).strip()
    # Remove excessive blank lines while preserving structure
    clean_content = re.sub(r'\n\n\n+', '\n\n', clean_content)

    return clean_content


# REMOVED: save_artifacts_to_session function - VIOLATES SRR PRINCIPLES
# SRR for session_data is ChatHistoryManager. Use save_workflow_conversation_turn instead.


async def extract_workflow_response_content(final_result, workflow_name: str, logger: Any) -> str:
    """
    Unified response content extraction for all workflow types.
    Handles async generators, objects with .content, and various nested structures.
    """
    try:
        # Priority 1: Check if final_result is an async generator (unified streaming extraction)
        if hasattr(final_result, "__aiter__"):
            logger.debug(f"[{workflow_name}] Detected async generator, iterating for robust extraction")
            
            deltas = []
            thoughts = []
            accumulated_text = ""
            chunk_count = 0

            async for chunk in final_result:
                chunk_count += 1
                if chunk is None: continue

                try:
                    # [DEBUG] Log first 3 chunks with metadata to INFO for diagnostic purposes
                    if chunk_count <= 3:
                        try:
                            # Log chunk type and message metadata
                            c_type = type(chunk).__name__
                            m_kwargs = {}
                            if hasattr(chunk, 'message'):
                                m_kwargs = getattr(chunk.message, 'additional_kwargs', {})
                            
                            c_data = str(chunk)
                            if len(c_data) > 150: c_data = c_data[:150] + "..."
                            
                            logger.debug(f"[{workflow_name}] DEBUG CHUNK {chunk_count}: type={c_type} | kwargs={m_kwargs} | data={c_data}")
                        except Exception as e:
                            logger.debug(f"[{workflow_name}] DEBUG CHUNK {chunk_count}: error logging: {e}")

                    # 1. Delta-based extraction
                    delta_obj = getattr(chunk, 'delta', None)
                    if delta_obj is not None:
                        text = getattr(delta_obj, 'content', None) if not isinstance(delta_obj, str) else delta_obj
                        if text is None and not isinstance(delta_obj, str):
                            text = str(delta_obj)
                        if text:
                            deltas.append(str(text))

                    # 2. Accumulated Message Content & Thinking
                    message = getattr(chunk, 'message', None)
                    if message:
                        # Extract content
                        m_content = getattr(message, 'content', None)
                        if m_content:
                            accumulated_text = str(m_content)
                        
                        # Extract thinking/reasoning (often in additional_kwargs)
                        kwargs = getattr(message, 'additional_kwargs', {}) or {}
                        thought = kwargs.get('thinking') or kwargs.get('thought') or kwargs.get('reasoning')
                        if thought:
                            thoughts.append(str(thought))

                    # 3. Direct content attribute
                    direct_content = getattr(chunk, 'content', None)
                    if direct_content:
                        accumulated_text = str(direct_content)
                    
                    # 4. Handle string chunks directly
                    if isinstance(chunk, str) and chunk:
                        deltas.append(chunk)

                except Exception as e:
                    logger.debug(f"[{workflow_name}] Extraction skip on chunk {chunk_count}: {e}")
                    continue

            # Determine final content: Prefer deltas, fallback to accumulated, fallback to thoughts
            joined_deltas = "".join(deltas).strip()
            joined_thoughts = "".join(thoughts).strip()
            
            if joined_deltas:
                response_content = joined_deltas
            elif accumulated_text:
                response_content = accumulated_text.strip()
            elif joined_thoughts:
                response_content = f"*(Thinking...)*\n\n{joined_thoughts}"
            else:
                response_content = ""

            # Clean up response: remove excessive whitespace and repetitive labels
            import re
            response_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', response_content)
            
            # Clean up repeated "assistant: " prefixes that can appear in streaming responses
            response_content = re.sub(r'(?i)\b(assistant:\s*)+', '', response_content)
            response_content = response_content.strip()

            logger.info(f"[{workflow_name}] Extracted {len(response_content)} chars (Deltas={len(joined_deltas)}, Thinking={len(joined_thoughts)})")
            return response_content

        # Priority 2: Check if final_result has a .response attribute that is an async generator
        elif hasattr(final_result, 'response') and hasattr(final_result.response, '__aiter__'):
            logger.debug(f"[{workflow_name}] Detected async generator in final_result.response, iterating")
            async_responses = []
            chunk_count = 0

            async for chunk in final_result.response:
                chunk_count += 1

                try:
                    if isinstance(chunk, str):
                        async_responses.append(chunk)
                    elif hasattr(chunk, 'delta') and chunk.delta:
                        # Robust chunk extraction to avoid role label spam (e.g. "assistant: assistant:")
                        if isinstance(chunk.delta, str):
                            async_responses.append(chunk.delta)
                        elif hasattr(chunk.delta, 'content') and chunk.delta.content:
                            async_responses.append(str(chunk.delta.content))
                    elif hasattr(chunk, 'message') and chunk.message:
                        if hasattr(chunk.message, 'content') and chunk.message.content:
                            async_responses.append(str(chunk.message.content))
                        else:
                            async_responses.append(str(chunk.message))
                    elif hasattr(chunk, 'content') and chunk.content:
                        async_responses.append(str(chunk.content))
                    else:
                        chunk_str = str(chunk) if chunk is not None else ""
                        if not chunk_str.lower().startswith("assistant:"):
                            async_responses.append(chunk_str)
                except Exception as chunk_error:
                    logger.error(f"[{workflow_name}] Error processing chunk {chunk_count}: {chunk_error}")
                    continue

            response_content = ''.join(async_responses).strip()
            # Clean up response - remove excessive whitespace
            import re
            response_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', response_content.strip())
            logger.info(f"[{workflow_name}] Extracted content from response async generator: {len(response_content)} chars")
            return response_content

        # Priority 3: Check for .response.content
        elif hasattr(final_result, 'response') and hasattr(final_result.response, 'content'):
            response_content = final_result.response.content
            logger.debug(f"[{workflow_name}] Extracted content from response.content: {len(response_content) if response_content else 0} chars")
            return response_content

        # Priority 4: Check if final_result.response is a string
        elif hasattr(final_result, 'response') and isinstance(final_result.response, str):
            response_content = final_result.response
            logger.debug(f"[{workflow_name}] Extracted content from response string: {len(response_content)} chars")
            return response_content

        # Priority 5: Check if final_result itself has .content
        elif hasattr(final_result, 'content'):
            response_content = final_result.content
            logger.debug(f"[{workflow_name}] Extracted content from final_result.content: {len(response_content) if response_content else 0} chars")
            return response_content

        # Priority 6: Check if final_result is a dictionary (workflow result format)
        elif isinstance(final_result, dict) and 'response' in final_result:
            response_content = final_result['response']
            logger.debug(f"[{workflow_name}] Extracted response from dictionary: {len(response_content) if response_content else 0} chars")
            return response_content

        # Priority 7: Check if final_result is a string
        elif isinstance(final_result, str):
            response_content = final_result
            logger.debug(f"[{workflow_name}] Using final_result as string: {len(response_content)} chars")
            return response_content

        # Fallback: Convert to string
        else:
            response_content = str(final_result) if final_result is not None else ""
            logger.warning(f"[{workflow_name}] Using fallback string conversion: {len(response_content)} chars")
            return response_content

    except Exception as e:
        logger.error(f"[{workflow_name}] Failed to extract response content: {str(e)}")
        import traceback
        logger.error(f"[{workflow_name}] Extraction traceback: {traceback.format_exc()}")
        return f"Error extracting response: {str(e)}"


async def write_response_to_stream(response_result: Any, ctx: Any) -> str:
    """
    Generate contextual, informative response for deep research workflows.

    Analyzes research findings, context nodes, and workflow execution to create
    detailed responses that explain what was found (or not found) during research,
    similar to STARTER_TOOLS professional rendering.

    Args:
        response_result: Workflow response result (CompletionResponse or similar)
        ctx: Workflow context containing research state and memory

    Returns:
        str: Contextual response text for chat UI
    """
    try:
        from llama_index.core.settings import Settings

        # Extract research context from workflow context
        user_request = await ctx.get("user_request", "research query")
        total_questions = await ctx.get("total_questions", 0)
        context_nodes = await ctx.get("context_nodes", [])

        # Get research findings from memory
        research_findings = []
        if hasattr(ctx, 'memory') and ctx.memory:
            # Extract research findings from conversation memory
            for msg in ctx.memory.get_all():
                if (hasattr(msg, 'content') and msg.content and
                    ("Research Finding" in msg.content or "research" in msg.content.lower())):
                    research_findings.append(msg.content)

        # Analyze what was actually found vs what was requested
        found_relevant_info = len(context_nodes) > 0
        answered_questions = len(research_findings)

        # Generate contextual response based on research outcomes
        if answered_questions == 0 and not found_relevant_info:
            # No information found
            response = f"""The provided context contains no information related to '{user_request}'. No relevant documents or data were found in the knowledge base to address this research query."""

        elif answered_questions == 0 and found_relevant_info:
            # Documents found but no specific questions answered
            response = f"""The provided context contains {len(context_nodes)} documents that may be relevant to '{user_request}', but no specific research questions could be formulated or answered based on the available information."""

        elif answered_questions > 0:
            # Research was conducted and questions answered
            response = f"""Research completed on '{user_request}' with {answered_questions} questions investigated using {len(context_nodes)} source documents. The analysis revealed specific findings about the topic based on available research data."""

        else:
            # Fallback generic response
            response = f"""Deep research analysis completed for '{user_request}'. A comprehensive report has been generated based on the available knowledge base."""

        # Add source information if available
        if context_nodes:
            source_info = f" Research was conducted using {len(context_nodes)} source documents."
            response += source_info

        workflow_logger.debug(f"Generated contextual response: {response[:100]}...")
        return response

    except Exception as e:
        workflow_logger.error(f"Failed to generate contextual response: {e}")
        # Fallback to simple response
        return f"Deep research completed. A comprehensive report has been generated based on the available knowledge base."


async def generate_followup_questions(user_request: str, research_findings: List[str], context_nodes: List[Any]) -> List[str]:
    """
    Generate contextual follow-up questions based on deep research findings.

    Analyzes research results and knowledge gaps to suggest relevant follow-up questions,
    similar to STARTER_TOOLS professional question generation.

    Args:
        user_request: Original user research query
        research_findings: List of research findings and answers
        context_nodes: Documents used for research

    Returns:
        List[str]: A list of suggested follow-up questions.
    """
    try:
        import re
        from llama_index.core.settings import Settings

        if not research_findings:
            return []

        # Summarize research context
        findings_summary = "\n".join(research_findings[-5:])  # Last 5 findings
        available_sources = len(context_nodes)

        # Generate follow-up questions based on research
        followup_prompt = f"""
        Based on the deep research conducted on: "{user_request}"

        RESEARCH SUMMARY:
        {findings_summary}

        SOURCES ANALYZED: {available_sources} documents

        Generate 3-5 contextual follow-up questions that would help deepen understanding or explore related aspects. Focus on:

        1. **Knowledge Gaps**: Questions about areas not fully covered in current research
        2. **Practical Applications**: How findings apply to real-world scenarios
        3. **Related Concepts**: Connected topics worth exploring
        4. **Implementation Details**: Specific how-to questions
        5. **Comparative Analysis**: Different approaches or perspectives

        Return only the questions as a numbered list, no explanations.
        """

        response = await Settings.llm.acomplete(followup_prompt)
        questions_text = response.text.strip()

        # Parse questions from response
        questions = []
        for line in questions_text.split('\n'):
            line = line.strip()
            # Remove numbering (1., 2., etc.)
            if line and (line[0].isdigit() or line.startswith('-')):
                # Remove numbering and clean
                question = re.sub(r'^\d+\.?\s*', '', line)
                question = re.sub(r'^-\s*', '', question)
                if question and len(question) > 10:  # Substantial questions only
                    questions.append(question.strip())

        # Limit to 3-5 questions
        questions = questions[:5]

        return questions

    except Exception as e:
        workflow_logger.error(f"Failed to generate follow-up questions: {e}")
        return []


def cleanup_workflow_cuda_resources(session_id: str, context: dict):
    """
    Centralized CUDA memory cleanup for workflow sessions.

    Handles GPU resource cleanup when workflow sessions are terminated,
    preventing CUDA memory exhaustion issues. Called from session managers
    during session destruction.

    Args:
        session_id: Session identifier for logging
        context: Session context information (session_type, workflow_id, etc.)
    """
    session_type = context.get("session_type", "unknown")
    workflow_id = context.get("workflow_id", None)

    try:
        import torch
        import gc
        
        # 1. Force garbage collection to release objects that might be pinning CUDA memory
        gc.collect()

        if torch.cuda.is_available():
            # Get memory before cleanup for logging
            # Allocated = currently used by tensors
            # Reserved = total memory managed by the caching allocator
            alloc_before = torch.cuda.memory_allocated() / 1024**2
            res_before = torch.cuda.memory_reserved() / 1024**2

            # 2. Clear CUDA cache (returns unallocated reserved memory to OS)
            torch.cuda.empty_cache()

            # Get memory after cleanup
            alloc_after = torch.cuda.memory_allocated() / 1024**2
            res_after = torch.cuda.memory_reserved() / 1024**2
            
            freed_reserved = res_before - res_after
            freed_allocated = alloc_before - alloc_after

            workflow_logger.info(
                f"CUDA cleanup for {session_type} session {session_id}: "
                f"Freed {freed_allocated:.1f}MB (Allocated), {freed_reserved:.1f}MB (Reserved). "
                f"Remaining: {alloc_after:.1f}MB (Alloc), {res_after:.1f}MB (Res)"
                f"{f' - workflow {workflow_id}' if workflow_id else ''}"
            )

    except ImportError:
        # CUDA not available - log and continue
        pass
    except Exception as e:
        # Don't fail session cleanup if CUDA cleanup fails
        workflow_logger.warning(f"CUDA cleanup failed for session {session_id}: {e}")
