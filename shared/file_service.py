import base64
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple, Union

from llama_index.server.models.file import ServerFile
from llama_index.server.settings import server_settings

logger = logging.getLogger("uvicorn")

PRIVATE_STORE_PATH = str(Path("output", "private"))


class FileService:
    """
    LOCAL PORT: Store files to server.
    This replaces the site-package version and allows for custom save directories 
    like the user's RAG-ROOT.
    """

    @classmethod
    def save_file(
        cls,
        content: Union[bytes, str],
        file_name: str,
        save_dir: Optional[str] = None,
    ) -> ServerFile:
        """
        Save the content to a file. Supports absolute paths for save_dir.
        """
        if save_dir is None:
            save_dir = PRIVATE_STORE_PATH

        file_id, extension = cls._process_file_name(file_name)
        
        # Ensure save_dir exists
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, file_id)

        # Write the file directly
        try:
            with open(file_path, "wb") as f:
                if isinstance(content, str):
                    f.write(content.encode())
                else:
                    f.write(content)
        except Exception as e:
            logger.error(f"Error when writing to file {file_path}: {e!s}")
            raise

        logger.info(f"Saved file to {file_path}")

        file_size = os.path.getsize(file_path)
        file_url = cls._get_file_url(file_id, save_dir)
        
        return ServerFile(
            id=file_id,
            type=extension,
            size=file_size,
            url=file_url,
            path=file_path,
        )

    @classmethod
    def _process_file_name(cls, file_name: str) -> tuple[str, str]:
        _id = str(uuid.uuid4())
        name, extension = os.path.splitext(file_name)
        extension = extension.lstrip(".")
        if extension == "":
            extension = "bin"
        # sanitize the name
        name = re.sub(r"[^a-zA-Z0-9.]", "_", name)
        file_id = f"{name}_{_id}.{extension}"
        return file_id, extension

    @classmethod
    def _get_file_url(cls, file_id: str, save_dir: Optional[str] = None) -> str:
        """
        Get the URL of a file. Handles RAG-ROOT paths specifically.
        """
        if save_dir is None:
            save_dir = PRIVATE_STORE_PATH
            
        # If it's a RAG-ROOT path (contains chat_history), we'll return a /api/files/ relative URL
        if "chat_history" in save_dir:
            parts = save_dir.split("chat_history")
            if len(parts) > 1:
                # /api/files/chat_history/P_financial_report/output/filename
                relative_path = "chat_history" + parts[1]
                return f"/api/files/{relative_path}/{file_id}".replace("//", "/")

        # Default fallback to site-package behavior
        url_path = f"{save_dir}/{file_id}".replace("\\", "/")
        return f"{server_settings.file_server_url_prefix}/{url_path}"

    @classmethod
    def get_file_path(cls, file_id: str, save_dir: Optional[str] = None) -> str:
        if save_dir is None:
            save_dir = PRIVATE_STORE_PATH
        return os.path.join(save_dir, file_id)

    @classmethod
    def get_file(cls, file_id: str, save_dir: Optional[str] = None) -> bytes:
        file_path = cls.get_file_path(file_id, save_dir)
        with open(file_path, "rb") as f:
            return f.read()
