from functools import wraps
from fastapi import Request, HTTPException
from .config_manager import config_manager
from .llama_utils import init_llm

# print("[DEBUG] bind_user_context decorator module loaded")

def bind_user_context(func):
    """
    Decorator to bind user context to FastAPI endpoints.
    Ensures user settings are loaded and available in the request state.
    Also initializes the LLM for the user.

    CRITICAL: In Python, decorators are applied from bottom to top.
    This decorator must be placed AFTER @router decorators to ensure FastAPI gets this decorated function beforehand.
    """
    # print(f"[PRINT] bind_user_context decorator applied to function: {func.__name__}")

    @wraps(func)
    async def context_bound_function(request: Request, *args, **kwargs):
        try:
            # print(f"[DEBUG] bind_user_context for FUNCTION: {func.__name__},  REQUEST: {request.method}, {request.url}")

            # Ensure user context is initialized
            user_id = getattr(request.state, 'user_id', 'Default')
            user_config = config_manager.get_user_config(user_id)
            request.state.user_config = user_config

            # CRITICAL: Always initialize LLM when decorator is called
            user_id = getattr(request.state, 'user_id', 'Default')
            user_config = request.state.user_config

            try:
                init_llm(user_config)
            except Exception as e:
                # Log error but don't fail the request - let endpoints handle LLM issues
                print(f"[ERROR] bind_user_context: Failed to initialize LLM for user {user_id}: {str(e)}")
                # print(f"  Exception type: {type(e).__name__}")
                # import traceback
                # print(f"  Exception traceback: {traceback.format_exc()}")

            # Verify settings are available
            if not hasattr(request.state, 'user_config'):
                raise HTTPException(
                    status_code=400,
                    detail="User context not available. Please ensure user is properly identified."
                )

            return await func(request, *args, **kwargs)
        except Exception as e:
            print(f"[ERROR] EXCEPTION in bind_user_context decorator: {str(e)}")
            # Re-raise the exception to not hide it
            raise

    return context_bound_function
