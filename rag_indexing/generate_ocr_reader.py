# Required package installations for all extractors:
#   pip install python-dotenv llama-index llama-index-core llama-index-readers-google google-cloud-vision
#   pip install easyocr pdf2image pytesseract pymupdf pillow
#   pip install llama-parse llama-index-llms-azure-inference llama-index-llms-nvidia google-gen
#   sudo apt-get install tesseract-ocr poppler-utils

import logging
import os, sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Union, Type, Any
from dotenv import load_dotenv

# Common Llama-index imports
from llama_index.core.settings import Settings
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document
from llama_index.core.llms import ChatMessage, ImageBlock, TextBlock

STORAGE_DIR = "storage"

# Unified logger setup - works for both standalone and library modes
try:
    from super_starter_suite.shared.config_manager import config_manager
    logger = config_manager.get_logger("gen_ocr")

    # Integrated mode: terminal_output.py is accessible, import stdout capture
    try:
        from .terminal_output import capture_stdout_output
    except ImportError:
        # Fallback if terminal_output.py import fails
        def capture_stdout_output(func, *args, **kwargs):
            """Transparent fallback - execute function without stdout capture."""
            return func(*args, **kwargs)

except ImportError:
    # Standalone mode: config_manager not available, use basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("uvicorn")

    # Standalone mode: define transparent stdout capture function
    def capture_stdout_output(func, *args, **kwargs):
        """Transparent fallback for standalone mode - execute without stdout capture."""
        return func(*args, **kwargs)

#-----------------------------------------------------------------------------------------------------------
# The prompt guides the model on what to do
OCR_PROMPT  = "Perform OCR on this image. Extract all Traditional Chinese and English characters exactly as they appear. "
OCR_PROMPT += "Generate output in Markdown format, adding additional headings or table over the raw text to give similar looks to the original image."
OCR_PROMPT += "For each table, add one TALBE-LOOKUP section, giving KEY = VALUE pairs for each cell in the table. The KEY format is: 'ROW_Header..COLUMN_Header', " + \
              "where ROW_Header is each rows's header at 1st column, and COLUMN_Header the column header at 1st row."



#===========================================================================================================================
def set_imageParser(parser: BaseReader) -> Dict[str, BaseReader]:
    return {
        ".jpg": parser,
        ".png": parser,
        ".jpeg": parser,
    }

#-----------------------------------------------------------------------------------------------------------
# --- Option 0: Llama-index default image reader ---
def get_file_extractor_Tesseract() -> Dict[str, BaseReader]:
    """
    Uses the default Llama-index ImageReader, which relies on Tesseract OCR.
    Setup: Requires Tesseract to be installed on your system.
    """
    from llama_index.readers.file import ImageReader
    
    logger.info("Using Extractor: Default ImageReader (Tesseract)")
    return set_imageParser(ImageReader(keep_image=True, parse_text=True))

#-----------------------------------------------------------------------------------------------------------
# --- Option 1: Google Cloud Vision API ---
def get_file_extractor_GoogleVision() -> Dict[str, BaseReader]:
    """
    Uses Google Cloud Vision, a powerful cloud-based OCR service.
    Setup:
    1. pip install llama-index-readers-google google-cloud-vision
    2. Enable 'Cloud Vision API' in your Google Cloud project.
    3. Set environment variable:
       export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
    """
    from llama_index.readers.google import GoogleVisionReader

    logger.info("Using Extractor: Google Vision Reader")
    return set_imageParser(GoogleVisionReader(language_hints=["zh-Hant", "en"]))   # Hinting for Traditional Chinese and English

#-----------------------------------------------------------------------------------------------------------
# --- Option 2: EasyOCR ---
# We need to create a custom reader class to wrap easyocr's functionality
class EasyOCRReader(BaseReader):
    """A custom reader for the easyocr library."""
    
    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initializes the reader.
        Args:
            languages (Optional[List[str]]): List of language codes (e.g., ['ch_tra', 'en']).
        """
        try:
            import easyocr
        except ImportError:
            raise ImportError("easyocr not installed. Please run: pip install easyocr")
            
        if languages is None:
            languages = ['ch_tra', 'en']
        
        logger.info(f"Initializing EasyOCR with languages: {languages}")
        self._reader = easyocr.Reader(languages)

    def load_data(self, file: Path, extra_info: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Loads data from an image file.
        Args:
            file (Path): Path to the image file.
            extra_info (Optional[Dict[str, Any]]): Additional metadata to include.
        """
        results = self._reader.readtext(str(file))
        # Concatenate all detected text blocks into a single string
        full_text = "\n".join([res[1] for res in results])
        logger.info(f"GEN_OCR:PROGRESS: EasyOCRReader process file: {str(file)} - Results: {len(results)} text blocks")

        return [Document(text=full_text, metadata=extra_info or {})]

