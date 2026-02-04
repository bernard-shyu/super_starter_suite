import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from super_starter_suite.shared.config_manager import UserConfig, config_manager
from llama_index.core.settings import Settings
# UNIFIED LOGGING SYSTEM - Replace global logging
llama_logger = config_manager.get_logger("shared")

# ------------------------------------------------------------------
# New utilities
# ------------------------------------------------------------------

def load_llm(user_config: UserConfig, chat_mode: bool = True, force_text_mode: bool = False, **kwargs):
    """
    Load an LLM instance based on the globally loaded user settings.

    Args:
        chat_mode: Whether to use chat mode or not (default: True)
        force_text_mode: Whether to force text-based structured prediction (bypassing tools)
        **kwargs: Additional arguments for LLM initialization

    Returns:
        Configured LLM instance

    Raises:
        RuntimeError: If user settings are not loaded or invalid
    """

    # Validate session context
    if not user_config:
        llama_logger.error("User config is None!")
        raise RuntimeError("User settings not loaded. Call load_user_config() first.")

    # Get LLM configuration from global settings
    try:
        provider = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.PROVIDER")
        model_id = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.ID")
        param    = user_config.get_user_setting("CHATBOT_AI_MODEL.PARAM")

        llama_logger.info(f"LLM config for user {user_config.user_id}: Provider: {provider}, Model: {model_id}, Param: {param}")

    except Exception as e:
        llama_logger.error(f"Error accessing LLM configuration: {str(e)}")
        raise RuntimeError(f"Error accessing LLM configuration: {str(e)}")

    if not provider or not model_id:
        llama_logger.error(f"Missing LLM provider ({provider}) or model-ID ({model_id}) for user {user_config.user_id}")
        raise ValueError(f"Missing LLM provider or model-ID in User Setting for {user_config.user_id}")

    # Load the LLM and set it in Settings
    llm = _load_llm(provider, model_id, param, chat_mode, force_text_mode=force_text_mode, **kwargs)

    # 🏷️ TAG THE INSTANCE: Store metadata on the instance for cache validation
    # Use object.__setattr__ to bypass Pydantic/dataclass strictness
    object.__setattr__(llm, '_sss_provider', provider)
    object.__setattr__(llm, '_sss_model_id', model_id)
    object.__setattr__(llm, '_sss_chat_mode', chat_mode)

    # CRITICAL: Set the LLM in Settings so it's used by workflows
    Settings.llm = llm
    return llm

