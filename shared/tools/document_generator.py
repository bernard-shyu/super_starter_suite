import logging
import os
import re
import base64
from enum import Enum
from io import BytesIO
from typing import Optional

from llama_index.core.tools.function_tool import FunctionTool
from llama_index.server.settings import server_settings

logger = logging.getLogger("uvicorn")

DEFAULT_OUTPUT_DIR = "output/tools"

class DocumentType(Enum):
    PDF = "pdf"
    HTML = "html"

COMMON_STYLES = """
body {
    font-family: Arial, sans-serif;
    line-height: 1.3;
    color: #333;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 1em;
    margin-bottom: 0.5em;
}
p {
    margin-bottom: 0.7em;
}
code {
    background-color: #f4f4f4;
    padding: 2px 4px;
    border-radius: 4px;
}
pre {
    background-color: #f4f4f4;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 1em;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}
th {
    background-color: #f2f2f2;
    font-weight: bold;
}
"""

HTML_SPECIFIC_STYLES = """
body {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}
"""

PDF_SPECIFIC_STYLES = """
@page {
    size: letter;
    margin: 2cm;
}
body {
    font-size: 11pt;
}
h1 { font-size: 18pt; }
h2 { font-size: 16pt; }
h3 { font-size: 14pt; }
h4, h5, h6 { font-size: 12pt; }
pre, code {
    font-family: Courier, monospace;
    font-size: 0.9em;
}
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {common_styles}
        {specific_styles}
    </style>
</head>
<body>
    {content}
</body>
</html>
"""

class DocumentGenerator:
    """
    LOCAL PORT: Document generator with RAG-ROOT support and B64 padding fixes.
    """
    def __init__(self, file_server_url_prefix: str, output_dir: Optional[str] = None):
        if not file_server_url_prefix:
            raise ValueError("file_server_url_prefix is required")
        self.file_server_url_prefix = file_server_url_prefix
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR

    @classmethod
    def _fix_base64_padding(cls, content: str) -> str:
        """
        Fixes missing padding in data:image base64 strings to prevent xhtml2pdf errors.
        """
        def fix_match(match):
            prefix = match.group(1)
            b64_data = match.group(2)
            # Add padding if necessary
            missing_padding = len(b64_data) % 4
            if missing_padding:
                b64_data += '=' * (4 - missing_padding)
            return f'src="{prefix}{b64_data}"'

        # Regex to find src="data:image/...;base64,..."
        pattern = r'src="(data:image\/[^;]+;base64,)([^"]+)"'
        return re.sub(pattern, fix_match, content)

    @classmethod
    def _generate_html_content(cls, original_content: str) -> str:
        try:
            import markdown
        except ImportError:
            raise ImportError("Failed to import markdown. Please install it.")

        html = markdown.markdown(original_content, extensions=["fenced_code", "tables"])
        # FIX: Sanitize base64 padding in generated HTML
        return cls._fix_base64_padding(html)

    @classmethod
    def _generate_pdf(cls, html_content: str) -> BytesIO:
        try:
            from xhtml2pdf import pisa
        except ImportError:
            raise ImportError("Failed to import xhtml2pdf. Please install it.")

        pdf_html = HTML_TEMPLATE.format(
            common_styles=COMMON_STYLES,
            specific_styles=PDF_SPECIFIC_STYLES,
            content=html_content,
        )

        buffer = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(pdf_html.encode("UTF-8")), buffer, encoding="UTF-8"
        )

        if pdf.err:
            logger.error(f"PDF generation failed: {pdf.err}")
            raise ValueError("PDF generation failed")

        buffer.seek(0)
        return buffer

    @classmethod
    def _generate_html(cls, html_content: str) -> str:
        return HTML_TEMPLATE.format(
            common_styles=COMMON_STYLES,
            specific_styles=HTML_SPECIFIC_STYLES,
            content=html_content,
        )

    def generate_document(
        self, original_content: str, document_type: str, file_name: str
    ) -> str:
        """
        To generate document as PDF or HTML file.
        """
        try:
            doc_type = DocumentType(document_type.lower())
        except ValueError:
            raise ValueError(f"Invalid document type: {document_type}. Must be 'pdf' or 'html'.")
            
        html_content = self._generate_html_content(original_content)

        if doc_type == DocumentType.PDF:
            content = self._generate_pdf(html_content)
            file_extension = "pdf"
        elif doc_type == DocumentType.HTML:
            content = BytesIO(self._generate_html(html_content).encode("utf-8"))
            file_extension = "html"
        else:
            raise ValueError(f"Unexpected document type: {document_type}")

        file_name = self._validate_file_name(file_name)
        full_file_name = f"{file_name}.{file_extension}"
        file_path = os.path.join(self.output_dir, full_file_name)

        self._write_to_file(content, file_path)

        # Generate URL
        if "chat_history" in self.output_dir:
            parts = self.output_dir.split("chat_history")
            if len(parts) > 1:
                relative_path = "chat_history" + parts[1]
                return f"/api/files/{relative_path}/{full_file_name}".replace("//", "/")

        return f"{self.file_server_url_prefix}/{self.output_dir}/{full_file_name}".replace("//", "/")

    @staticmethod
    def _write_to_file(content: BytesIO, file_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as file:
                file.write(content.getvalue())
        except Exception as e:
            logger.error(f"Error writing document to {file_path}: {e}")
            raise

    @staticmethod
    def _validate_file_name(file_name: str) -> str:
        if os.path.isabs(file_name):
            raise ValueError("Absolute file name is not allowed.")
        # Remove any leading directory traversal or trailing extensions
        file_name = os.path.basename(file_name)
        file_name = os.path.splitext(file_name)[0]
        
        if re.match(r"^[a-zA-Z0-9_.-]+$", file_name):
            return file_name
        else:
            # Fallback sanitation
            return re.sub(r"[^a-zA-Z0-9_.-]", "_", file_name)

    @classmethod
    def _validate_packages(cls) -> None:
        try:
            import markdown
            import xhtml2pdf
        except ImportError:
            raise ImportError("Failed to import markdown and xhtml2pdf. Please install them.")

    def to_tool(self) -> FunctionTool:
        self._validate_packages()
        return FunctionTool.from_defaults(self.generate_document)