def get_file_extractor_EasyOCR() -> Dict[str, BaseReader]:
    """
    Uses EasyOCR, a standalone deep learning-based OCR library.
    Setup:
    1. pip install easyocr
    2. The first run will download the necessary language models.
    """
    logger.info("Using Extractor: EasyOCR Reader")
    return set_imageParser(EasyOCRReader(languages=['ch_tra', 'en']))

#-----------------------------------------------------------------------------------------------------------
# --- Option 3: LlamaParse ---
# We need to create a custom reader class to wrap LlamaParse's functionality
class LlamaParseReader(BaseReader):
    """A custom reader that uses LlamaParse for document processing."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            from llama_parse import LlamaParse
        except ImportError as exc:
            raise ImportError("LlamaParse not installed. Please run: pip install llama-parse") from exc
        
        self.api_key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        if not self.api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set.")
        
        self.parser = LlamaParse(api_key=self.api_key)
    
    def load_data(self, file: Path, extra_info: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Process documents using LlamaParse."""
        documents = self.parser.load_data(str(file))
        logger.info(f"GEN_OCR:PROGRESS: LlamaParseReader process file: {str(file)} - Documents: {len(documents)}")
        return [
            Document(
                text=doc.text,
                metadata={
                    **(extra_info or {}),
                    **doc.metadata,
                    "source": str(file)
                }
            ) for doc in documents
        ]

def get_file_extractor_LlamaParse() -> Dict[str, BaseReader]:
    """Uses LlamaParse for document processing."""
    logger.info("Using Extractor: LlamaParse Reader")
    llama_parse_reader = LlamaParseReader()
    return {
        ".jpg":  llama_parse_reader,
        ".png":  llama_parse_reader,
        ".jpeg": llama_parse_reader,
        ".pdf":  llama_parse_reader,
        ".docx": llama_parse_reader,
        ".doc":  llama_parse_reader,
        ".pptx": llama_parse_reader,
        ".xlsx": llama_parse_reader,
    }

