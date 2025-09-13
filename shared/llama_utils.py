import os
from typing import Dict, Any, Optional, List
from super_starter_suite.shared.config_manager import UserConfig, config_manager
from llama_index.core.settings import Settings

# UNIFIED LOGGING SYSTEM - Replace global logging
llama_logger = config_manager.get_logger("llama")

# ------------------------------------------------------------------
# New utilities
# ------------------------------------------------------------------

def load_llm(user_config: UserConfig, chat_mode: bool = True, **kwargs):
    """
    Load an LLM instance based on the globally loaded user settings.

    Args:
        chat_mode: Whether to use chat mode or not (default: True)
        **kwargs: Additional arguments for LLM initialization

    Returns:
        Configured LLM instance

    Raises:
        RuntimeError: If user settings are not loaded or invalid
    """

    # Validate session context
    if not user_config:
        llama_logger.error("[DEBUG] User config is None!")
        raise RuntimeError("User settings not loaded. Call load_user_config() first.")

    # Get LLM configuration from global settings
    try:
        provider = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.PROVIDER")
        model_id = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED.ID")
        param    = user_config.get_user_setting("CHATBOT_AI_MODEL.PARAM")

        llama_logger.debug(f"[DEBUG] LLM config - Provider: {provider}, Model: {model_id}, Param: {param}")

    except Exception as e:
        llama_logger.error(f"[DEBUG] Error accessing LLM configuration: {str(e)}")
        raise RuntimeError(f"Error accessing LLM configuration: {str(e)}")

    if not provider or not model_id:
        llama_logger.error(f"[DEBUG] Missing LLM provider ({provider}) or model-ID ({model_id}) for user {user_config.user_id}")
        raise ValueError(f"Missing LLM provider or model-ID in User Setting for {user_config.user_id}")

    # Load the LLM and set it in Settings
    llm = _load_llm(provider, model_id, param, chat_mode, **kwargs)

    # CRITICAL: Set the LLM in Settings so it's used by workflows
    Settings.llm = llm
    return llm

def _load_llm(provider: str, model_id: str, param: Optional[Dict[str, Any]] = None, chat_mode: bool = True, **kwargs):
    # Load the appropriate LLM
    try:
        match provider.lower():
            case "nvidia" | "nv":
                from llama_index.llms.nvidia import NVIDIA
                from llama_index.llms.nvidia.utils import determine_model
                if determine_model(model_id) is None:
                    llama_logger.info(f"NOTICE: Nvidia LLM Model '{model_id}' is not defined in Llama-Index known-list. Using OpenAI-Like mode.")
                    return _load_llm("openailike", model_id, param, chat_mode, **kwargs)

                llm = NVIDIA(is_chat_model=True, is_function_calling_model=False,
                    api_key=os.environ.get("NVIDIA_API_KEY"),
                    model=model_id,
                    timeout=float(os.getenv("MY_TIME_OUT") or 120.0),
                    **kwargs)

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
                    is_function_calling_model=False,
                    timeout=float(os.getenv("MY_TIME_OUT") or 150.0),
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

def init_llm(user_config: UserConfig):
    """
    Helper to initialize LLM for a request.
    Expects request_state.user_config to be set.
    Reentry-safe: only initializes LLM once per session.
    """
    # Check if LLM is already initialized (reentry safety)
    if hasattr(Settings, '_llm') and Settings._llm is not None:
        # Check if it's not the default MockLLM
        if not str(Settings._llm).startswith('<llama_index.core.llms.mock.MockLLM'):
            llama_logger.debug(f"[DEBUG] LLM already initialized for user {user_config.user_id}, skipping re-initialization")
            return Settings._llm
        else:
            llama_logger.debug(f"[DEBUG] Current LLM is MockLLM, will reinitialize")

    llama_logger.debug(f"[DEBUG] Initializing LLM for user {user_config.user_id}")
    try:
        load_llm(user_config)
    except Exception as e:
        llama_logger.error(f"[DEBUG] init_llm FAILED for user {user_config.user_id}: {str(e)}")