def _load_llm(provider: str, model_id: str, param: Optional[Dict[str, Any]] = None, chat_mode: bool = True, force_text_mode: bool = False, **kwargs):
    # Load the appropriate LLM
    try:
        match provider.lower():
            case "nvidia" | "nv":
                from llama_index.llms.nvidia import NVIDIA
                from llama_index.llms.nvidia.utils import determine_model
                if determine_model(model_id) is None:
                    llama_logger.info(f"NOTICE: Nvidia LLM Model '{model_id}' is not defined in Llama-Index known-list. Using OpenAI-Like mode.")
                    return _load_llm("openailike", model_id, param, chat_mode, force_text_mode, **kwargs)

                llm = NVIDIA(is_chat_model=True, is_function_calling_model=True,
                    api_key=os.environ.get("NVIDIA_API_KEY"),
                    model=model_id,
                    timeout=float(os.getenv("MY_TIME_OUT") or 300.0),
                    **kwargs)

                # 🛠️ Solution F Patch: Force text mode for certain providers (like NVIDIA) if requested
                if force_text_mode:
                    _apply_nvidia_text_patch(llm)
                else:
                    _apply_nvidia_tool_patch(llm)

            case "openai" | "oai":
                from llama_index.llms.openai import OpenAI
                llm = OpenAI(is_chat_model=chat_mode,
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    model=model_id,
                    **kwargs)

            case "openailike" | "oalike" | "oal":
                from llama_index.llms.openai_like import OpenAILike
                llm = OpenAILike(is_chat_model=chat_mode,
                    api_base="https://integrate.api.nvidia.com/v1",
                    api_key=os.environ.get("NVIDIA_API_KEY"),
                    model=model_id,
                    timeout=float(os.getenv("MY_TIME_OUT") or 300.0),
                    **kwargs)

            case "vllm":
                from llama_index.llms.vllm import Vllm
                os.environ["HF_HOME"] = "~/.cache/huggingface/"
                llm = Vllm(is_chat_model=chat_mode,
                    model=model_id,
                    vllm_kwargs=param or {},
                    **kwargs)

            case "vllm_server" | "vserv":
                from llama_index.llms.vllm import VllmServer
                llm = VllmServer(
                    api_url="http://localhost:8000/generate",
                    max_new_tokens=100,
                    temperature=0)

            case "ollama":
                from llama_index.llms.ollama import Ollama
                llm = Ollama(is_chat_model=chat_mode,
                    model=model_id,
                    request_timeout=float(os.getenv("MY_TIME_OUT") or 300.0),
                    **kwargs)

            case "google_genai" | "gemini" | "gem":
                from llama_index.llms.google_genai import GoogleGenAI
                llm = GoogleGenAI(is_chat_model=chat_mode,
                    api_key=os.environ.get("GEMINI_API_KEY"),
                    model=model_id,
                    **kwargs)

            case "openrouter" | "or":
                from llama_index.llms.openrouter import OpenRouter
                llm = OpenRouter(is_chat_model=chat_mode,
                    api_key=os.environ.get("OPENROUTER_API_KEY"),
                    model=model_id,
                    **kwargs)

            case "azureai" | "azureai1" | "azureai2" | "az" | "az1" | "az2":
                from llama_index.llms.azure_inference import AzureAICompletionsModel
                match provider[-1]:
                    case "1": api_keyID = "GITHUB_TOKEN_BXU"
                    case "2": api_keyID = "GITHUB_TOKEN_MEI"
                    case _: api_keyID = "GITHUB_TOKEN"
                llm = AzureAICompletionsModel(
                    endpoint="https://models.github.ai/inference",
                    credential=os.environ.get(api_keyID, ""),
                    model_name=model_id,
                    **kwargs)

            case _:
                raise ValueError(f"Unsupported LLM provider: {provider}")

        return llm
    except Exception as e:
        raise RuntimeError(f"Failed to load LLM: {str(e)}")

def _apply_nvidia_text_patch(llm):
    """
    Apply an instance-level patch to NVIDIA LLM to handle tool-less structured prediction.
    This avoids the 'Tools cannot be empty' error by falling back to LLMTextCompletionProgram.
    """
    from types import MethodType
    from llama_index.core.program import LLMTextCompletionProgram

    # 🛡️ SAFETY CHECK: Safely check for the method.
    # Some LlamaIndex models (like OpenAILike) might raise Pydantic-specific errors on attribute access.
    try:
        original_astructured_predict = getattr(llm, 'astructured_predict', None)
    except Exception:
        original_astructured_predict = None

    if original_astructured_predict is None:
        llama_logger.debug(f"Skipping NVIDIA patch: {type(llm).__name__} does not have astructured_predict")
        return

    async def patched_astructured_predict(self, output_cls, prompt, **kwargs):
        # If no tools are provided, use text-based completion program
        if not kwargs.get("tools"):
            program = LLMTextCompletionProgram.from_defaults(
                output_cls=output_cls,
                prompt=prompt,
                llm=self
            )
            return await program.acall(**kwargs)
        # Otherwise use original implementation
        return await original_astructured_predict(output_cls, prompt, **kwargs)

    # Attach the patched method to the instance
    # 🎯 FIX: Use object.__setattr__ to bypass Pydantic's strict field validation
    # (otherwise it fails for 'OpenAILike' with 'no field' error)
    object.__setattr__(llm, 'astructured_predict', MethodType(patched_astructured_predict, llm))

