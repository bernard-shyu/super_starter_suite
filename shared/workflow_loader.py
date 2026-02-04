"""
Dynamic Workflow Loader Module

This module provides functionality for dynamically loading workflow modules,
routers, and classes at runtime. It enables the pluggable workflow architecture
by allowing workflows to be configured in system_config.toml and loaded on demand.
"""

import importlib
import inspect
import sys
from typing import Type, Tuple, Dict, Any, Optional, Union
from abc import ABC

from fastapi import APIRouter
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.dto import WorkflowConfig
from typing import Dict

# Type aliases for better code readability
WorkflowClass = Type[Any]
WorkflowEvent = Type[Any]

logger = config_manager.get_logger("workflow.loader")


def get_workflow_config(workflow_ID: str) -> WorkflowConfig:
    """
    Get a single workflow configuration by ID.

    Args:
        workflow_ID: The workflow identifier to look up (e.g., 'A_code_generator')

    Returns:
        WorkflowConfig: The configuration for the specified workflow

    Raises:
        ValueError: If the workflow ID is not found in configuration
    """
    workflow_config = get_all_workflow_configs().get(workflow_ID)
    if workflow_config is None:
        raise ValueError(f"Workflow config for '{workflow_ID}' not found in system config")
    return workflow_config


def get_all_workflow_configs() -> Dict[str, WorkflowConfig]:
    """
    🎯 UNIFIED CONFIG LOADER: Get complete workflow configurations with all properties inlined.

    No reference section lookups - returns complete config objects ready for use.

    Returns:
        Dict[str, WorkflowConfig]: Dictionary mapping workflow IDs to complete config objects
    """
    workflow_section = config_manager.system_config.get("WORKFLOW", {})

    workflow_configs: Dict[str, WorkflowConfig] = {}
    for workflow_id, config_dict in workflow_section.items():
        try:
            # 🎯 DIRECT INLINED CONFIGURATION - No reference lookups needed
            workflow_config = WorkflowConfig(
                # 🎯 CORE WORKFLOW PROPERTIES
                code_path=config_dict.get("code_path", ""),
                timeout=config_dict.get("timeout", 60.0),
                display_name=config_dict.get("display_name", workflow_id),
                description=config_dict.get("description", None),
                icon=config_dict.get("icon", None),

                # 🎯 INTEGRATION TYPE PROPERTIES
                integrate_type=config_dict.get("integrate_type", "adapted"),
                response_format=config_dict.get("response_format", "json"),

                # 🎯 ARTIFACT CONFIGURATION
                artifact_enabled=config_dict.get("artifact_enabled", False),
                artifacts_enabled=config_dict.get("artifacts_enabled", False),
                synthetic_response=config_dict.get("synthetic_response", None),

                # 🎯 SESSION MANAGEMENT
                chat_history_context=config_dict.get("chat_history_context", True),

                # 🎯 WORKFLOW IDENTIFICATION
                workflow_ID=workflow_id,  # SINGLE RESPONSIBILITY: Store raw workflow ID for session management

                # 🎯 UNIFIED UI CONFIGURATION (directly inlined - no reference sections)
                ui_component=config_dict.get("ui_component", None),

                # 🎯 UNIFIED RENDERING FLAGS (directly inlined - no reference sections)
                show_tool_calls=config_dict.get("show_tool_calls", False),
                show_citation=config_dict.get("show_citation", "None"),
                show_followup_questions=config_dict.get("show_followup_questions", False),
                show_workflow_states=config_dict.get("show_workflow_states", False),

                # 🎯 CLI WORKFLOW FEATURES
                hie_enabled=config_dict.get("hie_enabled", False),

                # 🎯 LLM BEHAVIOR FLAGS
                force_text_structured_predict=config_dict.get("force_text_structured_predict", False)
            )

            workflow_configs[workflow_id] = workflow_config
        except Exception as e:
            logger.error(f"Error loading unified workflow config for '{workflow_id}': {e}")
            # Skip this workflow config if there's an error
            continue

    return workflow_configs


def get_ui_pattern_config(workflow_id: str) -> Optional[Dict]:
    """
    Get UI pattern configuration for a workflow.

    Args:
        workflow_id: The workflow identifier

    Returns:
        UI pattern configuration dictionary or None if not found
    """
    workflow_config = get_workflow_config(workflow_id)
    ui_pattern_name = getattr(workflow_config, 'ui_pattern', None)

    if not ui_pattern_name:
        return None

    ui_patterns = config_manager.system_config.get("WF_UI_PATTERN", {})
    pattern_config = ui_patterns.get(ui_pattern_name)

    if not pattern_config:
        logger.warning(f"UI pattern '{ui_pattern_name}' not found for workflow '{workflow_id}'")
        return None

    return pattern_config

