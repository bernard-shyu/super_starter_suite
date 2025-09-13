"""
Test script for verifying USER_RAG_ROOT configuration loading.

This script loads the user settings for the "Bernard" user, prints the
USER_RAG_ROOT and GENERATE.METHOD values, and attempts to retrieve a
RAG index using the get_rag_index helper. It is intended for manual
execution in the project's conda environment (ai8) to confirm that the
settings are correctly loaded and that get_rag_index no longer raises an
error.
"""

from super_starter_suite.shared.config_manager import load_user_setting, get_user_setting
from super_starter_suite.shared.llama_utils import get_rag_index

def main():
    # Load settings for Bernard user
    load_user_setting('Bernard')

    # Display key settings
    print('USER_RAG_ROOT:', get_user_setting('USER_PREFERENCES.USER_RAG_ROOT'))
    print('GENERATE.METHOD:', get_user_setting('GENERATE.METHOD'))

    # Attempt to retrieve the RAG index (may be None if not generated yet)
    index = get_rag_index('RAG')
    print('RAG index loaded:', index is not None)

if __name__ == '__main__':
    main()