def _apply_nvidia_tool_patch(llm):
    """
    Apply a monkey-patch to NVIDIA LLM instance to handle 'None' arguments in tool calls.
    This fixes the 'TypeError: the JSON object must be str...' crash with Llama 3.1 405B.
    """
    from types import MethodType
    from llama_index.core.llms import ChatResponse
    import json
    
    # Check if method exists before patching
    original_get_tool_calls = getattr(llm, 'get_tool_calls_from_response', None)
    if not original_get_tool_calls:
        return

    def patched_get_tool_calls_from_response(self, response: ChatResponse, error_on_no_tool_call: bool = True, **kwargs: Any):
        """
        NVIDIA / Llama 3.1 405B Patch: Handle fragmented and malformed tool calls.
        IMPORTANT: This must be IMMUTABLE to avoid poisoning the stream buffer.
        """
        from llama_index.core.llms.llm import ToolSelection
        import copy
        import re

        # 1. Extract raw tool calls from response without mutating it
        if not hasattr(response, 'message') or not hasattr(response.message, 'additional_kwargs'):
            return original_get_tool_calls(response, error_on_no_tool_call=error_on_no_tool_call, **kwargs)

        raw_tool_calls = response.message.additional_kwargs.get('tool_calls', [])
        if not raw_tool_calls:
            return original_get_tool_calls(response, error_on_no_tool_call=error_on_no_tool_call, **kwargs)

        # 2. Process and Clean Tool Calls (Work on local variables only)
        final_tool_calls = []
        
        # 🛠️ AGGRESSIVE MERGING: If there are multiple fragments, join them first
        if len(raw_tool_calls) > 1:
            llama_logger.debug(f"ToolPatch: Merging {len(raw_tool_calls)} fragmented tool calls.")
            merged_args = ""
            base_tc = raw_tool_calls[0]
            
            for tc in raw_tool_calls:
                arg = getattr(getattr(tc, 'function', None), 'arguments', "") or ""
                # Strip artifacts that appear during fragmentation
                if arg.startswith("{}"): arg = arg[2:]
                # Llama 3.1 tends to repeat the preamble in every fragment: {}"input": "
                if '{"input": "' in arg:
                     arg = arg.split('{"input": "', 1)[-1]
                merged_args += arg
            
            # Ensure it starts with the correct header if it looks like partial input
            if not merged_args.startswith('{'):
                merged_args = '{"input": "' + merged_args
            
            # Create a synthetic tool call for evaluation
            temp_tc = copy.deepcopy(base_tc)
            temp_tc.function.arguments = merged_args
            current_raw_calls = [temp_tc]
        else:
            current_raw_calls = [copy.deepcopy(tc) for tc in raw_tool_calls]

        # 3. Individual Call Repair & Validation
        for tool_call in current_raw_calls:
            if not hasattr(tool_call, 'function'): continue
            
            args = tool_call.function.arguments
            if args is None or (isinstance(args, str) and args.strip() in ("", "{}", "{}u")):
                tool_call.function.arguments = "{}"
                final_tool_calls.append(tool_call)
                continue
            
            if isinstance(args, str):
                cleaned = args.strip()
                # Strip prepended garbage
                if cleaned.startswith("{}") and len(cleaned) > 2: cleaned = cleaned[2:].strip()
                
                success = False
                repaired_args = "{}"
                
                # Try 1: Valid JSON
                try: 
                    json.loads(cleaned)
                    repaired_args = cleaned
                    success = True
                except Exception: pass

                # Try 2: Regex extraction (Handle trailing junk like '"}s"')
                if not success:
                    match = re.search(r'(\{.*\})', cleaned)
                    if match:
                        try:
                            candidate = match.group(1)
                            json.loads(candidate)
                            repaired_args = candidate
                            success = True
                        except Exception: pass

                # Try 3: Repair partial JSON (unclosed quotes/braces)
                if not success:
                    try:
                        candidate = cleaned
                        # Fix broken escape sequences at the very end
                        if candidate.endswith('\\'): candidate += '\\'
                        
                        # Close unclosed quotes
                        if candidate.count('"') % 2 != 0: candidate += '"'
                        
                        # Close unclosed braces
                        open_braces = candidate.count('{') - candidate.count('}')
                        if open_braces > 0: candidate += '}' * open_braces
                        
                        json.loads(candidate)
                        repaired_args = candidate
                        llama_logger.debug(f"ToolPatch: Repaired partial JSON: {args!r} -> {candidate!r}")
                        success = True
                    except Exception: pass

                # Try 4: Heuristic wrapping for query_index
                if not success:
                    # If it's just raw text, wrap it. 
                    # Smart strip: If it looks like a partial "input": " header, strip it first.
                    text_meat = cleaned
                    # Remove various forms of partial JSON headers Llama likes to vomit
                    text_meat = re.sub(r'^\{?\s*"input"\s*:\s*"?', '', text_meat)
                    text_meat = re.sub(r'["\}]+$', '', text_meat) # Strip trailing quotes/braces
                    text_meat = text_meat.strip()
                    
                    if len(text_meat) > 2:
                        tool_name = getattr(tool_call.function, 'name', '')
                        if tool_name == "query_index":
                            repaired_args = json.dumps({"input": text_meat})
                            llama_logger.debug(f"ToolPatch: Wrapped raw text: {args!r} -> {repaired_args!r}")
                            success = True

                if not success:
                    llama_logger.warning(f"ToolPatch: Could not repair arguments. Falling back to empty JSON. Original: {args!r}")
                    repaired_args = "{}"
                
                tool_call.function.arguments = repaired_args
                final_tool_calls.append(tool_call)

        # 4. Construct back to LlamaIndex ToolSelection objects
        results = []
        for tc in final_tool_calls:
            results.append(ToolSelection(
                tool_id=getattr(tc, 'id', 'call_fake'),
                tool_name=getattr(tc.function, 'name', 'unknown'),
                tool_kwargs=json.loads(tc.function.arguments) if tc.function.arguments else {}
            ))
        return results

    # Apply the patch using object.__setattr__ to bypass Pydantic validity checks
    object.__setattr__(llm, 'get_tool_calls_from_response', MethodType(patched_get_tool_calls_from_response, llm))
    llama_logger.debug(f"Applied NVIDIA tool patch to {llm.metadata.model_name}")

