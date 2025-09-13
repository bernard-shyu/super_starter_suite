import toml
import os
import sys
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
import logging
from pathlib import Path

# UNIFIED LOGGING SYSTEM - Use config_manager after it's instantiated
# We'll use a placeholder logger for now and replace it after config_manager is created
temp_logger = logging.getLogger("sss.config")

# Path to configuration files
CONFIG_DIR = Path(__file__).parent.parent / "config"
SYSTEM_CONFIG_FILE = CONFIG_DIR / "system_config.toml"
USER_STATE_FILE = CONFIG_DIR / "user_state.toml"

def load_toml_config(file_path: Path) -> Dict:
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r") as f:
            return toml.load(f)
    except toml.decoder.TomlDecodeError as e:
        temp_logger.error(f"Error loading TOML config {file_path.name}: {e}")
        return {}

def save_toml_config(file_path: Path, config: Dict):
    """Save configuration to TOML file with structure preservation."""
    try:
        with open(file_path, "w") as f:
            toml.dump(config, f)

        # Validate the saved file by loading it back
        saved_config = load_toml_config(file_path)
        if saved_config != config:
            temp_logger.warning(f"TOML structure may have changed during save for {file_path.name}")
            # Log the differences for debugging
            import json
            temp_logger.debug(f"Original config keys: {set(config.keys())}")
            temp_logger.debug(f"Saved config keys: {set(saved_config.keys())}")
    except Exception as e:
        temp_logger.error(f"Error saving TOML config to {file_path}: {e}")
        raise

