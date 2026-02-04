"""
UI Enhancement Functions

Functions for enhancing workflow responses for UI rendering.
Handles citations, artifacts, and progress states for frontend display.
"""

from typing import Dict, Any, List, Optional
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.dto import WorkflowConfig

# UNIFIED LOGGING SYSTEM
workflow_logger = config_manager.get_logger("workflow.ui_event")


# 🎯 ENHANCED WORKFLOW EXECUTION: UI Rendering Support for ALL Workflow Types
# Replaces the problematic UnifiedWorkflowExecutionEngine with clean UI enhancements

def enhance_workflow_execution_for_ui(response_data: Dict[str, Any], workflow_config: 'WorkflowConfig') -> Dict[str, Any]:
    """
    🎨 FRONT-END ENHANCED UI RENDERING: Apply to ALL workflow types (adapted/ported/meta)

    Adds rendering_instructions to workflow responses for consistent UI display:
    - Citations with clickable links
    - Artifacts in dedicated panel display
    - Progressive state display
    - Tool calls and follow-up questions

    Supports both adapted (STARTER_TOOLS) and ported (Pattern C) workflows equally.

    Args:
        response_data: Raw workflow response (response, artifacts, enhanced_metadata)
        workflow_config: Complete workflow configuration from system_config.toml

    Returns:
        Enhanced response with rendering_instructions for frontend
    """
    try:
        # Extract components from response
        workflow_response = response_data.get('response', '')
        artifacts_collected = response_data.get('artifacts', [])
        enhanced_metadata = response_data.get('enhanced_metadata', {})

        workflow_logger.debug(f"[UI_ENHANCER] Enhancing response for {workflow_config.display_name}, response length: {len(workflow_response)}")
        workflow_logger.debug(f"[UI_ENHANCER] DEBUG - Input enhanced_metadata keys: {list(enhanced_metadata.keys())}")
        workflow_logger.debug(f"[UI_ENHANCER] DEBUG - Input enhanced_metadata.citations: {enhanced_metadata.get('citations')}")
        workflow_logger.debug(f"[UI_ENHANCER] DEBUG - Input enhanced_metadata.citation_metadata: {enhanced_metadata.get('citation_metadata')}")

        # Log progress states to backend instead of UI display
        _log_progress_states_to_backend(workflow_response, workflow_config)

        # 🎯 BUILD RENDERING INSTRUCTIONS using workflow config + response data
        # Preserve original enhanced_metadata and add rendering instructions
        rendering_instructions = {
            # Preserve original metadata
            **enhanced_metadata,

            # Citations: Process for clickable [citation:uuid] links
            "citations": _extract_citations_for_ui(workflow_response, artifacts_collected, enhanced_metadata),

            # Artifacts: Format for ArtifactDisplayManager (dedicated panel)
            "artifacts": _prepare_artifacts_for_ui(artifacts_collected, workflow_config),

            # Follow-up questions: Extract from workflow response or generate based on context
            "followup_questions": _extract_followup_questions(workflow_response, enhanced_metadata, workflow_config),

            # UI Component: Which frontend renderer to use
            "ui_component": workflow_config.ui_component or "SimpleWorkflowProgress",

            # Display flags from config (can be overridden by enhanced_metadata) - ENSURE STRING VALUES FOR show_citation
            "show_citation": enhanced_metadata.get('show_citation', workflow_config.show_citation or "None"),
            "show_tool_calls": bool(enhanced_metadata.get('show_tool_calls', workflow_config.show_tool_calls or False)),
            "show_followup_questions": bool(enhanced_metadata.get('show_followup_questions', workflow_config.show_followup_questions or False)),
            "show_workflow_states": bool(enhanced_metadata.get('show_workflow_states', workflow_config.show_workflow_states or False)),
        }

        # Return enhanced response with rendering instructions
        enhanced_response = {
            "response": workflow_response,
            "artifacts": artifacts_collected,
            "enhanced_metadata": rendering_instructions  # ← UI rendering instructions (preserves original metadata)
        }

        return enhanced_response

    except Exception as e:
        workflow_logger.warning(f"[UI_ENHANCER] Failed to enhance workflow response: {e}")
        import traceback
        workflow_logger.warning(f"[UI_ENHANCER] Traceback: {traceback.format_exc()}")
        # Return original response on enhancement failure
        return response_data

def _extract_citations_for_ui(response_text: str, artifacts: List[Dict], enhanced_metadata: Dict) -> List[str]:
    """Extract citations from response for UI clickable links"""
    citations = []

    # Extract [citation:uuid] markers from response text (Format 1: Native LlamaIndex)
    import re
    response_citations = re.findall(r'\[citation:[^\]]+\]', response_text)
    citations.extend(response_citations)

    # Handle numbered citations [1], [2], etc. by mapping to citation_metadata UUIDs (Format 2: Numbered)
    citation_metadata = enhanced_metadata.get('citation_metadata', {})
    if citation_metadata and not response_citations:
        # Extract numbered citation markers [1], [2], etc.
        numbered_citations = re.findall(r'\[(\d+)\]', response_text)
        if numbered_citations:
            # Sort unique citation numbers and map to UUIDs in order
            unique_numbers = sorted(list(set(int(num) for num in numbered_citations)))
            metadata_uuids = list(citation_metadata.keys())

            for i, num in enumerate(unique_numbers):
                if i < len(metadata_uuids):
                    citations.append(f'[citation:{metadata_uuids[i]}]')

    # CRITICAL FIX: Always populate citations from citation_metadata when available
    # This handles cases where ported workflows don't include markers in response text
    if citation_metadata and not citations:
        # Convert citation_metadata UUIDs to citation markers for UI
        for uuid in citation_metadata.keys():
            citations.append(f'[citation:{uuid}]')
        workflow_logger.debug(f"[UI_ENHANCER] Populated {len(citations)} citations from citation_metadata")

    # Add citations from enhanced metadata if available
    metadata_citations = enhanced_metadata.get('citations', [])
    citations.extend(metadata_citations)

    # Also check 'citations' array which may contain citations in some workflows
    sources_citations = enhanced_metadata.get('citations', [])
    citations.extend(sources_citations)

    return list(set(citations))  # Remove duplicates