def init_llm(user_config: UserConfig, force_text_mode: bool = False):
    """
    Helper to initialize LLM for a request.
    Expects request_state.user_config to be set.
    Reentry-safe: only initializes LLM once per session (unless forced).
    """
    # 🎯 FORCE TEXT MODE: The signal now comes as a flag, not a workflow ID string
    if force_text_mode:
        llama_logger.info(f"Force text mode flag received in init_llm")

    # Get current desired config
    try:
        desired_provider = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.PROVIDER")
        desired_model_id = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.ID")
    except Exception:
        desired_provider = None
        desired_model_id = None

    # Check if LLM is already initialized (reentry safety with CHANGE DETECTION)
    # 🎯 FIX: Check _llm directly to avoid triggering LlamaIndex's lazy initialization of default OpenAI model
    current_llm = getattr(Settings, '_llm', None)
    if current_llm is not None:
        # Check if it's not the default MockLLM
        if not str(current_llm).startswith('<llama_index.core.llms.mock.MockLLM'):
            # VALIDATE CACHED LLM: Check if it matches desired configuration
            cached_provider = getattr(current_llm, '_sss_provider', None)
            cached_model_id = getattr(current_llm, '_sss_model_id', None)

            # If matches and NO special patch requested, we can skip
            if not force_text_mode and cached_provider == desired_provider and cached_model_id == desired_model_id:
                llama_logger.debug(f"LLM already initialized and matches config for user {user_config.user_id}, skipping re-initialization")
                return current_llm
            else:
                reason = "force_text_mode requested" if force_text_mode else f"config change detected: {cached_provider}/{cached_model_id} -> {desired_provider}/{desired_model_id}"
                llama_logger.info(f"Re-initializing LLM for user {user_config.user_id}: {reason}")
        else:
            pass

    try:
        return load_llm(user_config, force_text_mode=force_text_mode)
    except Exception as e:
        llama_logger.error(f"init_llm FAILED for user {user_config.user_id}: {str(e)}")
        return None

