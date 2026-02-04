
import logging
import os
import sys

# Mock enough of the project to get config_manager
project_root = "/home/bernard/workspace/prajna_AI/prajna-stadium/vibe-coding"
sys.path.append(project_root)

from super_starter_suite.shared.config_manager import config_manager

def list_all_loggers():
    print("--- Current Logger Levels from config ---")
    loggers = logging.Logger.manager.loggerDict
    for name, logger in sorted(loggers.items()):
        if isinstance(logger, logging.Logger):
            print(f"Logger: {name}, Level: {logging.getLevelName(logger.level)}, Effective Level: {logging.getLevelName(logger.getEffectiveLevel())}")

if __name__ == "__main__":
    # Ensure logging is configured
    config_manager.configure_logging()
    
    print("--- Active loggers after configuration ---")
    list_all_loggers()
    
    # Try to find which one might produce the message
    print("\n--- Identifying potential loggers for HTTP Request: POST ---")
    libs = ['httpx', 'requests', 'urllib3']
    for lib in libs:
        logger = logging.getLogger(lib)
        print(f"Logger: {lib}, Level: {logging.getLevelName(logger.level)}, Effective Level: {logging.getLevelName(logger.getEffectiveLevel())}")

    external_http_enabled = config_manager.system_config.get('LOGGING', {}).get('EXTERNAL_HTTP_LOG', False)
    print(f"\nEXTERNAL_HTTP_LOG is set to: {external_http_enabled}")
    
    if not external_http_enabled:
        all_warnings = all(logging.getLogger(lib).getEffectiveLevel() >= logging.WARNING for lib in libs)
        if all_warnings:
            print("SUCCESS: Noisy HTTP loggers are correctly silenced (>= WARNING).")
        else:
            print("FAILURE: Some noisy HTTP loggers are NOT silenced.")
    else:
        print("INFO: EXTERNAL_HTTP_LOG is enabled, so noisy logs may appear.")
