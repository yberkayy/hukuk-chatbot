import logging
from functools import lru_cache

from langchain_chroma import Chroma

from app.config import ensure_directories, settings
from app.embeddings import get_embeddings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    ensure_directories()
    logger.info('Initializing Chroma vector store at %s', settings.CHROMA_DB_DIR)
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=settings.CHROMA_DB_DIR,
    )