#===========================================================================================================================
# --- Common Mixins ---
class ImageProcessorMixin(ABC):
    """Mixin class providing common image processing functionality."""
    
    def _ensure_image_imports(self):
        """Ensure image-related imports are available."""
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError("Required image packages not found. Please run: pip install pillow") from exc
        
        self.Image = Image

    def _process_image_file(self, file: Path, extra_info: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Process a single image file."""
        self._ensure_image_imports()
        img = self.Image.open(file)
        logger.info(f"GEN_OCR:PROGRESS: AI-Parser process file ({file}). Image type: {type(img)}")
        ocr_text = self._process_image(img)
        logger.debug(f"Processed image with content length: {len(ocr_text)}")
        return [Document(text=ocr_text, metadata={
            **(extra_info or {}),
            "source": str(file)
        })]

    def _convert_image_to_base64(self, image):
        """Convert a PIL image to base64 encoded string."""
        from io import BytesIO
        import base64
        with BytesIO() as buffer:
            image.save(buffer, format='PNG')  # format=image.format or 'PNG')
            image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode('utf-8')    #return image_bytes # Return raw bytes
        
    @abstractmethod
    def _process_image(self, image) -> str:
        """Process a single image and return extracted text. Must be implemented by subclasses."""
        pass

#-----------------------------------------------------------------------------------------------------------
class PDFProcessorMixin(ABC):
    """Mixin class providing common PDF processing functionality."""
    
    def _ensure_pdf_imports(self):
        """Ensure PDF-related imports are available."""
        try:
            import pdf2image
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ImportError("Required packages not found. Please run: pip install pillow pdf2image pymupdf") from exc
        
        self.pdf2image = pdf2image
        self.fitz = fitz

    def _process_pdf_file(self, file: Path, extra_info: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Process PDF files with mixed content."""
        self._ensure_pdf_imports()
        doc = self.fitz.open(file)
        logger.info(f"GEN_OCR:PROGRESS: AI-Parser process file ({file}). Document Type: {type(doc)}  Pages: {len(doc)}")
        results = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            image_list = page.get_images()
            
            if image_list:  # If page contains images
                images = self.pdf2image.convert_from_path(str(file), first_page=page_num+1, last_page=page_num+1)
                logger.debug(f"PDF_FILE {file}  PAGE: {page_num+1} contains images. Types: {type(images[0])}")
                if images:
                    ocr_text = self._process_image(images[0])
                    combined_text = f"Page {page_num + 1}:\n{text}\nOCR Content:\n{ocr_text}"
                else:
                    combined_text = f"Page {page_num + 1}:\n{text}"
                logger.debug(f"GEN_OCR:PROGRESS: Processed page {page_num + 1} with content length: {len(combined_text)}")
            else:
                combined_text = f"Page {page_num + 1}:\n{text}"
            
            results.append(Document(text=combined_text, metadata={
                **(extra_info or {}),
                "page_num": page_num + 1,
                "source": str(file)
            }))

        logger.debug(f"GEN_OCR:PROGRESS: AI-Parser finished PDF file process. Pages: {len(doc)} Results: {len(results)}")
        return results

#-----------------------------------------------------------------------------------------------------------
# --- Base class for AI Vision OCR readers ---
class AIVisionOCRReader(BaseReader, PDFProcessorMixin, ImageProcessorMixin):
    """Base class for AI Vision OCR readers that handle both images and PDFs."""
    
    def __init__(self):
        self._ensure_image_imports()
        self.llm = None  # Will be set by child classes
    
    def _process_image(self, image) -> str:
        """Generic image processing using the configured LLM."""
        if self.llm is None:
            raise ValueError("LLM model not initialized. Child class must set self.llm")
            
        image_bytes = self._convert_image_to_base64(image) # Get raw bytes
        message = ChatMessage(blocks=[
            TextBlock(text=OCR_PROMPT),
            ImageBlock(image=image_bytes), # Pass raw bytes to ImageBlock
        ])
        response = self.llm.chat(messages=[message])
        logger.debug(f"_process_image: image: {type(image)} image_bytes: {type(image_bytes)}  response: {type(response)}")
        return response
    
    def load_data(self, file: Path, extra_info: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Common load_data implementation for both PDFs and images."""
        logger.info(f"GEN_OCR:PROGRESS: Google AIVision process file: {str(file)}")
        if file.suffix.lower() == '.pdf':
            return self._process_pdf_file(file, extra_info)
        else:
            return self._process_image_file(file, extra_info)

    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Return list of supported file formats."""
        return [".jpg", ".png", ".jpeg", ".pdf"]
    
    @classmethod
    def create_extractor(cls, **kwargs) -> Dict[str, BaseReader]:
        """Factory method to create file extractors."""
        reader = cls(**kwargs)
        return {fmt: reader for fmt in cls.get_supported_formats()}

#===========================================================================================================================
# --- Option 4: Google Gemini Multi-modal Model ---
# We need another custom reader class to wrap the Gemini API call
class GeminiVAIReader(AIVisionOCRReader):
    """Google Gemini implementation of AI Vision OCR reader."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = 'gemini-1.5-flash'):
        super().__init__()
        try:
            from llama_index.llms.google_genai import GoogleGenAI
        except ImportError as exc:
            raise ImportError("Required packages not found. Please run: pip install llama-index-llms-google-genai") from exc
        
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        
        self.llm = GoogleGenAI(model=model_name, api_key=api_key)

    @classmethod
    def create_extractor(cls, model_config: Optional[Dict] = None) -> Dict[str, BaseReader]:
        """Creates a Gemini Vision extractor."""
        logger.info("Using Extractor: Gemini Vision Reader")
        return super().create_extractor(
            model_name = 'gemini-1.5-flash' if not model_config['parser'] else model_config['parser'],
            **model_config['param'] 
        )

#-----------------------------------------------------------------------------------------------------------
# --- Option 5: Azure Multimodal ---
# We need to create a custom reader class to wrap Azure's multimodal capabilities
class AzureAIReader(AIVisionOCRReader):
    """Azure AI implementation of AI Vision OCR reader."""
    
    def __init__(self, model_name: Optional[str] = None, endpoint: Optional[str] = None, credential: Optional[str] = None):
        super().__init__()
        try:
            from llama_index.llms.azure_inference import AzureAICompletionsModel
        except ImportError as exc:
            raise ImportError("Required packages not found. Please run: pip install llama-index-llms-azure-inference") from exc
        
        endpoint = endpoint or os.getenv("AZURE_ENDPOINT", "https://models.github.ai/inference")
        credential = credential or os.getenv("GITHUB_TOKEN")
        
        if not credential:
            raise ValueError("GITHUB_TOKEN environment variable not set.")
        
        self.llm = AzureAICompletionsModel(
            model_name=model_name,
            endpoint=endpoint,
            credential=credential
        )

    @classmethod
    def create_extractor(cls, model_config: Optional[Dict] = None) -> Dict[str, BaseReader]:
        """Creates an Azure AI extractor."""
        logger.info("Using Extractor: Azure Multimodal Reader")
        return super().create_extractor(
            model_name = "openai/gpt-4.1" if not model_config['parser'] else model_config['parser'],
            **model_config['param'] 
        )

#-----------------------------------------------------------------------------------------------------------
# --- Option 6: Nvidia Multimodal ---
# We need to create a custom reader class to wrap NVIDIA's multimodal models
class NvidiaAIReader(AIVisionOCRReader):
    """NVIDIA implementation of AI Vision OCR reader."""
    
    def __init__(self, model_name: Optional[str] = None):
        super().__init__()
        try:
            from llama_index.llms.nvidia import NVIDIA
        except ImportError as exc:
            raise ImportError("Required packages not found. Please run: pip install llama-index-llms-nvidia") from exc
        
        self.llm = NVIDIA(
            model=model_name,
            api_key=os.getenv("NVIDIA_API_KEY"),
            is_chat_model=True,
            is_function_calling_model=False,
            timeout=float(os.getenv("MY_TIME_OUT", "120.0"))
        )

    @classmethod
    def create_extractor(cls, model_config: Optional[Dict] = None) -> Dict[str, BaseReader]:
        """Creates an NVIDIA AI extractor."""
        logger.info("Using Extractor: NVIDIA Multimodal Reader")
        return super().create_extractor(
            model_name = "meta/llama-3.3-70b-instruct" if not model_config['parser'] else model_config['parser'],
            **model_config['param'] 
        )

#===========================================================================================================
# --- How to use it in your `generate_index` function ---
def generate_index(extractor: str = "EasyOCR", model_config: Optional[Dict] = None):
    """
    Index the documents in the data directory.

    Parameters
    ----------
    extractor : str
        The OCR/extraction method to use.
    model_config : dict | None
        Optional model configuration dictionary for AI extractors.
    """
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

    # Separate AI model-based extractors from function-based ones
    AI_MODEL_EXTRACTORS = {
        "GeminiAI": GeminiVAIReader,
        "AzureAI": AzureAIReader,
        "NvidiaAI": NvidiaAIReader,
    }

    FUNCTION_EXTRACTORS = {
        "EasyOCR": get_file_extractor_EasyOCR,
        "Tesseract": get_file_extractor_Tesseract,
        "GoogleVision": get_file_extractor_GoogleVision,
        "LlamaParse": get_file_extractor_LlamaParse,
    }

    # First check AI model-based extractors
    if extractor in AI_MODEL_EXTRACTORS:
        extractor_class = AI_MODEL_EXTRACTORS[extractor]
        file_extractor = extractor_class.create_extractor(model_config=model_config)
    # Then check function-based extractors
    elif extractor in FUNCTION_EXTRACTORS:
        file_extractor = FUNCTION_EXTRACTORS[extractor]()
    else:
        raise ValueError(f"Unknown extractor: {extractor}")

    input_dir = os.environ.get("DATA_DIR", "data")
    logger.info("GEN_OCR:STATE: Start document parsing with extractor: %s for Data %s", extractor, input_dir[-60:])
    # load the documents and create the index
    reader = SimpleDirectoryReader(
        input_dir=input_dir,
        filename_as_id=True,
        file_extractor=file_extractor,
        #required_exts= [".md"],
        recursive=True,
    )
    documents = reader.load_data()

    logger.info("GEN_OCR:STATE: Start RAG index generating to Storage: %s", STORAGE_DIR[-60:])

    # THIN SHIM: Use stdout capture wrapper to handle TQDM progress bars
    def generate_rag_index():
        """Core RAG generation logic - kept clean and focused."""
        return VectorStoreIndex.from_documents(
            documents,
            show_progress=True,
        )

    # Wrap core generation with stdout capture to handle TQDM progress bars
    # In integrated mode: TQDM output gets captured and sent to UI
    # In standalone mode: TQDM output prints normally to console
    index = capture_stdout_output(generate_rag_index)

    # store it for later
    os.makedirs(STORAGE_DIR, exist_ok=True)
    index.storage_context.persist(STORAGE_DIR)
    logger.info("GEN_OCR:STATE: Finished RAG index generating. Stored in %s", STORAGE_DIR[-60:])

#-----------------------------------------------------------------------------------------------------------
def generate_ui_for_workflow():
    """
    Generate UI for UIEventData event in app/workflow.py
    """
    import asyncio
    from main import COMPONENT_DIR

    # To generate UI components for additional event types,
    # import the corresponding data model (e.g., MyCustomEventData)
    # and run the generate_ui_for_workflow function with the imported model.
    # Make sure the output filename of the generated UI component matches the event type (here `ui_event`)
    try:
        from app.workflow import UIEventData  # type: ignore
    except ImportError:
        raise ImportError("Couldn't generate UI component for the current workflow.")
    from llama_index.server.gen_ui import generate_event_component

    # works well with OpenAI gpt-4.1, Claude 3.7 Sonnet or Gemini Pro 2.5
    code = asyncio.run(
        generate_event_component(event_cls=UIEventData, llm=Settings.llm)
    )
    with open(f"{COMPONENT_DIR}/ui_event.jsx", "w") as f:
        f.write(code)

#===========================================================================================================================
def perform_rag_generation(
    extractor: str = "EasyOCR",
    user_rag_root: str = "",
    model_config: dict | None = None,
    data_path: str = "",
    storage_path: str = ""
):
    """
    Perform RAG index generation.

    Parameters
    ----------
    extractor : str
        The OCR/extraction method to use. Options include:
        "EasyOCR", "Tesseract", "GoogleVision", "LlamaParse",
        "GeminiAI", "AzureAI", "NvidiaAI".
    user_rag_root : str
        Base directory for the user's RAG data. If empty, defaults to the
        environment variable ``USER_RAG_ROOT`` or the current working directory.
    model_config : dict | None
        Optional model configuration dictionary. Currently unused but kept for
        compatibility with the caller.
    data_path : str
        Sub‑directory under ``user_rag_root`` where the source data lives.
        This is typically something like ``data.RAG`` or ``data.CODE_GEN``.
    storage_path : str
        Sub‑directory under ``user_rag_root`` where the storage data lives.
        This is typically something like ``storage.RAG`` or ``storage.CODE_GEN``.
    """
    global STORAGE_DIR

    # Load environment variables (e.g., API keys)
    load_dotenv()

    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")     # English: "BAAI/bge-base-en-v1.5" / "BAAI/bge-large-en-v1.5",  multi-lingual: "BAAI/bge-m3" / "BAAI/bge-m3-retromae"

    # Set environment variables for the generate_index function
    os.environ["DATA_DIR"] = data_path

    STORAGE_DIR = storage_path

    # Call the existing index generation helper
    logger.info("Starting RAG generation: extractor=%s, data_path=%s, storage_path=%s", extractor, data_path[-60:], storage_path[-40:])
    try:
        generate_index(extractor=extractor, model_config=model_config)
    except Exception as e:
        logger.error("RAG generation failed: %s", e)
        raise

#===========================================================================================================================
if __name__ == '__main__':
    from app.settings import init_settings
    load_dotenv()
    init_settings()

    # CHOOSE YOUR EXTRACTOR of OCR methods:  EasyOCR | LlamaParse | GeminiAI | AzureAI | NvidiaAI | Tesseract | GoogleVision
    extractor = os.getenv("OCR_READER", "EasyOCR")
    model_config   = { 
            'parser': os.getenv("OCR_LLM_MODEL", None),   # gemini-1.5-flash | microsoft/phi-3.5-vision-instruct
            'param':  {}
        }
 
    logger.info("Starting RAG generation: extractor=%s, ", extractor)
    generate_index(extractor=extractor, model_config=model_config)
