"""
Yargıtay Decision Ingestion Script
====================================
Ingests Yargıtay decision text files into a separate ChromaDB collection.
Supports resume (skips already-indexed documents) and batch processing.

Usage:
    python ingest_yargitay.py                # Full ingestion with LLM extraction
    python ingest_yargitay.py --no-llm       # Regex-only extraction (faster, no API cost)
"""
import hashlib
import logging
import sys

from app.config import ensure_directories, settings
from app.yargitay_loader import load_yargitay_documents
from app.yargitay_vector_store import get_yargitay_vector_store

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
)
logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 64


def build_chunk_id(source: str, content: str) -> str:
    """Generate a deterministic ID for deduplication."""
    content_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()[:20]
    source_hash = hashlib.sha1(source.encode('utf-8')).hexdigest()[:12]
    return f'yargitay:{source_hash}:{content_hash}'


def _get_existing_ids(vector_store, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    try:
        existing = vector_store.get(ids=ids, include=['metadatas'])
        return set(existing.get('ids') or [])
    except Exception:
        return set()


def ingest_yargitay(use_llm: bool = True) -> None:
    ensure_directories()

    logger.info('Loading Yargıtay decisions (use_llm=%s)...', use_llm)
    documents = load_yargitay_documents(use_llm=use_llm)

    if not documents:
        logger.warning('No documents to ingest.')
        return

    vector_store = get_yargitay_vector_store()

    # Check existing count
    collection = getattr(vector_store, '_collection', None)
    existing_count = int(collection.count()) if collection and hasattr(collection, 'count') else 0
    logger.info('Existing Yargıtay embeddings: %s', existing_count)

    # Generate IDs for all documents
    chunk_ids = [
        build_chunk_id(
            source=doc.metadata.get('source', 'unknown'),
            content=doc.page_content,
        )
        for doc in documents
    ]

    total_added = 0

    for start in range(0, len(documents), UPSERT_BATCH_SIZE):
        end = min(start + UPSERT_BATCH_SIZE, len(documents))
        batch_docs = documents[start:end]
        batch_ids = chunk_ids[start:end]

        # Check for duplicates
        existing_ids = _get_existing_ids(vector_store, batch_ids)

        new_docs = []
        new_ids = []
        for doc, doc_id in zip(batch_docs, batch_ids):
            if doc_id not in existing_ids:
                new_docs.append(doc)
                new_ids.append(doc_id)

        if new_docs:
            try:
                vector_store.add_documents(documents=new_docs, ids=new_ids)
                total_added += len(new_docs)
            except Exception:
                logger.exception('Failed to index batch %s-%s', start, end)

        logger.info(
            'Batch %s-%s: %s processed, %s new, %s skipped',
            start + 1, end, len(batch_docs), len(new_docs), len(batch_docs) - len(new_docs),
        )

    # Final count
    final_count = int(collection.count()) if collection and hasattr(collection, 'count') else 0
    logger.info(
        'Ingestion complete. %s documents processed, %s added. Collection: %s -> %s',
        len(documents), total_added, existing_count, final_count,
    )


if __name__ == '__main__':
    use_llm = '--no-llm' not in sys.argv
    ingest_yargitay(use_llm=use_llm)
