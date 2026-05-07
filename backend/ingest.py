import hashlib
import logging
from pathlib import Path

from app.config import ensure_directories, settings
from app.json_loader import extract_json_documents, list_json_paths
from app.vector_store import get_vector_store

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
)
logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 256


def build_chunk_id(document_key: str, source: str, madde_no: str, content: str) -> str:
    document_hash = hashlib.sha1(document_key.encode('utf-8')).hexdigest()[:12]
    content_hash = hashlib.sha1(content.encode('utf-8')).hexdigest()[:16]
    return f'{document_hash}:{source}:{madde_no}:{content_hash}'


def _get_collection_count(vector_store) -> int:
    collection = getattr(vector_store, '_collection', None)
    if collection and hasattr(collection, 'count'):
        return int(collection.count())
    return 0


def _get_existing_ids(vector_store, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    existing = vector_store.get(ids=ids, include=['metadatas'])
    return set(existing.get('ids') or [])


def _chunk_file(vector_store, json_path: Path, file_index: int, total_files: int) -> tuple[int, int]:
    try:
        chunks = extract_json_documents(json_path)
    except Exception:
        logger.exception('[%s/%s] Failed to parse %s', file_index, total_files, json_path.name)
        return 0, 0

    if not chunks:
        logger.info('[%s/%s] Skipping %s: no maddeler created', file_index, total_files, json_path.name)
        return 0, 0

    for chunk in chunks:
        chunk.page_content = f"passage: {chunk.page_content}"

    chunk_ids = [
        build_chunk_id(
            document_key=json_path.as_posix().lower(),
            source=str(chunk.metadata.get('source', 'unknown')),
            madde_no=str(chunk.metadata.get('madde_no', '0')),
            content=chunk.page_content,
        )
        for chunk in chunks
    ]

    added = 0
    for start in range(0, len(chunks), UPSERT_BATCH_SIZE):
        end = start + UPSERT_BATCH_SIZE
        batch_docs = chunks[start:end]
        batch_ids = chunk_ids[start:end]

        try:
            existing_ids = _get_existing_ids(vector_store, batch_ids)
        except Exception:
            logger.exception(
                '[%s/%s] Failed duplicate check for %s batch %s-%s',
                file_index,
                total_files,
                json_path.name,
                start,
                min(end, len(chunks)),
            )
            continue
        new_docs: list = []
        new_ids: list[str] = []

        for doc, doc_id in zip(batch_docs, batch_ids):
            if doc_id in existing_ids:
                continue
            new_docs.append(doc)
            new_ids.append(doc_id)

        if new_docs:
            try:
                vector_store.add_documents(documents=new_docs, ids=new_ids)
            except Exception:
                logger.exception(
                    '[%s/%s] Failed indexing %s batch %s-%s',
                    file_index,
                    total_files,
                    json_path.name,
                    start,
                    min(end, len(chunks)),
                )
                continue
            added += len(new_docs)

        logger.info(
            '[%s/%s] %s chunk progress: %s/%s processed, %s added in current batch',
            file_index,
            total_files,
            json_path.name,
            min(end, len(chunks)),
            len(chunks),
            len(new_docs),
        )

    logger.info(
        '[%s/%s] Completed %s: %s chunks processed, %s chunks added',
        file_index,
        total_files,
        json_path.name,
        len(chunks),
        added,
    )
    return len(chunks), added


def ingest_single_file(vector_store, json_path: Path) -> tuple[int, int]:
    """Process and ingest a single JSON file, returning (chunks_processed, chunks_added)."""
    ensure_directories()
    return _chunk_file(vector_store, json_path, 1, 1)


def ingest() -> None:
    ensure_directories()
    vector_store = get_vector_store()

    json_paths = list_json_paths(settings.DATA_DIR)
    if not json_paths:
        logger.warning('No documents to ingest.')
        return

    existing_before = _get_collection_count(vector_store)
    if existing_before > 0:
        logger.info('Existing embeddings found: %s chunks already indexed', existing_before)
    else:
        logger.info('No existing embeddings found. Starting fresh ingestion.')

    total_chunks_processed = 0
    total_chunks_added = 0
    total_files = len(json_paths)

    logger.info('Starting ingestion for %s JSON files', total_files)
    for file_index, json_path in enumerate(json_paths, start=1):
        processed, added = _chunk_file(vector_store, json_path, file_index, total_files)
        total_chunks_processed += processed
        total_chunks_added += added

    if hasattr(vector_store, 'persist'):
        vector_store.persist()

    existing_after = _get_collection_count(vector_store)
    logger.info(
        'Ingestion complete. %s chunks processed, %s chunks added. Collection size: %s -> %s',
        total_chunks_processed,
        total_chunks_added,
        existing_before,
        existing_after,
    )


if __name__ == '__main__':
    ingest()
