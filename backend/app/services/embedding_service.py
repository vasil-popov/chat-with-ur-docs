import logging
import os
from typing import Optional

from langchain_community.vectorstores import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

COLLECTION_NAME = "life_os_docs"
_vectorstore: Optional[PGVector] = None


def _get_connection_string() -> str:
    user = os.getenv("POSTGRE_USER")
    password = os.getenv("POSTGRE_PASS")
    host = os.getenv("POSTGRE_IP", "localhost")
    port = os.getenv("POSTGRE_PORT", "5432")
    db = os.getenv("POSTGRE_DB_NAME")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_vectorstore() -> PGVector:
    global _vectorstore
    if _vectorstore is None:
        embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
        _vectorstore = PGVector(
            collection_name=COLLECTION_NAME,
            connection_string=_get_connection_string(),
            embedding_function=embeddings,
        )
        logger.info("PGVector vectorstore initialized (collection: %s)", COLLECTION_NAME)
    return _vectorstore


def embed_file(file_id: str, file_name: str, text: str) -> int:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_text(text)
    if not chunks:
        return 0

    from langchain_core.documents import Document
    docs = [
        Document(page_content=chunk, metadata={"file_id": file_id, "file_name": file_name})
        for chunk in chunks
    ]
    vs = get_vectorstore()
    vs.add_documents(docs)
    logger.info("Embedded %d chunks for file %s", len(chunks), file_id)
    return len(chunks)


def search(query: str, file_ids: Optional[list[str]] = None, k: int = 5) -> list:
    vs = get_vectorstore()
    if file_ids:
        results = vs.similarity_search_with_score(
            query, k=k, filter={"file_id": {"$in": file_ids}}
        )
    else:
        results = vs.similarity_search_with_score(query, k=k)
    return results


def delete_file_embeddings(file_id: str) -> None:
    vs = get_vectorstore()
    try:
        vs.delete(filter={"file_id": file_id})
        logger.info("Deleted embeddings for file %s", file_id)
    except Exception as e:
        logger.warning("Could not delete embeddings for %s: %s", file_id, e)