# ------------------------------------------------------------------
# Model Listing Utilities
# ------------------------------------------------------------------

def get_nvidia_models() -> List[Dict[str, Any]]:
    """Fetches model list from NVIDIA API."""
    try:
        from llama_index.llms.nvidia import NVIDIA
        from llama_index.llms.nvidia.utils import determine_model
        nv_llm = NVIDIA()
        models = []
        for m in nv_llm.available_models:
            is_new = determine_model(m.id) is None
            models.append({
                "id": m.id,
                "provider": "nvidia",
                "type": m.model_type,
                "supports_tools": m.supports_tools,
                "supports_structured": m.supports_structured_output,
                "is_new": is_new
            })
        return models
    except Exception as e:
        llama_logger.error(f"Failed to fetch NVIDIA models: {str(e)}")
        raise

def get_openrouter_models() -> List[Dict[str, Any]]:
    """Fetches model list from OpenRouter API."""
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', [])
            models = []
            for m in data:
                models.append({
                    "id": m.get('id'),
                    "provider": "OpenRouter",
                    "name": m.get('name'),
                    "context_length": m.get('context_length'),
                    "description": m.get('description', '')[:100]
                })
            return sorted(models, key=lambda x: x['id'].lower())
        else:
            llama_logger.error(f"Failed to fetch OpenRouter models: {response.status_code}")
            return []
    except Exception as e:
        llama_logger.error(f"Error fetching OpenRouter models: {str(e)}")
        return []

def get_azure_models() -> List[Dict[str, Any]]:
    """Fetches model list from Azure (GitHub Models) API."""
    try:
        api_token = os.getenv("GITHUB_TOKEN")
        if not api_token:
            llama_logger.warning("GITHUB_TOKEN not set for Azure models fetch")
            return []
        
        url = "https://models.github.ai/catalog/models"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else (data.get("models") or data.get("data") or [])
            models = []
            for m in items:
                models.append({
                    "id": m.get("model_id") or m.get("id"),
                    "provider": "azureAI",
                    "name": m.get("name")
                })
            return models
        else:
            llama_logger.error(f"Failed to fetch Azure models: {resp.status_code}")
            return []
    except Exception as e:
        llama_logger.error(f"Error fetching Azure models: {str(e)}")
        return []

def list_external_models(source: str) -> Dict[str, Any]:
    """
    Unified entry point for listing models from various sources.
    
    Returns:
        A dictionary with "models" key and optional "warning" key.
    """
    source_lower = source.lower()
    
    if source_lower == "system":
        system_config = config_manager.load_system_config()
        return {"models": system_config.get("AI_MODELS_AVAILABLE", {}).get("CHATBOT", [])}
    
    elif source_lower == "nvidia":
        try:
            return {"models": get_nvidia_models()}
        except Exception as e:
            return {"models": [], "error": str(e)}
            
    elif source_lower == "openrouter":
        return {"models": get_openrouter_models()}
        
    elif source_lower == "azure" or source_lower == "azureai":
        models = get_azure_models()
        if not models and not os.getenv("GITHUB_TOKEN"):
            return {"models": [], "warning": "GITHUB_TOKEN not set"}
        return {"models": models}
        
    else:
        return {"models": [], "error": f"Unsupported model source: {source}"}