class ConfigManager:
    """
    Purpose: Manages the loading, saving, and merging of configuration data from various sources.

    Responsibilities:
    - Loads system-wide configuration from system_config.toml.
    - Loads user-specific settings from settings.<USER-ID>.toml.
    - Manages user state information from user_state.toml.
    - Provides methods to get merged configuration data for a specific user.
    - Handles the association of user IDs with IP addresses.
    """

    def __init__(self):
        """Initialize the ConfigManager with system configuration and user state."""
        self.system_config = load_toml_config(SYSTEM_CONFIG_FILE)
        self.user_state = load_toml_config(USER_STATE_FILE)
        if "USER_MAPPING" not in self.user_state:
            self.user_state["USER_MAPPING"] = {}
        if 'CURR_WORKFLOW' not in self.user_state:
            self.user_state['CURR_WORKFLOW'] = {}
        self._user_configs = {}

        # Add new methods for direct system config access
        self.load_system_config = lambda: self.system_config.copy()
        self.save_system_config = self._save_system_config

        # Configure logging based on system config
        self.configure_logging()

    def get_user_id(self, ip_address: str) -> str:
        """Get the user ID associated with an IP address.

        Args:
            ip_address: The IP address to look up

        Returns:
            The associated user ID or "Default" if not found
        """
        return self.user_state["USER_MAPPING"].get(ip_address, "Default")

    def associate_user_ip(self, ip_address: str, user_id: str):
        """Associate a user ID with an IP address.

        Args:
            ip_address: The IP address to associate
            user_id: The user ID to associate with the IP
        """
        self.user_state["USER_MAPPING"][ip_address] = user_id
        save_toml_config(USER_STATE_FILE, self.user_state)

    def get_user_workflow(self, user_id: str) -> str:
        """Get the current workflow for a user.

        Args:
            user_id: The user ID to get the workflow for

        Returns:
            The current workflow name or "agentic_rag" if not found
        """
        return self.user_state["CURR_WORKFLOW"].get(user_id, "agentic_rag")

    def update_user_workflow(self, user_id: str, workflow: str):
        """Update the current workflow for a user.

        Args:
            user_id: The user ID to update
            workflow: The new workflow name
        """
        self.user_state['CURR_WORKFLOW'][user_id] = workflow
        save_toml_config(USER_STATE_FILE, self.user_state)

    def load_user_settings(self, user_id: str) -> Dict:
        """Load user settings from the TOML file without merging with system config.

        Args:
            user_id: The user ID to load settings for

        Returns:
            Dictionary containing the raw user settings from the TOML file
        """
        settings_file = CONFIG_DIR / f"settings.{user_id}.toml"
        return load_toml_config(settings_file)

    def save_user_settings(self, user_id: str, settings: Dict):
        """Save user settings to the TOML file and clear the cached UserConfig.

        Args:
            user_id: The user ID to save settings for
            settings: Dictionary containing the settings to save
        """
        settings_file = CONFIG_DIR / f"settings.{user_id}.toml"
        save_toml_config(settings_file, settings)

        # Clear the cached UserConfig for this user to force reload
        if user_id in self._user_configs:
            del self._user_configs[user_id]

    def get_merged_config(self, user_id: str) -> Dict:
        """Get merged configuration for a user (system + user settings).

        Args:
            user_id: The user ID to get merged config for

        Returns:
            Dictionary containing the merged configuration
        """
        user_settings = self.load_user_settings(user_id)
        # Deep merge system_config and user_settings, with user_settings overriding system_config
        merged_config = self.system_config.copy()
        for key, value in user_settings.items():
            if isinstance(value, dict) and key in merged_config and isinstance(merged_config[key], dict):
                merged_config[key].update(value)
            else:
                merged_config[key] = value
        return merged_config

    def reload_user_state(self):
        """Reload the user state from the TOML file."""
        self.user_state = load_toml_config(USER_STATE_FILE)

    def get_user_config(self, user_id: str) -> 'UserConfig':
        """Get a UserConfig instance for the specified user.

        Args:
            user_id: The user ID to get the config for

        Returns:
            UserConfig instance containing the merged configuration
        """
        if user_id not in self._user_configs:
            self._user_configs[user_id] = UserConfig(user_id)
        return self._user_configs[user_id]

    def get_available_themes(self) -> list:
        """Get the list of available themes from system configuration.

        Returns:
            List of available theme names
        """
        return self.system_config.get("SYSTEM", {}).get("AVAILABLE_THEMES", [])

    def get_user_theme(self, user_id: str) -> str:
        """Get the current theme preference for a user.

        Args:
            user_id: The user ID to get the theme for

        Returns:
            The user's current theme name
        """
        user_settings = self.load_user_settings(user_id)
        return user_settings.get("USER_PREFERENCES", {}).get("THEME", "light_classic")

    def update_user_theme(self, user_id: str, theme: str):
        """Update the theme preference for a user.

        Args:
            user_id: The user ID to update
            theme: The new theme name (format: {color}_{style})
        """
        # Validate theme is in available themes
        available_themes = self.get_available_themes()
        if theme not in available_themes:
            raise ValueError(f"Theme '{theme}' is not in available themes: {available_themes}")

        user_settings = self.load_user_settings(user_id)
        if "USER_PREFERENCES" not in user_settings:
            user_settings["USER_PREFERENCES"] = {}
        user_settings["USER_PREFERENCES"]["THEME"] = theme
        self.save_user_settings(user_id, user_settings)

    def parse_theme(self, theme: str) -> tuple:
        """Parse a theme name into its color and style components.

        Args:
            theme: Theme name in format {color}_{style}

        Returns:
            Tuple of (color, style)
        """
        if "_" not in theme:
            raise ValueError(f"Invalid theme format: {theme}. Expected format: color_style")
        color, style = theme.split("_", 1)
        return color, style

    def configure_logging(self):
        """Configure global logging based on system configuration.

        This method should be called early in application startup to configure
        logging levels and component-specific loggers based on the LOGGING
        section in system_config.toml.
        """

        # Prevent multiple configurations
        if hasattr(self, '_logging_configured'):
            return
        self._logging_configured = True

        try:
            logging_config = self.system_config.get('LOGGING', {})

            # Set the root logger level
            log_level = logging_config.get('LEVEL', 20)  # Default to INFO
            logging.getLogger().setLevel(log_level)

            # Configure component-specific loggers
            components = {
                'websocket': logging_config.get('WEBSOCKET_LOG', True),
                'generation': logging_config.get('GENERATION_LOG', True),
                'api': logging_config.get('API_LOG', True),
                'cache': logging_config.get('CACHE_LOG', False)
            }

            for component, enabled in components.items():
                logger = logging.getLogger(f"sss.{component}")
                if enabled:
                    logger.setLevel(log_level)
                    logger.propagate = True  # Allow propagation to root logger
                else:
                    logger.setLevel(logging.WARNING)  # Only show warnings/errors
                    logger.propagate = True

            # Configure component-specific levels (overrides global level)
            component_levels = logging_config.get('COMPONENT_LEVELS', {})
            for component_name, level in component_levels.items():
                logger = logging.getLogger(component_name)
                logger.setLevel(level)
                logger.propagate = True

            # Configure uvicorn logger to match our level
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_logger.setLevel(log_level)

            # Completely disable uvicorn.error logger to prevent duplicate messages
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.setLevel(logging.CRITICAL)  # Only show CRITICAL messages
            uvicorn_error_logger.propagate = False
            # Add NullHandler to prevent any output from this logger
            if not uvicorn_error_logger.handlers:
                uvicorn_error_logger.addHandler(logging.NullHandler())

            # Configure colorful logging if enabled
            colors_enabled = logging_config.get('COLORS_ENABLED', True)
            if colors_enabled and self._supports_color():
                # Set up colorful formatter for console output
                console_handler = logging.StreamHandler()
                console_handler.setLevel(log_level)

                # Simple ANSI color formatter
                color_scheme = logging_config.get('COLOR_SCHEME', 'uvicorn')
                formatter = self._get_color_formatter(color_scheme)
                console_handler.setFormatter(formatter)

                # Add to root logger if not already present
                root_logger = logging.getLogger()
                if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
                    root_logger.addHandler(console_handler)

            temp_logger.info(f"Logging configured - Level: {log_level}, Components: {components}, Component Levels: {component_levels}, Colors: {colors_enabled}")

        except Exception as e:
            temp_logger.error(f"Failed to configure logging: {e}")
            # Fallback to basic logging
            logging.basicConfig(level=logging.INFO)

    def _supports_color(self):
        """Check if terminal supports ANSI colors."""
        if os.environ.get('NO_COLOR'):
            return False
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
        term = os.environ.get('TERM', '').lower()
        return term not in ('dumb', 'unknown') and any(t in term for t in ['xterm', 'screen', 'ansi', 'color', 'linux'])

    def _get_color_formatter(self, scheme='uvicorn'):
        """Get a simple color formatter with custom format."""
        colors = {
            'DEBUG': '\x1b[36m',     # Cyan
            'INFO': '\x1b[32m',      # Green (changed from white: '\x1b[37m')
            'WARNING': '\x1b[33m',   # Yellow
            'ERROR': '\x1b[31m',     # Red
            'CRITICAL': '\x1b[91m',  # Bright Red
        }
        reset = '\x1b[0m'

        class SimpleColorFormatter(logging.Formatter):
            def format(self, record):
                level_color = colors.get(record.levelname, colors['INFO'])
                # Format: LEVEL: HH:MM:SS,MS message
                # Pad level name to 8 characters for alignment
                padded_level = f"{record.levelname:<8}"
                colored_level = f"{level_color}{padded_level}{reset}"
                # Get time only (HH:MM:SS,MS)
                time_str = self.formatTime(record, "%H:%M:%S,%f")[:-3]  # Remove microseconds precision
                return f"{colored_level} {time_str} {record.getMessage()}"

        return SimpleColorFormatter()

    def get_logger(self, component: str) -> logging.Logger:
        """Get a configured logger for a specific component.

        UNIFIED LOGGING SYSTEM:
        This method provides standardized logging across the Super Starter Suite.
        All components should use this method instead of logging.getLogger() directly.

        Args:
            component: Component name (e.g., "gen_index", "config", "main")

        Returns:
            Configured logger instance with sss.{component} naming
        """
        return logging.getLogger(f"sss.{component}")

    def is_component_logging_enabled(self, component: str) -> bool:
        """Check if logging is enabled for a specific component.

        Args:
            component: Component name

        Returns:
            True if component logging is enabled
        """
        logging_config = self.system_config.get('LOGGING', {})
        component_key = f"{component.upper()}_LOG"
        return logging_config.get(component_key, False)

    def _save_system_config(self, config: Dict):
        """Save system configuration to the TOML file.

        Args:
            config: Dictionary containing the system configuration to save
        """
        save_toml_config(SYSTEM_CONFIG_FILE, config)
        self.system_config = config.copy()

