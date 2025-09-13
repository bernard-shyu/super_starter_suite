import sys, os, json, pprint
from llama_index.core import SimpleDirectoryReader, Settings, StorageContext, load_index_from_storage
from llama_index.core import VectorStoreIndex, SummaryIndex, TreeIndex, KeywordTableIndex

#from common.LLamaIndex_helper import load_llm
#Settings.llm = load_llm()          # Settings.llm = Ollama(model="llama3.1", request_timeout=360.0)

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")     # English: "BAAI/bge-large-en-v1.5" / "BAAI/bge-base-en",  multi-lingual: "BAAI/bge-m3" / "BAAI/bge-m3-retromae"

#=================================================================================
# A. VectorStoreIndex
#=================================================================================
def listIndex_ref_doc_info(storage_dir: str = "storage") -> None:
    global index
    if os.path.exists(f"{storage_dir}/docstore.json"):
        storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
        index = load_index_from_storage(storage_context)

        # Access reference document info from the index
        for doc_id, ref_info in index.ref_doc_info.items():
            print("\n" + "="*160, f"\nDoc ID: {doc_id}")
            print("Metadata:", ref_info.metadata)
            print("Node IDs:", ref_info.node_ids)

def listIndex_docstore_docs(storage_dir: str = "storage", text_len: int = 100) -> None:
    if os.path.exists(f"{storage_dir}/docstore.json"):
        storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
        index = load_index_from_storage(storage_context)

        # Accessing Nodes and Their Metadata
        for node_id, node in index.docstore.docs.items():
            print("\n" + "="*160, f"\nNode ID: {node_id}  \t mimetype: {node.mimetype}  start_char_idx: {node.start_char_idx}  end_char_idx: {node.end_char_idx}")
            print(f"Metadata: {node.metadata} \n")
            print(f"Text:", node.text[:text_len])

#=================================================================================
# storage backend && more advanced filtering
#=================================================================================
def _to_DO():
    #-------------------------------------------------------------------- 
    # 1. SimpleDocumentStore (Default In-Memory/Local Storage)
    #-------------------------------------------------------------------- 
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    # List all documents and their metadata
    for doc in documents:
        print(doc.text[:100], doc.metadata, doc.id_)

    # Advanced filtering: Only show docs with a specific author
    filtered_docs = [doc for doc in documents if doc.metadata.get("author") == "Alice"]
    for doc in filtered_docs:
        print(doc.text[:100], doc.metadata)


    #-------------------------------------------------------------------- 
    # 2. MongoDB Document Store
    #-------------------------------------------------------------------- 
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
    from llama_index.storage.docstore.mongodb import MongoDBDocumentStore

    docstore = MongoDBDocumentStore(uri="mongodb://localhost:27017", db_name="llama", namespace="docs")
    storage_context = StorageContext.from_defaults(docstore=docstore)
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    # List all documents and their metadata from MongoDB
    for doc_id, doc in docstore.docs.items():
        print(doc.text[:100], doc.metadata, doc.id_)

    # Advanced filtering: Only docs from 2024
    filtered = [doc for doc in docstore.docs.values() if doc.metadata.get("year") == 2024]
    for doc in filtered:
        print(doc.text[:100], doc.metadata)

    #-------------------------------------------------------------------- 
    # 3. Redis Document Store
    #-------------------------------------------------------------------- 
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
    from llama_index.storage.docstore.redis import RedisDocumentStore
    import redis

    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    docstore = RedisDocumentStore(redis_client, namespace="docs")
    storage_context = StorageContext.from_defaults(docstore=docstore)
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    # List all documents and their metadata from Redis
    for doc_id, doc in docstore.docs.items():
        print(doc.text[:100], doc.metadata, doc.id_)

    # Advanced filtering: Only docs with tag "finance"
    filtered = [doc for doc in docstore.docs.values() if doc.metadata.get("tag") == "finance"]
    for doc in filtered:
        print(doc.text[:100], doc.metadata)

    #-------------------------------------------------------------------- 
    # 4. Google Cloud Firestore Document Store
    #-------------------------------------------------------------------- 
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
    from llama_index.storage.docstore.firestore import FirestoreDocumentStore

    docstore = FirestoreDocumentStore(project="your-gcp-project", namespace="docs")
    storage_context = StorageContext.from_defaults(docstore=docstore)
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

    # List all documents and their metadata from Firestore
    for doc_id, doc in docstore.docs.items():
        print(doc.text[:100], doc.metadata, doc.id_)

    # Advanced filtering: Only docs with category "legal"
    filtered = [doc for doc in docstore.docs.values() if doc.metadata.get("category") == "legal"]
    for doc in filtered:
        print(doc.text[:100], doc.metadata)


    #-------------------------------------------------------------------- 
    # 5. Filtering at Query Time (VectorStoreIndex with MetadataFilters)
    #-------------------------------------------------------------------- 
    from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter

    filters = MetadataFilters(filters=[ExactMatchFilter(key="author", value="Alice")])
    query_engine = index.as_query_engine(filters=filters)
    response = query_engine.query("What did Alice write?")
    print(response)

storage_dir = "storage"
text_len = 100
if len(sys.argv) > 1:
    storage_dir = sys.argv[1] 
    if len(sys.argv) > 2:
        text_len = int(sys.argv[2])

#listIndex_ref_doc_info(storage_dir)
listIndex_docstore_docs(storage_dir, text_len)