def _prepare_artifacts_for_ui(artifacts: List[Dict], workflow_config: 'WorkflowConfig') -> List[Dict]:
    """Prepare artifacts for dedicated ArtifactDisplayManager UI"""
    if not artifacts:
        return []

    prepared_artifacts = []
    for artifact in artifacts:
        # Normalize artifact structure for consistent UI display
        prepared = {
            'type': artifact.get('type', 'unknown'),
            'language': artifact.get('language', 'text'),
            'code': artifact.get('code') or artifact.get('content', ''),
            'filename': artifact.get('file_name') or artifact.get('filename', ''),
            'title': artifact.get('title', ''),
            'data': artifact.get('data'),
            'created_at': artifact.get('created_at')
        }

        # Generate title if missing based on workflow config + artifact type
        if not prepared['title']:
            prepared['title'] = _generate_artifact_title(prepared, workflow_config.display_name)

        prepared_artifacts.append(prepared)

    return prepared_artifacts

def _log_progress_states_to_backend(response_text: str, workflow_config: 'WorkflowConfig') -> None:
    """Log progressive states to backend logger instead of UI display"""
    try:
        # Extract from response text pattern matching
        extracted_states = _extract_progress_from_response(response_text)

        # Combine states
        all_states = list(set(extracted_states))

        if all_states:
            workflow_logger.info(f"[UI_ENHANCER] ⚡ Progress states for {workflow_config.display_name}: {', '.join(all_states)}")
        else:
            workflow_logger.debug(f"[UI_ENHANCER] No progress states detected for {workflow_config.display_name}")

    except Exception as e:
        workflow_logger.warning(f"[UI_ENHANCER] Failed to log progress states: {e}")

def _extract_progress_from_response(response: str) -> List[str]:
    """Extract progress indications from workflow response text"""
    progress_indicators = []

    # Look for common progress patterns
    import re
    patterns = [
        r'(?:\(|▶\s*|•\s*)([A-Z]\w+|[Gg]enerating|[Aa]nalyzing|[Pp]lanning|[Cc]ompleting)[\s.:)]',
        r'(\w+ing|\w+ed)[\s.,]',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response)
        progress_indicators.extend(matches)

    return progress_indicators

def _extract_followup_questions(response_text: str, enhanced_metadata: Dict, workflow_config: 'WorkflowConfig') -> List[str]:
    """Extract follow-up questions from workflow response and metadata"""
    followup_questions = []

    try:
        # Check enhanced_metadata for follow-up questions (generated by workflow)
        metadata_questions = enhanced_metadata.get('followup_questions', [])
        if metadata_questions:
            followup_questions.extend(metadata_questions)
            workflow_logger.debug(f"[UI_ENHANCER] Found {len(metadata_questions)} follow-up questions in metadata")

        # Extract from response text patterns (fallback)
        if not followup_questions:
            import re
            # Look for question patterns in response
            question_patterns = [
                r'(?:>\s*|•\s*|\*\s*)([^\n\?\.!]*\?)',  # Questions starting with > or bullets
                r'(?:Follow-up|Next|Additional) (?:question|questions?):?\s*([^\n]+)',
                r'([A-Z][^\n\?\.!]*\?)'  # Capitalized questions
            ]

            for pattern in question_patterns:
                matches = re.findall(pattern, response_text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    question = match.strip()
                    if question and len(question) > 10 and question not in followup_questions:
                        followup_questions.append(question)

        # Limit to reasonable number
        followup_questions = followup_questions[:5]

        if followup_questions:
            workflow_logger.debug(f"[UI_ENHANCER] Extracted {len(followup_questions)} follow-up questions")

    except Exception as e:
        workflow_logger.warning(f"[UI_ENHANCER] Failed to extract follow-up questions: {e}")

    return followup_questions


def _generate_artifact_title(artifact: Dict[str, str], workflow_display_name: str) -> str:
    """Generate descriptive title for artifact based on type and workflow"""
    artifact_type = artifact.get('type', 'unknown')
    language = artifact.get('language', 'unknown')

    if artifact_type == 'code':
        if language and language != 'text':
            return f"Generated {language.title()} Code"
        return "Generated Code"

    elif artifact_type in ['document', 'report']:
        return f"Generated {artifact_type.title()}"

    elif artifact_type in ['analysis', 'data']:
        return f"Generated {artifact_type.title()}"

    else:
        return f"{workflow_display_name} Output"