config_manager = ConfigManager()

class UserRAGIndex:
    def __init__(self, my_config,  rag_type: str, rag_root: str, generate_method: str):
        self.my_config = my_config
        self.generate_method = generate_method
        self.rag_root = rag_root

        if generate_method in [ "EasyOCR", "LlamaParse" ]:
            self.model_config = {}
            self.storage_suffix = f"{generate_method}"
        else:
            # For system config AI methods, use flat structure
            selected_model_key  = f"{generate_method}_SELECTED_MODEL"
            model_parser        = my_config.get_user_setting(f"GENERATE_AI_METHOD.{selected_model_key}", "")
            self.model_config   = { 
                    'parser': model_parser,
                    'param':  my_config.get_user_setting(f"MODEL_PARAMETERS.AI_PARSER_PARAMS", {})
                }
            self.storage_suffix = f"{generate_method}.{model_parser.replace('/', '--')}"

        self.set_rag_type(rag_type)

    def set_rag_type(self, rag_type: str):
        self.rag_type     = rag_type
        self.data_path    = os.path.join(self.rag_root, f"data.{rag_type}")
        self.storage_path = os.path.join(self.rag_root, f"storage.{rag_type}", self.storage_suffix)

    def sanity_check(self):
        # Perform sanity checks specific to RAG workflows
        # Check rag_type if in USER_PREFERENCES.RAG_TYPES
        rag_types = self.my_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
        if rag_types and self.rag_type not in rag_types:
            return f"RAG type {self.rag_type} not defined"

        # Check generate_method if not provided, using the user's current workflow
        generate_methods = self.my_config.get_user_setting("SYSTEM.GENERATE_METHODS", [])
        if generate_methods and self.generate_method not in generate_methods:
            return f"Generate Method {self.generate_method} not defined"

        # Determine data_path is valid path
        if not os.path.exists(self.data_path):
            return f"Data path {self.data_path} is not valid"

        # Check if RAG root directory exists and is writable
        if not os.path.exists(self.rag_root):
            return f"RAG root directory {self.rag_root} does not exist"
        if not os.access(self.rag_root, os.W_OK):
            return f"RAG root directory {self.rag_root} is not writable"

        return None
    