def load_workflow_module(workflow_id: str, workflow_config: WorkflowConfig) -> Tuple[APIRouter, Optional[WorkflowClass], Optional[WorkflowEvent], Optional[Type[Any]]]:
    """
    Dynamically load a workflow module and extract its components, including an optional initializer.

    Args:
        workflow_id: The unique identifier for the workflow (e.g., 'A_agentic_rag')
        workflow_config: The configuration object for the workflow

    Returns:
        A tuple containing (APIRouter, WorkflowClass, WorkflowEvent, WorkflowInitializer)

    Raises:
        ImportError: If the module cannot be imported
        AttributeError: If required attributes are missing from the module
    """
    try:
        # Import the workflow module dynamically
        module_path = workflow_config.code_path
        workflow_module = importlib.import_module(module_path)

        # Extract the FastAPI router - look for 'router' attribute
        router: Optional[APIRouter] = None
        if hasattr(workflow_module, 'router') and isinstance(workflow_module.router, APIRouter):
            router = workflow_module.router
        else:
            # Try common naming patterns
            for attr_name in dir(workflow_module):
                attr = getattr(workflow_module, attr_name)
                if isinstance(attr, APIRouter):
                    router = attr
                    break

        if router is None:
            raise AttributeError(f"No APIRouter found in module {module_path}")

        # Extract the main workflow class
        main_workflow_class: Optional[WorkflowClass] = None
        for attr_name in dir(workflow_module):
            attr = getattr(workflow_module, attr_name)
            if (inspect.isclass(attr) and issubclass(attr, ABC) and attr != ABC and
                hasattr(attr, 'run')):  # Assume workflow classes implement 'run' method
                if 'workflow' in attr_name.lower() or attr_name.endswith('Workflow'):
                    main_workflow_class = attr
                    break

        if main_workflow_class is None:
            main_workflow_class = None

        # Extract the event class
        event_class: Optional[WorkflowEvent] = None
        for attr_name in dir(workflow_module):
            attr = getattr(workflow_module, attr_name)
            if inspect.isclass(attr) and attr != ABC:
                if 'event' in attr_name.lower() or attr_name.endswith('Event'):
                    event_class = attr
                    break

        if event_class is None:
            logger.warning(f"No event class found in {module_path}, returning None for event class")
            event_class = None

        # Extract the workflow initializer class/method
        initializer: Optional[Type[Any]] = None
        for attr_name in dir(workflow_module):
            attr = getattr(workflow_module, attr_name)
            if inspect.isclass(attr) and hasattr(attr, 'initialize') and callable(getattr(attr, 'initialize')):
                if 'initializer' in attr_name.lower() or attr_name.endswith('Initializer'):
                    initializer = attr
                    break
        
        if initializer is None:
            logger.debug(f"No specific initializer found for workflow '{workflow_id}' in '{module_path}'. Using generic initialization.")

        return router, main_workflow_class, event_class, initializer

    except ImportError as e:
        logger.error(f"Failed to import workflow module '{workflow_config.code_path}': {e}")
        raise ImportError(f"Could not load workflow '{workflow_id}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading workflow '{workflow_id}': {e}")
        raise


def load_all_workflows() -> Dict[str, Tuple[APIRouter, Optional[WorkflowClass], Optional[WorkflowEvent], Optional[Type[Any]]]]:
    """
    Load all configured workflows from the system configuration.

    Returns:
        A dictionary mapping workflow IDs to (router, workflow_class, event_class, initializer) tuples
    """

    workflow_configs = get_all_workflow_configs()
    loaded_workflows = {}

    for workflow_id, workflow_config in workflow_configs.items():
        try:
            # load_workflow_module now returns 4 items
            router, workflow_class, event_class, initializer = load_workflow_module(workflow_id, workflow_config)
            loaded_workflows[workflow_id] = (router, workflow_class, event_class, initializer)
        except Exception as e:
            logger.error(f"Failed to load workflow '{workflow_id}': {e}")
            # Continue loading other workflows even if one fails
            continue

    logger.info(f"Loaded {len(loaded_workflows)} out of {len(workflow_configs)} configured workflows")
    return loaded_workflows


def get_workflow_factory_function(workflow_name: str):
    """
    Get the workflow factory function for a given workflow name.

    This function provides backward compatibility for code that expects
    a separate factory function getter.

    Args:
        workflow_name: The workflow identifier (e.g., 'A_agentic_rag')

    Returns:
        The workflow factory function from the WorkflowConfig
    """
    workflow_config = get_workflow_config(workflow_name)
    return workflow_config.workflow_factory


def reload_workflow(workflow_id: str, workflow_config: WorkflowConfig) -> Tuple[APIRouter, Optional[WorkflowClass], Optional[WorkflowEvent], Optional[Type[Any]]]:
    """
    Reload a specific workflow, useful for development or configuration updates.

    Args:
        workflow_id: The workflow to reload
        workflow_config: The updated configuration

    Returns:
        The reloaded workflow components
    """

    # Clear module from cache to force reload
    if workflow_config.code_path in sys.modules:
        importlib.reload(sys.modules[workflow_config.code_path])

    return load_workflow_module(workflow_id, workflow_config)
