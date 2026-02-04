import os

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from common.LLamaIndex_helper import load_llm

def init_settings_OpenAI():
    if os.getenv("OPENAI_API_KEY") is None:
        raise RuntimeError("OPENAI_API_KEY is missing in environment variables")
    Settings.llm = OpenAI(model=os.getenv("MODEL") or "gpt-4.1")
    Settings.embed_model = OpenAIEmbedding(
        model=os.getenv("EMBEDDING_MODEL") or "text-embedding-3-large"
    )

def init_settings():
    Settings.llm = load_llm()
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")     # English: "BAAI/bge-base-en-v1.5" / "BAAI/bge-large-en-v1.5",  multi-lingual: "BAAI/bge-m3" / "BAAI/bge-m3-retromae"