class UserConfig:
    """
    Purpose: Represents the configuration data specific to a user, encapsulating all necessary configuration details for a user's session.

    Responsibilities:
    - Initializes with a user ID and a reference to the ConfigManager.
    - Loads and merges system configuration, user settings, and runtime configuration data.
    - Provides properties to access specific configuration details required for RAG index generation.
    - Updates runtime configuration based on user interactions (e.g., workflow selection).
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.my_user_setting = {}  # Maintain user-specific settings here
        self._load_configs()

    def _load_configs(self):
        # Load system config, user settings, and runtime config
        self.my_user_setting = config_manager.get_merged_config(self.user_id)

        # Load CURR_WORKFLOW entry for this user from the user state file
        self.my_workflow = config_manager.get_user_workflow(self.user_id)

        RAG_TYPE = self.get_user_setting(f"WORKFLOW_RAG_TYPE.{self.my_workflow}", "RAG")
        rag_root = self.get_user_setting("USER_PREFERENCES.USER_RAG_ROOT", "default_rag_root")
        generate_method = self.get_user_setting("GENERATE.METHOD", "LlamaParse")

        self.my_rag = UserRAGIndex(
            my_config       = self,
            rag_type        = RAG_TYPE,
            rag_root        = rag_root,
            generate_method = generate_method,
        )
        # Reduced verbosity - only log on first load or when config changes
        if not hasattr(self, '_config_logged'):
            config_manager.get_logger("config").debug(f"UserConfig::  USER={self.user_id}  WORKFLOW={self.my_workflow}  RAG_TYPE={RAG_TYPE}  METHOD={generate_method}")
            self._config_logged = True

    def update_runtime_config(self, workflow: str):
        config_manager.update_user_workflow(self.user_id, workflow)
        self._load_configs()

    def get_user_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a specific user setting from the loaded settings.

        This is the ONLY function that should be used to access user settings throughout the application.

        Args:
            key: The setting key to retrieve, using dot notation for nested keys
            default: The default value to return if the key is not found

        Returns:
            The value of the setting, or the default if not found

        Raises:
            RuntimeError: If user settings haven't been loaded yet
            ValueError: If the key is empty or invalid

        Examples:
            # Get a top-level setting
            value = self.get_user_setting("USER_RAG_ROOT")

            # Get a nested setting
            value = self.get_user_setting("USER_PREFERENCES.USER_RAG_ROOT")

            # Get a setting with default value
            value = self.get_user_setting("OPTIONAL_SETTING", "default_value")
        """
        if not key:
            raise ValueError("Setting key cannot be empty")

        if self.my_user_setting is None:
            raise RuntimeError("User settings not loaded. Call load_user_setting() first.")

        keys = key.split('.')
        value: Any = self.my_user_setting

        for k in keys:
            if not isinstance(value, dict):
                return default
            if k not in value:
                return default
            value = value[k]

        return value
